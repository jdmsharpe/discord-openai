import re
from typing import List, Optional

CHUNK_TEXT_SIZE = 3500  # Maximum number of characters in each text chunk.
REASONING_MODELS = ["o4-mini", "o3", "o3-mini", "o1", "o1-mini"]
RICH_TTS_MODELS = ["gpt-4o-tts", "gpt-4o-mini-tts"]
RICH_TTS_VOICES = ["ash", "ballad", "coral", "sage", "verse"]


class ChatCompletionParameters:
    def __init__(
        self,
        messages: List[dict] = [],
        model: str = "gpt-4.1",
        persona: str = "You are a helpful assistant.",
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        conversation_starter: Optional[str] = None,
        conversation_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        paused: Optional[bool] = False,
    ):
        self.messages = messages
        self.model = model
        self.persona = persona
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.seed = seed

        # Define the models that do not support custom temperature and top_p.
        if model in REASONING_MODELS:
            # For reasoning models, force the default temperature (1.0) and ignore top_p.
            self.temperature = 1.0
            self.top_p = None
        else:
            self.temperature = temperature
            self.top_p = top_p

        self.conversation_starter = conversation_starter
        self.conversation_id = conversation_id
        self.channel_id = channel_id
        self.paused = paused

    def to_dict(self):
        # Create a copy of messages to avoid mutating the original list.
        messages_copy = [msg.copy() for msg in self.messages]
        for message in messages_copy:
            if "content" in message:
                # Ensure the content is a list of dictionaries if not already.
                if not isinstance(message["content"], list):
                    message["content"] = [message["content"]]

        payload = {
            "messages": messages_copy,
            "model": self.model,
        }
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            payload["presence_penalty"] = self.presence_penalty
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_p is not None:
            payload["top_p"] = self.top_p

        return payload


class ImageGenerationParameters:
    def __init__(
        self,
        prompt: str = "",
        model: str = "gpt-image-1",
        n: int = 1,
        quality: str = "medium",
        size: str = "1024x1024",
        style: Optional[str] = None,
        response_format: str = "url",
    ):
        # Validate types to help debug the "Constructor parameter should be str" error
        if not isinstance(prompt, str):
            raise TypeError(f"prompt must be str, got {type(prompt).__name__}: {prompt}")
        if not isinstance(model, str):
            raise TypeError(f"model must be str, got {type(model).__name__}: {model}")
        if not isinstance(n, int):
            raise TypeError(f"n must be int, got {type(n).__name__}: {n}")
        if not isinstance(quality, str):
            raise TypeError(f"quality must be str, got {type(quality).__name__}: {quality}")
        if not isinstance(size, str):
            raise TypeError(f"size must be str, got {type(size).__name__}: {size}")
        if style is not None and not isinstance(style, str):
            raise TypeError(f"style must be str or None, got {type(style).__name__}: {style}")
        if not isinstance(response_format, str):
            raise TypeError(f"response_format must be str, got {type(response_format).__name__}: {response_format}")
        
        self.prompt = prompt
        self.model = model
        self.n = n
        
        # Set appropriate quality based on model if using default
        if quality == "medium" and model in ["dall-e-2", "dall-e-3"]:
            self.quality = "standard"  # DALL-E models use "standard" as default
        else:
            self.quality = quality
            
        self.size = size
        self.style = style
        self.response_format = response_format

    def to_dict(self):
        payload = {
            "prompt": self.prompt,
            "model": self.model,
            "n": self.n,
            "quality": self.quality,
            "size": self.size,
            "response_format": self.response_format,
        }
        if self.style is not None:
            payload["style"] = self.style
        return payload


class TextToSpeechParameters:
    def __init__(
        self,
        input: str = "",
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
        instructions: str = "",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        self.input = input
        self.model = model

        # Older models do not support all voices.
        if model not in RICH_TTS_MODELS:
            if voice not in RICH_TTS_VOICES:
                # User picked a voice that is not supported by the model.
                # For TTS-1 and TTS-1-HD, force the default voice (Alloy).
                self.voice = "alloy"

            self.instructions = None
        else:
            self.voice = voice
            self.instructions = instructions

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


def extract_urls(text):
    url_pattern = (
        r"http[s]?://(?:[a-zA-Z0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    urls = re.findall(url_pattern, text)
    return urls
