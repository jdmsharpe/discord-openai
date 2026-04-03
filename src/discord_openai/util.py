import hashlib
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import aiohttp
from openai import APIError

CHUNK_TEXT_SIZE = 3500  # Maximum number of characters in each text chunk.

# Per-million-token pricing: (input_cost, output_cost)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.4-pro": (3.00, 12.00),
    "gpt-5.4": (2.00, 8.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.3-chat-latest": (2.00, 8.00),
    "gpt-5.2-pro": (3.00, 12.00),
    "gpt-5.2": (2.00, 8.00),
    "gpt-5.1": (2.00, 8.00),
    "gpt-5-pro": (5.00, 20.00),
    "gpt-5": (2.00, 8.00),
    "gpt-5-mini": (0.40, 1.60),
    "gpt-5-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o4-mini": (1.10, 4.40),
    "o3-pro": (20.00, 80.00),
    "o3": (10.00, 40.00),
    "o3-deep-research": (10.00, 40.00),
    "o4-mini-deep-research": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    "o1-pro": (150.00, 600.00),
    "o1": (15.00, 60.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4": (30.00, 60.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}


class UsageInfo(TypedDict):
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int


class PendingMcpApproval(TypedDict):
    approval_request_id: str
    request_response_id: str
    server_label: str
    tool_name: str
    arguments: str
    intro_title: str | None
    intro_description: str | None
    attachment_url: str | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    tool_call_counts: dict[str, int]


def extract_usage(response: Any) -> UsageInfo:
    """Extract token usage info from an OpenAI Responses API object."""
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    cached_tokens = getattr(input_details, "cached_tokens", 0) or 0
    reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def calculate_cost(
    model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> float:
    """Calculate the cost in dollars for a given model and token usage.

    Cached input tokens are billed at 50% of the regular input price.
    Reasoning tokens are already included in output_tokens at the standard output price.
    """
    input_price, output_price = MODEL_PRICING.get(model, (2.50, 10.00))
    non_cached = input_tokens - cached_tokens
    return (
        (non_cached / 1_000_000) * input_price
        + (cached_tokens / 1_000_000) * (input_price * 0.5)
        + (output_tokens / 1_000_000) * output_price
    )


# Per-call tool pricing (dollars per call/container)
TOOL_CALL_PRICING: dict[str, float] = {
    "web_search": 0.01,  # $10.00 / 1k calls
    "file_search": 0.0025,  # $2.50 / 1k calls (Responses API)
    "code_interpreter": 0.03,  # $0.03 / container (1 GB default)
    "shell": 0.03,  # $0.03 / container (same billing as code_interpreter)
}


def calculate_tool_cost(tool_call_counts: dict[str, int]) -> float:
    """Calculate the cost in dollars for tool calls made in a response."""
    return sum(count * TOOL_CALL_PRICING.get(tool, 0.0) for tool, count in tool_call_counts.items())


# ---------------------------------------------------------------------------
# Image generation pricing: (model, quality, size) -> cost per image
# ---------------------------------------------------------------------------
IMAGE_PRICING: dict[tuple[str, str, str], float] = {
    # GPT Image 1.5
    ("gpt-image-1.5", "low", "1024x1024"): 0.009,
    ("gpt-image-1.5", "low", "1024x1536"): 0.013,
    ("gpt-image-1.5", "low", "1536x1024"): 0.013,
    ("gpt-image-1.5", "medium", "1024x1024"): 0.034,
    ("gpt-image-1.5", "medium", "1024x1536"): 0.05,
    ("gpt-image-1.5", "medium", "1536x1024"): 0.05,
    ("gpt-image-1.5", "high", "1024x1024"): 0.133,
    ("gpt-image-1.5", "high", "1024x1536"): 0.20,
    ("gpt-image-1.5", "high", "1536x1024"): 0.20,
    # GPT Image 1
    ("gpt-image-1", "low", "1024x1024"): 0.011,
    ("gpt-image-1", "low", "1024x1536"): 0.016,
    ("gpt-image-1", "low", "1536x1024"): 0.016,
    ("gpt-image-1", "medium", "1024x1024"): 0.042,
    ("gpt-image-1", "medium", "1024x1536"): 0.063,
    ("gpt-image-1", "medium", "1536x1024"): 0.063,
    ("gpt-image-1", "high", "1024x1024"): 0.167,
    ("gpt-image-1", "high", "1024x1536"): 0.25,
    ("gpt-image-1", "high", "1536x1024"): 0.25,
    # GPT Image 1 Mini
    ("gpt-image-1-mini", "low", "1024x1024"): 0.005,
    ("gpt-image-1-mini", "low", "1024x1536"): 0.006,
    ("gpt-image-1-mini", "low", "1536x1024"): 0.006,
    ("gpt-image-1-mini", "medium", "1024x1024"): 0.011,
    ("gpt-image-1-mini", "medium", "1024x1536"): 0.015,
    ("gpt-image-1-mini", "medium", "1536x1024"): 0.015,
    ("gpt-image-1-mini", "high", "1024x1024"): 0.036,
    ("gpt-image-1-mini", "high", "1024x1536"): 0.052,
    ("gpt-image-1-mini", "high", "1536x1024"): 0.052,
}

# Default image costs when quality or size is "auto" (medium 1024x1024 estimate)
IMAGE_PRICING_DEFAULTS: dict[str, float] = {
    "gpt-image-1.5": 0.034,
    "gpt-image-1": 0.042,
    "gpt-image-1-mini": 0.011,
}


def calculate_image_cost(model: str, quality: str, size: str, n: int = 1) -> float:
    """Calculate cost for image generation based on model, quality, and size."""
    if quality == "auto" or size == "auto":
        per_image = IMAGE_PRICING_DEFAULTS.get(model, 0.034)
    else:
        per_image = IMAGE_PRICING.get(
            (model, quality, size),
            IMAGE_PRICING_DEFAULTS.get(model, 0.034),
        )
    return per_image * n


# ---------------------------------------------------------------------------
# TTS pricing: per character
# ---------------------------------------------------------------------------
TTS_PRICING_PER_CHAR: dict[str, float] = {
    "tts-1": 0.000015,  # $15.00 / 1M characters
    "tts-1-hd": 0.000030,  # $30.00 / 1M characters
    "gpt-4o-mini-tts": 0.000020,  # ~$0.015/min, ~750 chars/min
    "gpt-4o-tts": 0.000020,
}


def calculate_tts_cost(model: str, num_characters: int) -> float:
    """Calculate estimated cost for TTS based on input character count."""
    per_char = TTS_PRICING_PER_CHAR.get(model, 0.000015)
    return per_char * num_characters


# ---------------------------------------------------------------------------
# STT pricing: per minute of audio
# ---------------------------------------------------------------------------
STT_PRICING_PER_MINUTE: dict[str, float] = {
    "gpt-4o-transcribe": 0.006,
    "gpt-4o-transcribe-diarize": 0.006,
    "gpt-4o-mini-transcribe": 0.003,
    "whisper-1": 0.006,
}

# Rough bytes-per-second used to estimate audio duration from file size
_AUDIO_BPS_WAV = 88_000  # mono 16-bit 44.1 kHz
_AUDIO_BPS_COMPRESSED = 16_000  # ~128 kbps


def estimate_audio_duration_seconds(file_size_bytes: int, filename: str) -> float:
    """Estimate audio duration in seconds from file size and format."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    bps = _AUDIO_BPS_WAV if ext == "wav" else _AUDIO_BPS_COMPRESSED
    return file_size_bytes / bps


def calculate_stt_cost(model: str, duration_seconds: float) -> float:
    """Calculate cost for STT based on estimated audio duration."""
    per_minute = STT_PRICING_PER_MINUTE.get(model, 0.006)
    return per_minute * (duration_seconds / 60.0)


# ---------------------------------------------------------------------------
# Video generation pricing: per second of video
# ---------------------------------------------------------------------------
VIDEO_PRICING_PER_SECOND: dict[str, float] = {
    "sora-2": 0.10,
    "sora-2-pro": 0.20,
}


def calculate_video_cost(model: str, seconds: int) -> float:
    """Calculate cost for video generation."""
    per_second = VIDEO_PRICING_PER_SECOND.get(model, 0.10)
    return per_second * seconds


REASONING_MODELS = ["o4-mini", "o3-pro", "o3", "o3-mini", "o1-pro", "o1"]
DEEP_RESEARCH_MODELS = ["o3-deep-research", "o4-mini-deep-research"]

# Server-side compaction: automatically compress context when it exceeds this
# token threshold, preventing context-window overflow in long conversations.
CONTEXT_MANAGEMENT = [{"type": "compaction", "compact_threshold": 200_000}]

# Extended prompt caching: retain cached prefixes up to 24 hours instead of
# the default 5-10 minute in-memory window, improving cache hits across conversations.
PROMPT_CACHE_RETENTION = "24h"

# Input content types for Responses API
# For multimodal input, use content blocks within a message item
INPUT_TEXT_TYPE = "text"
INPUT_IMAGE_TYPE = "image_url"
INPUT_FILE_TYPE = "input_file"

# Image MIME type prefixes — everything else routes to input_file
IMAGE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


def hash_user_id(user_id: int) -> str:
    """Hash a numeric user ID into a short, stable safety identifier for OpenAI."""
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:16]


def build_attachment_content_block(content_type: str | None, url: str) -> dict:
    """Return the appropriate Responses API content block for an attachment.

    Images are sent as ``image_url`` blocks; all other supported file types
    (PDFs, documents, spreadsheets, code, etc.) are sent as ``input_file``
    blocks using the ``file_url`` field.
    """
    if content_type and content_type.split(";")[0].strip() in IMAGE_CONTENT_TYPES:
        return {"type": INPUT_IMAGE_TYPE, "image_url": url}
    return {"type": INPUT_FILE_TYPE, "file_url": url}


# Reasoning effort levels
REASONING_EFFORT_NONE = "none"
REASONING_EFFORT_MINIMAL = "minimal"
REASONING_EFFORT_LOW = "low"
REASONING_EFFORT_MEDIUM = "medium"
REASONING_EFFORT_HIGH = "high"
REASONING_EFFORT_XHIGH = "xhigh"

# GPT-5 base models that never support temperature/top_p
GPT5_NO_TEMP_MODELS = frozenset({"gpt-5", "gpt-5-mini", "gpt-5-nano"})
RICH_TTS_MODELS = ["gpt-4o-tts", "gpt-4o-mini-tts"]

RICH_TTS_VOICES = {"ballad", "verse", "marin", "cedar"}
STANDARD_TTS_VOICES = {"alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"}
DEFAULT_TTS_VOICE = "marin"
DEFAULT_STANDARD_TTS_VOICE = "coral"
MODEL_SUPPORTED_TTS_VOICES = {
    "tts-1": STANDARD_TTS_VOICES,
    "tts-1-hd": STANDARD_TTS_VOICES,
    "gpt-4o-tts": STANDARD_TTS_VOICES | RICH_TTS_VOICES,
    "gpt-4o-mini-tts": STANDARD_TTS_VOICES | RICH_TTS_VOICES,
}
DEFAULT_SUPPORTED_TTS_VOICES = STANDARD_TTS_VOICES | RICH_TTS_VOICES


class ResponseParameters:
    """Parameters for OpenAI Responses API (replacement for Chat Completions)."""

    def __init__(
        self,
        model: str = "gpt-5.4",
        instructions: str = "You are a helpful assistant.",
        input: Any = None,  # Can be string or list of content items
        previous_response_id: str | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning: dict | None = None,
        verbosity: str | None = None,
        tools: list[dict] | None = None,
        tool_names: list[str] | None = None,
        mcp_preset_names: list[str] | None = None,
        # Discord-specific fields (not sent to API)
        conversation_starter: Any | None = None,
        conversation_starter_id: int | None = None,
        conversation_id: int | None = None,
        channel_id: int | None = None,
        paused: bool = False,
        pending_mcp_approval: PendingMcpApproval | None = None,
        last_user_input: Any = None,
        last_user_message_id: int | None = None,
        updated_at: datetime | None = None,
        # For regeneration support
        response_id_history: list[str] | None = None,
        # OpenAI safety identifier (hashed user ID for abuse detection)
        safety_identifier: str | None = None,
    ):
        self.model = model
        self.instructions = instructions
        # Input can be a string or a list of content items
        self.input = input if input is not None else ""
        self.previous_response_id = previous_response_id

        # Handle model-specific reasoning and temperature/top_p restrictions.
        self.reasoning = reasoning
        if model in REASONING_MODELS:
            # o-series: reasoning required, temperature/top_p not supported.
            self.temperature = None
            self.top_p = None
            self.reasoning = (
                reasoning if reasoning else {"effort": REASONING_EFFORT_MEDIUM, "summary": "auto"}
            )
        elif model in GPT5_NO_TEMP_MODELS:
            # gpt-5, gpt-5-mini, gpt-5-nano never support temperature/top_p.
            self.temperature = None
            self.top_p = None
            self.reasoning = reasoning
        else:
            # GPT-5.4/5.2/5.1/5-pro, GPT-4.x, etc.
            # temperature/top_p are not supported when reasoning effort is not "none".
            effort = reasoning.get("effort") if reasoning else None
            if effort and effort != REASONING_EFFORT_NONE:
                self.temperature = None
                self.top_p = None
            else:
                self.temperature = temperature
                self.top_p = top_p
        self.verbosity = verbosity
        self.tools = [tool.copy() for tool in tools] if tools is not None else []
        self.tool_names = (
            list(tool_names)
            if tool_names is not None
            else [
                tool.get("type")
                for tool in self.tools
                if isinstance(tool, dict) and isinstance(tool.get("type"), str)
            ]
        )
        self.mcp_preset_names = list(mcp_preset_names) if mcp_preset_names is not None else []

        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

        # Discord-specific fields
        self.conversation_starter = conversation_starter
        self.conversation_starter_id = conversation_starter_id
        if self.conversation_starter_id is None and conversation_starter is not None:
            self.conversation_starter_id = getattr(conversation_starter, "id", None)
        self.conversation_id = conversation_id
        self.channel_id = channel_id
        self.paused = paused
        self.pending_mcp_approval = pending_mcp_approval
        self.last_user_input = deepcopy(last_user_input) if last_user_input is not None else None
        self.last_user_message_id = last_user_message_id
        self.updated_at = updated_at if updated_at is not None else datetime.now(timezone.utc)

        # Response ID history for regeneration
        self.response_id_history = response_id_history if response_id_history is not None else []
        self.safety_identifier = safety_identifier

    def touch(self) -> None:
        """Update the in-memory activity timestamp for this conversation."""
        self.updated_at = datetime.now(timezone.utc)

    def set_last_user_input(self, input_content: Any, message_id: int | None = None) -> None:
        """Store the latest normalized user input for deterministic regeneration."""
        self.last_user_input = deepcopy(input_content)
        self.last_user_message_id = message_id
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls (excludes Discord-specific fields)."""
        payload: dict[str, Any] = {
            "model": self.model,
        }

        if self.instructions:
            payload["instructions"] = self.instructions
        if self.input:
            payload["input"] = self.input
        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            payload["presence_penalty"] = self.presence_penalty
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.reasoning is not None:
            payload["reasoning"] = self.reasoning
        if self.verbosity:
            payload["text"] = {"verbosity": self.verbosity}
        if self.tools:
            payload["tools"] = self.tools
        payload["context_management"] = CONTEXT_MANAGEMENT
        payload["prompt_cache_retention"] = PROMPT_CACHE_RETENTION
        if self.instructions:
            payload["prompt_cache_key"] = hashlib.sha256(self.instructions.encode()).hexdigest()[
                :16
            ]
        if self.safety_identifier:
            payload["safety_identifier"] = self.safety_identifier

        return payload


class ImageGenerationParameters:
    def __init__(
        self,
        prompt: str = "",
        model: str = "gpt-image-1.5",
        n: int = 1,
        quality: str | None = "auto",
        size: str | None = "auto",
    ):
        self.prompt = prompt
        self.model = model
        self.n = n
        self.quality = quality
        self.size = size

    def to_dict(self):
        payload = {
            "prompt": self.prompt,
            "model": self.model,
            "n": self.n,
        }
        if self.quality is not None:
            payload["quality"] = self.quality
        if self.size is not None:
            payload["size"] = self.size
        return payload


class VideoGenerationParameters:
    """Parameters for OpenAI Video (Sora) API."""

    def __init__(
        self,
        prompt: str = "",
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
    ):
        self.prompt = prompt
        self.model = model
        self.size = size
        self.seconds = seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "prompt": self.prompt,
            "model": self.model,
            "size": self.size,
            "seconds": self.seconds,
        }


class ResearchParameters:
    """Parameters for OpenAI Deep Research via the Responses API with background mode."""

    def __init__(
        self,
        prompt: str = "",
        model: str = "o3-deep-research",
        file_search: bool = False,
        code_interpreter: bool = False,
    ):
        self.prompt = prompt
        self.model = model
        self.file_search = file_search
        self.code_interpreter = code_interpreter

    def to_dict(self, tools: list[dict]) -> dict[str, Any]:
        """Convert to dictionary for API calls.

        Args:
            tools: Pre-resolved tool list (web_search is always included).
        """
        return {
            "model": self.model,
            "input": self.prompt,
            "tools": tools,
            "background": True,
        }


class TextToSpeechParameters:
    def __init__(
        self,
        input: str = "",
        model: str = "gpt-4o-mini-tts",
        voice: str = DEFAULT_TTS_VOICE,
        instructions: str = "",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        self.input = input
        self.model = model

        supported_voices = MODEL_SUPPORTED_TTS_VOICES.get(model, DEFAULT_SUPPORTED_TTS_VOICES)
        if voice in supported_voices:
            self.voice = voice
        elif DEFAULT_TTS_VOICE in supported_voices:
            self.voice = DEFAULT_TTS_VOICE
        else:
            self.voice = DEFAULT_STANDARD_TTS_VOICE

        if model in RICH_TTS_MODELS:
            self.instructions = instructions
        else:
            self.instructions = None

        self.response_format = response_format
        self.speed = speed

    def to_dict(self):
        return {
            "input": self.input,
            "model": self.model,
            "voice": self.voice,
            "instructions": self.instructions,
            "response_format": self.response_format,
            "speed": self.speed,
        }


def chunk_text(text, size=CHUNK_TEXT_SIZE):
    """Yield successive size chunks from text."""
    return list(text[i : i + size] for i in range(0, len(text), size))


def truncate_text(text, max_length, suffix="..."):
    """Truncate text to max_length, adding suffix if truncated.

    Args:
        text: The text to truncate
        max_length: Maximum length before truncation
        suffix: String to append when truncated (default "...")

    Returns:
        Original text if under max_length, otherwise truncated with suffix
    """
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix


def _parse_error_payload(payload: Any) -> dict[str, str]:
    """Pull standard OpenAI error fields from a payload structure."""
    if not isinstance(payload, dict):
        return {}

    candidate = payload.get("error")
    if isinstance(candidate, dict):
        payload = candidate

    extracted: dict[str, str] = {}
    for key in ("message", "type", "code", "param"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            extracted[key] = value.strip()
    return extracted


def _extract_response_error_info(response: Any) -> dict[str, str]:
    """Attempt to parse error details from an HTTP-like response object."""
    info: dict[str, str] = {}
    if response is None:
        return info

    if hasattr(response, "json"):
        try:
            payload = response.json()
        except Exception:
            payload = None
        else:
            info = _parse_error_payload(payload)
            if not info and isinstance(payload, dict):
                for key in ("detail", "message", "error"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        info["message"] = value.strip()
                        break

    if "message" not in info:
        text_value = getattr(response, "text", None)
        if isinstance(text_value, str) and text_value.strip():
            info.setdefault("message", text_value.strip())

    return info


def format_openai_error(error: Exception) -> str:
    """Return a readable description for exceptions raised by OpenAI operations."""
    message = getattr(error, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(error).strip()

    status = getattr(error, "status_code", None)
    error_type = getattr(error, "type", None)
    code = getattr(error, "code", None)
    param = getattr(error, "param", None)

    if isinstance(error, APIError):
        extracted = _parse_error_payload(getattr(error, "body", None))
    else:
        response = getattr(error, "response", None)
        if response is not None and status is None:
            status = getattr(response, "status_code", None)
        extracted = _extract_response_error_info(response)

    if extracted.get("message"):
        message = extracted["message"]
    error_type = error_type or extracted.get("type")
    code = code or extracted.get("code")
    param = param or extracted.get("param")

    message = message or "An unexpected error occurred."

    details = []
    if status is not None:
        details.append(f"Status: {status}")

    error_name = type(error).__name__
    if error_name and error_name != "Exception":
        details.append(f"Error: {error_name}")

    if error_type:
        details.append(f"Type: {error_type}")
    if code:
        details.append(f"Code: {code}")
    if param:
        details.append(f"Param: {param}")

    if details:
        return f"{message}\n\n" + "\n".join(details)
    return message


def build_input_content(text: str | None, attachments: list) -> Any:
    """Build Responses API input from text and optional Discord attachments.

    Returns a plain string when there are no attachments, or a list of
    content blocks when multimodal input is needed.
    """
    if not attachments:
        return text or ""
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": INPUT_TEXT_TYPE, "text": text})
    for att in attachments:
        content_type = getattr(att, "content_type", None)
        url = getattr(att, "url", None)
        if content_type and url:
            content.append(build_attachment_content_block(content_type, url))
    return content if content else (text or "")


async def download_attachment(url: str, filename: str) -> Path:
    """Download a URL to a temp file and return the path. Caller must clean up."""
    async with aiohttp.ClientSession() as session, session.get(url) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to download the attachment (status {resp.status}).")
        path = Path(tempfile.gettempdir()) / Path(filename).name
        path.write_bytes(await resp.read())
        return path
