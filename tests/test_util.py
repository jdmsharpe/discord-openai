from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIError

from discord_openai.cogs.openai.tooling import (
    TOOL_CODE_INTERPRETER,
    TOOL_FILE_SEARCH,
    TOOL_SHELL,
    TOOL_WEB_SEARCH,
)
from discord_openai.util import (
    CONTEXT_MANAGEMENT,
    DEEP_RESEARCH_MODELS,
    IMAGE_PRICING,
    IMAGE_PRICING_DEFAULTS,
    INPUT_FILE_TYPE,
    INPUT_IMAGE_TYPE,
    INPUT_TEXT_TYPE,
    MODEL_PRICING,
    PROMPT_CACHE_RETENTION,
    REASONING_EFFORT_HIGH,
    REASONING_EFFORT_MEDIUM,
    STT_PRICING_PER_MINUTE,
    TTS_PRICING_PER_CHAR,
    VIDEO_PRICING_PER_SECOND,
    ImageGenerationParameters,
    ResearchParameters,
    ResponseParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
    _extract_response_error_info,
    _parse_error_payload,
    build_attachment_content_block,
    build_input_content,
    calculate_cost,
    calculate_image_cost,
    calculate_stt_cost,
    calculate_tool_cost,
    calculate_tts_cost,
    calculate_video_cost,
    chunk_text,
    estimate_audio_duration_seconds,
    extract_usage,
    format_openai_error,
    hash_user_id,
    truncate_text,
)


class TestResponseParameters:
    def test_to_dict_basic(self):
        """Test basic to_dict output for non-reasoning model."""
        params = ResponseParameters(
            model="gpt-5.2",
            instructions="You are a helpful assistant.",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Hello!"}],
            frequency_penalty=0.5,
            presence_penalty=0.3,
            temperature=0.8,
            top_p=0.9,
        )
        result = params.to_dict()
        assert result["model"] == "gpt-5.2"
        assert result["instructions"] == "You are a helpful assistant."
        assert result["input"] == [{"type": INPUT_TEXT_TYPE, "text": "Hello!"}]
        assert result["frequency_penalty"] == 0.5
        assert result["presence_penalty"] == 0.3
        assert result["temperature"] == 0.8
        assert result["top_p"] == 0.9
        assert "reasoning" not in result
        assert "previous_response_id" not in result

    def test_reasoning_model_behavior(self):
        """Test that reasoning models use reasoning parameter instead of temperature/top_p."""
        params = ResponseParameters(
            model="o1",  # Reasoning model
            instructions="Test instructions",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            temperature=0.5,  # Should be ignored
            top_p=0.8,  # Should be ignored
        )
        result = params.to_dict()
        assert result["model"] == "o1"
        assert "temperature" not in result
        assert "top_p" not in result
        assert "reasoning" in result
        assert result["reasoning"]["effort"] == REASONING_EFFORT_MEDIUM

    def test_reasoning_model_custom_effort(self):
        """Test that custom reasoning effort is respected."""
        params = ResponseParameters(
            model="o3",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            reasoning={"effort": REASONING_EFFORT_HIGH},
        )
        result = params.to_dict()
        assert result["reasoning"]["effort"] == REASONING_EFFORT_HIGH

    def test_non_reasoning_model_behavior(self):
        """Test that non-reasoning models use temperature and top_p."""
        params = ResponseParameters(
            model="gpt-4o",  # Not a reasoning model and not in GPT5_NO_TEMP_MODELS
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            temperature=0.7,
            top_p=0.9,
        )
        result = params.to_dict()
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
        assert "reasoning" not in result

    def test_gpt5_no_temp_models_strip_temperature(self):
        """Test that gpt-5, gpt-5-mini, gpt-5-nano never allow temperature/top_p."""
        for model in ("gpt-5", "gpt-5-mini", "gpt-5-nano"):
            params = ResponseParameters(
                model=model,
                input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
                temperature=0.7,
                top_p=0.9,
            )
            result = params.to_dict()
            assert "temperature" not in result, f"{model} should strip temperature"
            assert "top_p" not in result, f"{model} should strip top_p"

    def test_reasoning_effort_strips_temperature(self):
        """Test that temperature/top_p are stripped when reasoning effort is not none."""
        params = ResponseParameters(
            model="gpt-5.4",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            temperature=0.7,
            top_p=0.9,
            reasoning={"effort": "high"},
        )
        result = params.to_dict()
        assert "temperature" not in result
        assert "top_p" not in result
        assert result["reasoning"]["effort"] == "high"

    def test_reasoning_effort_none_keeps_temperature(self):
        """Test that temperature/top_p are kept when reasoning effort is 'none'."""
        params = ResponseParameters(
            model="gpt-5.4",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            temperature=0.7,
            top_p=0.9,
            reasoning={"effort": "none"},
        )
        result = params.to_dict()
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9

    def test_verbosity_included_in_payload(self):
        """Test that verbosity is included in the text block when set."""
        params = ResponseParameters(
            model="gpt-5.4",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            verbosity="low",
        )
        result = params.to_dict()
        assert result["text"] == {"verbosity": "low"}

    def test_verbosity_omitted_when_not_set(self):
        """Test that text block is omitted when verbosity is not set."""
        params = ResponseParameters(
            model="gpt-5.4",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
        )
        result = params.to_dict()
        assert "text" not in result

    def test_previous_response_id(self):
        """Test that previous_response_id is included when set."""
        params = ResponseParameters(
            model="gpt-5.2",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Follow-up"}],
            previous_response_id="resp_abc123",
        )
        result = params.to_dict()
        assert result["previous_response_id"] == "resp_abc123"

    def test_input_with_image(self):
        """Test input with text and image content."""
        params = ResponseParameters(
            model="gpt-5.2",
            input=[
                {"type": INPUT_TEXT_TYPE, "text": "What's in this image?"},
                {
                    "type": INPUT_IMAGE_TYPE,
                    "image_url": "https://example.com/image.jpg",
                },
            ],
        )
        result = params.to_dict()
        assert len(result["input"]) == 2
        assert result["input"][0]["type"] == "text"
        assert result["input"][1]["type"] == "image_url"

    def test_discord_fields_excluded(self):
        """Test that Discord-specific fields are not included in to_dict."""
        params = ResponseParameters(
            model="gpt-5.2",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            conversation_starter="user123",
            conversation_id=123456,
            channel_id=789012,
            paused=True,
            response_id_history=["resp_1", "resp_2"],
            tool_names=["web_search"],
            mcp_preset_names=["github"],
            pending_mcp_approval={
                "approval_request_id": "mcpr_1",
                "request_response_id": "resp_pending",
                "server_label": "GitHub",
                "tool_name": "create_issue",
                "arguments": "{}",
                "intro_title": None,
                "intro_description": None,
                "attachment_url": None,
                "input_tokens": 10,
                "output_tokens": 5,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
                "tool_call_counts": {},
            },
        )
        result = params.to_dict()
        assert "conversation_starter" not in result
        assert "conversation_id" not in result
        assert "channel_id" not in result
        assert "paused" not in result
        assert "response_id_history" not in result
        assert "tool_names" not in result
        assert "mcp_preset_names" not in result
        assert "pending_mcp_approval" not in result

    def test_response_parameters_store_mcp_fields(self):
        params = ResponseParameters(
            model="gpt-5.4",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            tools=[{"type": "web_search"}],
            tool_names=["web_search"],
            mcp_preset_names=["github", "gmail"],
        )

        assert params.tool_names == ["web_search"]
        assert params.mcp_preset_names == ["github", "gmail"]
        assert params.pending_mcp_approval is None

    def test_input_string_format(self):
        """Test that input can be a simple string."""
        params = ResponseParameters(
            model="gpt-5.2",
            input="Hello, world!",
        )
        result = params.to_dict()
        assert result["input"] == "Hello, world!"

    def test_input_list_format(self):
        """Test that input can be a list of content items for multimodal."""
        params = ResponseParameters(
            model="gpt-5.2",
            input=[
                {"type": INPUT_TEXT_TYPE, "text": "What's in this?"},
                {"type": INPUT_IMAGE_TYPE, "image_url": "https://example.com/img.jpg"},
            ],
        )
        result = params.to_dict()
        assert len(result["input"]) == 2

    def test_response_id_history_default_isolated(self):
        """Test that response_id_history list is isolated between instances."""
        params_one = ResponseParameters()
        params_one.response_id_history.append("resp_123")
        params_two = ResponseParameters()
        assert params_two.response_id_history == []
        assert params_one.response_id_history is not params_two.response_id_history

    def test_tools_default_empty(self):
        """Tools should default to an empty list and be omitted from payload."""
        params = ResponseParameters()
        assert params.tools == []
        assert "tools" not in params.to_dict()

    def test_tools_single_included_in_payload(self):
        """Tools should be included in API payload when configured."""
        params = ResponseParameters(tools=[TOOL_WEB_SEARCH])
        result = params.to_dict()
        assert "tools" in result
        assert result["tools"] == [TOOL_WEB_SEARCH]

    def test_tools_multiple_included_in_payload(self):
        """Multiple tools should be serialized in order."""
        params = ResponseParameters(tools=[TOOL_WEB_SEARCH, TOOL_CODE_INTERPRETER])
        result = params.to_dict()
        assert result["tools"] == [TOOL_WEB_SEARCH, TOOL_CODE_INTERPRETER]

    def test_tools_file_search_and_shell_included(self):
        """Additional tools should be serialized correctly."""
        params = ResponseParameters(tools=[TOOL_FILE_SEARCH, TOOL_SHELL])
        result = params.to_dict()
        assert result["tools"] == [TOOL_FILE_SEARCH, TOOL_SHELL]

    def test_tools_default_isolated_between_instances(self):
        """Default tools list should not be shared across instances."""
        params_one = ResponseParameters()
        params_one.tools.append(TOOL_WEB_SEARCH.copy())
        params_two = ResponseParameters()
        assert params_two.tools == []
        assert params_one.tools is not params_two.tools

    def test_context_management_always_present(self):
        """context_management with compaction should always be in to_dict output."""
        params = ResponseParameters()
        result = params.to_dict()
        assert result["context_management"] == CONTEXT_MANAGEMENT
        assert result["context_management"][0]["type"] == "compaction"
        assert result["context_management"][0]["compact_threshold"] == 200_000

    def test_prompt_cache_retention_always_present(self):
        """prompt_cache_retention should always be in to_dict output."""
        params = ResponseParameters()
        result = params.to_dict()
        assert result["prompt_cache_retention"] == PROMPT_CACHE_RETENTION
        assert result["prompt_cache_retention"] == "24h"


class TestImageGenerationParameters:
    def test_to_dict(self):
        params = ImageGenerationParameters(
            prompt="A house in the woods",
            model="gpt-image-1.5",
            n=1,
            quality="high",
            size="1024x1024",
        )
        result = params.to_dict()
        assert result["prompt"] == "A house in the woods"
        assert result["model"] == "gpt-image-1.5"
        assert result["n"] == 1
        assert result["quality"] == "high"
        assert result["size"] == "1024x1024"

    def test_defaults(self):
        params = ImageGenerationParameters(prompt="Test prompt")
        result = params.to_dict()
        assert result["model"] == "gpt-image-1.5"
        assert result["quality"] == "auto"
        assert result["size"] == "auto"
        assert result["n"] == 1

    def test_quality_auto(self):
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1.5",
            quality="auto",
        )
        result = params.to_dict()
        assert result["quality"] == "auto"

    def test_size_auto(self):
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1.5",
            size="auto",
        )
        result = params.to_dict()
        assert result["size"] == "auto"


class TestTextToSpeechParameters:
    def test_to_dict(self):
        params = TextToSpeechParameters(
            input="Hello, world!",
            model="gpt-4o-mini-tts",
            voice="alloy",
            response_format="mp3",
            speed=1.0,
        )
        result = params.to_dict()
        assert result["input"] == "Hello, world!"
        assert result["model"] == "gpt-4o-mini-tts"
        assert result["voice"] == "alloy"
        assert result["response_format"] == "mp3"
        assert result["speed"] == 1.0

    def test_standard_voice_preserved_for_tts(self):
        params = TextToSpeechParameters(input="Hi", model="tts-1", voice="echo")
        assert params.voice == "echo"
        assert params.instructions is None

    def test_invalid_voice_falls_back_to_default(self):
        params = TextToSpeechParameters(input="Hi", model="tts-1", voice="marin")
        assert params.voice == "coral"
        assert params.instructions is None

    def test_rich_model_retains_voice_and_instructions(self):
        params = TextToSpeechParameters(
            input="Hi",
            model="gpt-4o-mini-tts",
            voice="ash",
            instructions="whisper tone",
        )
        assert params.voice == "ash"
        assert params.instructions == "whisper tone"


class TestVideoGenerationParameters:
    def test_to_dict(self):
        params = VideoGenerationParameters(
            prompt="A cat playing piano",
            model="sora-2",
            size="1280x720",
            seconds="8",
        )
        result = params.to_dict()
        assert result["prompt"] == "A cat playing piano"
        assert result["model"] == "sora-2"
        assert result["size"] == "1280x720"
        assert result["seconds"] == "8"

    def test_defaults(self):
        params = VideoGenerationParameters(prompt="Test video")
        result = params.to_dict()
        assert result["prompt"] == "Test video"
        assert result["model"] == "sora-2"
        assert result["size"] == "1280x720"
        assert result["seconds"] == "8"

    def test_sora_pro_model(self):
        params = VideoGenerationParameters(
            prompt="High quality video",
            model="sora-2-pro",
            size="1792x1024",
            seconds="12",
        )
        result = params.to_dict()
        assert result["model"] == "sora-2-pro"
        assert result["size"] == "1792x1024"
        assert result["seconds"] == "12"

    def test_portrait_size(self):
        params = VideoGenerationParameters(
            prompt="Portrait video",
            size="720x1280",
        )
        result = params.to_dict()
        assert result["size"] == "720x1280"

    def test_tall_portrait_size(self):
        params = VideoGenerationParameters(
            prompt="Tall portrait video",
            size="1024x1792",
        )
        result = params.to_dict()
        assert result["size"] == "1024x1792"

    def test_four_seconds(self):
        params = VideoGenerationParameters(
            prompt="Short video",
            seconds="4",
        )
        result = params.to_dict()
        assert result["seconds"] == "4"


class TestResearchParameters:
    def test_defaults(self):
        params = ResearchParameters(prompt="Test research")
        assert params.prompt == "Test research"
        assert params.model == "o3-deep-research"
        assert params.file_search is False
        assert params.code_interpreter is False

    def test_to_dict_basic(self):
        params = ResearchParameters(prompt="What is quantum computing?")
        tools = [TOOL_WEB_SEARCH]
        result = params.to_dict(tools)
        assert result["model"] == "o3-deep-research"
        assert result["input"] == "What is quantum computing?"
        assert result["tools"] == [TOOL_WEB_SEARCH]
        assert result["background"] is True

    def test_to_dict_with_multiple_tools(self):
        params = ResearchParameters(
            prompt="Analyze market data",
            model="o4-mini-deep-research",
            file_search=True,
            code_interpreter=True,
        )
        tools = [TOOL_WEB_SEARCH, TOOL_FILE_SEARCH, TOOL_CODE_INTERPRETER]
        result = params.to_dict(tools)
        assert result["model"] == "o4-mini-deep-research"
        assert len(result["tools"]) == 3
        assert result["background"] is True

    def test_deep_research_models_constant(self):
        assert "o3-deep-research" in DEEP_RESEARCH_MODELS
        assert "o4-mini-deep-research" in DEEP_RESEARCH_MODELS

    def test_deep_research_models_have_pricing(self):
        for model in DEEP_RESEARCH_MODELS:
            assert model in MODEL_PRICING, f"Missing pricing for {model}"


class TestChunkText:
    def test_chunk_text(self):
        text = "This is a test."
        size = 4
        result = list(chunk_text(text, size))
        # The text is split into chunks of size 4
        assert result == [
            "This",
            " is ",
            "a te",
            "st.",
        ]

    def test_chunk_text_long(self):
        text = "This is a test. " * 64  # len(text) * 64 = 1024
        size = 1024
        result = list(chunk_text(text, size))
        assert len(result[0]) == size


class TestTruncateText:
    def test_truncate_short_text(self):
        """Text under max_length should be returned unchanged."""
        text = "Hello, world!"
        result = truncate_text(text, 100)
        assert result == "Hello, world!"

    def test_truncate_exact_length(self):
        """Text exactly at max_length should be returned unchanged."""
        text = "12345"
        result = truncate_text(text, 5)
        assert result == "12345"

    def test_truncate_long_text(self):
        """Text over max_length should be truncated with suffix."""
        text = "This is a very long string that needs truncation"
        result = truncate_text(text, 10)
        assert result == "This is a ..."
        assert len(result) == 13  # 10 + len("...")

    def test_truncate_none(self):
        """None input should return None."""
        result = truncate_text(None, 100)
        assert result is None

    def test_truncate_custom_suffix(self):
        """Custom suffix should be used when truncating."""
        text = "This is a long string"
        result = truncate_text(text, 10, suffix="[...]")
        assert result == "This is a [...]"

    def test_truncate_empty_suffix(self):
        """Empty suffix should truncate without adding anything."""
        text = "Hello, world!"
        result = truncate_text(text, 5, suffix="")
        assert result == "Hello"

    def test_truncate_embed_prompt_limit(self):
        """Test with actual embed prompt limit (2000 chars)."""
        long_prompt = "x" * 2500
        result = truncate_text(long_prompt, 2000)
        assert len(result) == 2003  # 2000 + len("...")
        assert result.endswith("...") is True

    def test_truncate_embed_response_limit(self):
        """Test with actual embed response limit (3500 chars)."""
        long_response = "y" * 4000
        result = truncate_text(long_response, 3500)
        assert len(result) == 3503  # 3500 + len("...")
        assert result.endswith("...") is True


class TestBuildAttachmentContentBlock:
    def test_image_png(self):
        result = build_attachment_content_block("image/png", "https://cdn.example.com/photo.png")
        assert result["type"] == INPUT_IMAGE_TYPE
        assert result["image_url"] == "https://cdn.example.com/photo.png"

    def test_image_jpeg(self):
        result = build_attachment_content_block("image/jpeg", "https://cdn.example.com/photo.jpg")
        assert result["type"] == INPUT_IMAGE_TYPE

    def test_image_gif(self):
        result = build_attachment_content_block("image/gif", "https://cdn.example.com/anim.gif")
        assert result["type"] == INPUT_IMAGE_TYPE

    def test_image_webp(self):
        result = build_attachment_content_block("image/webp", "https://cdn.example.com/photo.webp")
        assert result["type"] == INPUT_IMAGE_TYPE

    def test_pdf_file(self):
        result = build_attachment_content_block(
            "application/pdf", "https://cdn.example.com/report.pdf"
        )
        assert result["type"] == INPUT_FILE_TYPE
        assert result["file_url"] == "https://cdn.example.com/report.pdf"

    def test_docx_file(self):
        result = build_attachment_content_block(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "https://cdn.example.com/doc.docx",
        )
        assert result["type"] == INPUT_FILE_TYPE
        assert result["file_url"] == "https://cdn.example.com/doc.docx"

    def test_csv_file(self):
        result = build_attachment_content_block("text/csv", "https://cdn.example.com/data.csv")
        assert result["type"] == INPUT_FILE_TYPE

    def test_text_plain(self):
        result = build_attachment_content_block("text/plain", "https://cdn.example.com/notes.txt")
        assert result["type"] == INPUT_FILE_TYPE

    def test_none_content_type(self):
        """Unknown/missing content type should default to input_file."""
        result = build_attachment_content_block(None, "https://cdn.example.com/mystery")
        assert result["type"] == INPUT_FILE_TYPE

    def test_content_type_with_charset(self):
        """Content types with parameters like charset should still match."""
        result = build_attachment_content_block(
            "image/png; charset=utf-8", "https://cdn.example.com/photo.png"
        )
        assert result["type"] == INPUT_IMAGE_TYPE


class TestModelPricing:
    CHAT_MODELS = [
        "gpt-5.4-pro",
        "gpt-5.4",
        "gpt-5.3-chat-latest",
        "gpt-5.2-pro",
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5-pro",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "o3-deep-research",
        "o4-mini-deep-research",
        "o4-mini",
        "o3-pro",
        "o3",
        "o3-mini",
        "o1-pro",
        "o1",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    def test_all_chat_models_have_pricing(self):
        for model in self.CHAT_MODELS:
            assert model in MODEL_PRICING, f"Missing pricing for {model}"

    def test_pricing_values_positive(self):
        for model, (inp, out) in MODEL_PRICING.items():
            assert inp > 0, f"{model} input price must be positive"
            assert out > 0, f"{model} output price must be positive"

    def test_output_price_gte_input_price(self):
        for model, (inp, out) in MODEL_PRICING.items():
            assert out >= inp, f"{model} output should be >= input price"

    def test_calculate_cost_known_model(self):
        cost = calculate_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost == pytest.approx(12.50)  # 2.50 + 10.00

    def test_calculate_cost_zero_tokens(self):
        cost = calculate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_calculate_cost_unknown_model_uses_default(self):
        cost = calculate_cost("unknown-model", 1_000_000, 1_000_000)
        assert cost == pytest.approx(12.50)  # default (2.50, 10.00)

    def test_calculate_cost_small_tokens(self):
        cost = calculate_cost("gpt-4.1-nano", 100, 50)
        expected = (100 / 1_000_000) * 0.10 + (50 / 1_000_000) * 0.40
        assert cost == pytest.approx(expected)


class TestImagePricing:
    IMAGE_MODELS = ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]
    QUALITIES = ["low", "medium", "high"]
    SIZES = ["1024x1024", "1024x1536", "1536x1024"]

    def test_all_combos_have_pricing(self):
        for model in self.IMAGE_MODELS:
            for quality in self.QUALITIES:
                for size in self.SIZES:
                    assert (model, quality, size) in IMAGE_PRICING, (
                        f"Missing pricing for ({model}, {quality}, {size})"
                    )

    def test_all_models_have_default(self):
        for model in self.IMAGE_MODELS:
            assert model in IMAGE_PRICING_DEFAULTS

    def test_pricing_values_positive(self):
        for key, price in IMAGE_PRICING.items():
            assert price > 0, f"{key} price must be positive"

    def test_calculate_known_combo(self):
        cost = calculate_image_cost("gpt-image-1.5", "high", "1024x1024")
        assert cost == pytest.approx(0.133)

    def test_calculate_auto_uses_default(self):
        cost = calculate_image_cost("gpt-image-1.5", "auto", "auto")
        assert cost == pytest.approx(IMAGE_PRICING_DEFAULTS["gpt-image-1.5"])

    def test_calculate_multiple_images(self):
        cost = calculate_image_cost("gpt-image-1-mini", "low", "1024x1024", n=3)
        assert cost == pytest.approx(0.005 * 3)

    def test_calculate_unknown_model_uses_fallback(self):
        cost = calculate_image_cost("unknown-model", "high", "1024x1024")
        assert cost == pytest.approx(0.034)  # global default


class TestTtsPricing:
    def test_all_models_have_pricing(self):
        for model in ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]:
            assert model in TTS_PRICING_PER_CHAR

    def test_calculate_known_model(self):
        cost = calculate_tts_cost("tts-1", 1_000_000)
        assert cost == pytest.approx(15.00)

    def test_calculate_tts_hd(self):
        cost = calculate_tts_cost("tts-1-hd", 1_000_000)
        assert cost == pytest.approx(30.00)

    def test_calculate_unknown_model(self):
        cost = calculate_tts_cost("unknown-tts", 1_000_000)
        assert cost == pytest.approx(15.00)  # default fallback

    def test_zero_characters(self):
        cost = calculate_tts_cost("tts-1", 0)
        assert cost == 0.0


class TestSttPricing:
    def test_all_models_have_pricing(self):
        for model in [
            "gpt-4o-transcribe",
            "gpt-4o-transcribe-diarize",
            "gpt-4o-mini-transcribe",
            "whisper-1",
        ]:
            assert model in STT_PRICING_PER_MINUTE

    def test_calculate_one_minute(self):
        cost = calculate_stt_cost("whisper-1", 60.0)
        assert cost == pytest.approx(0.006)

    def test_calculate_mini_transcribe(self):
        cost = calculate_stt_cost("gpt-4o-mini-transcribe", 120.0)
        assert cost == pytest.approx(0.006)  # $0.003/min * 2 min

    def test_zero_duration(self):
        cost = calculate_stt_cost("whisper-1", 0.0)
        assert cost == 0.0

    def test_estimate_duration_mp3(self):
        # 128kbps = 16000 bytes/sec, so 160000 bytes = 10 seconds
        duration = estimate_audio_duration_seconds(160_000, "audio.mp3")
        assert duration == pytest.approx(10.0)

    def test_estimate_duration_wav(self):
        # WAV ~88000 bytes/sec, so 880000 bytes = 10 seconds
        duration = estimate_audio_duration_seconds(880_000, "audio.wav")
        assert duration == pytest.approx(10.0)

    def test_estimate_duration_unknown_ext(self):
        # Falls back to compressed rate
        duration = estimate_audio_duration_seconds(160_000, "audio.ogg")
        assert duration == pytest.approx(10.0)


class TestVideoPricing:
    def test_all_models_have_pricing(self):
        for model in ["sora-2", "sora-2-pro"]:
            assert model in VIDEO_PRICING_PER_SECOND

    def test_calculate_sora_2(self):
        cost = calculate_video_cost("sora-2", 8)
        assert cost == pytest.approx(0.80)

    def test_calculate_sora_2_pro(self):
        cost = calculate_video_cost("sora-2-pro", 20)
        assert cost == pytest.approx(4.00)

    def test_calculate_unknown_model(self):
        cost = calculate_video_cost("unknown-video", 10)
        assert cost == pytest.approx(1.00)  # default $0.10/sec


class TestFormatOpenAIError:
    def test_format_openai_error_api_error(self):
        class DummyStatusError(APIError):
            def __init__(self, response_body):
                request = httpx.Request("POST", "https://api.example.com/test")
                super().__init__("Error code: 400", request, body=response_body)
                self.status_code = 400

        body = {
            "error": {
                "message": "Unsupported file format mov",
                "type": "invalid_request_error",
                "param": "file",
                "code": "unsupported_value",
            }
        }

        error = DummyStatusError(body)
        formatted = format_openai_error(error)
        expected = "\n".join(
            [
                "Unsupported file format mov",
                "",
                "Status: 400",
                "Error: DummyStatusError",
                "Type: invalid_request_error",
                "Code: unsupported_value",
                "Param: file",
            ]
        )
        assert formatted == expected

    def test_format_openai_error_generic_response(self):
        class DummyResponse:  # pragma: no cover - simple stand-in for http response
            def __init__(self):
                self.status_code = 403
                self.text = "Forbidden"

            def json(self):
                raise ValueError("No JSON available")

        class DummyException(Exception):
            def __init__(self, response):
                super().__init__("Request failed")
                self.response = response

        error = DummyException(DummyResponse())
        formatted = format_openai_error(error)
        expected = "\n".join(
            [
                "Forbidden",
                "",
                "Status: 403",
                "Error: DummyException",
            ]
        )
        assert formatted == expected


class TestHashUserId:
    def test_deterministic(self):
        """Same user ID should always produce the same hash."""
        assert hash_user_id(123456) == hash_user_id(123456)

    def test_length_is_16(self):
        """Hash should be truncated to 16 hex characters."""
        assert len(hash_user_id(99999)) == 16

    def test_different_ids_produce_different_hashes(self):
        assert hash_user_id(1) != hash_user_id(2)

    def test_hex_characters_only(self):
        """Output should only contain valid hex digits."""
        result = hash_user_id(42)
        assert all(c in "0123456789abcdef" for c in result) is True

    def test_large_user_id(self):
        """Should handle large Discord snowflake-style IDs."""
        result = hash_user_id(1234567890123456789)
        assert len(result) == 16


class TestCalculateToolCost:
    def test_single_web_search(self):
        cost = calculate_tool_cost({"web_search": 1})
        assert cost == pytest.approx(0.01)

    def test_multiple_web_searches(self):
        cost = calculate_tool_cost({"web_search": 5})
        assert cost == pytest.approx(0.05)

    def test_code_interpreter(self):
        cost = calculate_tool_cost({"code_interpreter": 1})
        assert cost == pytest.approx(0.03)

    def test_file_search(self):
        cost = calculate_tool_cost({"file_search": 1})
        assert cost == pytest.approx(0.0025)

    def test_shell(self):
        cost = calculate_tool_cost({"shell": 1})
        assert cost == pytest.approx(0.03)

    def test_mixed_tools(self):
        cost = calculate_tool_cost({"web_search": 3, "code_interpreter": 1})
        assert cost == pytest.approx(0.03 + 0.03)

    def test_empty_dict(self):
        cost = calculate_tool_cost({})
        assert cost == 0.0

    def test_unknown_tool_is_free(self):
        cost = calculate_tool_cost({"unknown_tool": 10})
        assert cost == 0.0

    def test_unknown_tool_mixed_with_known(self):
        cost = calculate_tool_cost({"web_search": 1, "some_future_tool": 5})
        assert cost == pytest.approx(0.01)


class TestExtractUsage:
    def test_full_usage(self):
        response = MagicMock()
        response.usage.input_tokens = 100
        response.usage.output_tokens = 200
        response.usage.input_tokens_details.cached_tokens = 50
        response.usage.output_tokens_details.reasoning_tokens = 30
        result = extract_usage(response)
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 200
        assert result["cached_tokens"] == 50
        assert result["reasoning_tokens"] == 30

    def test_no_usage_attribute(self):
        response = object()  # no 'usage' attribute
        result = extract_usage(response)
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["cached_tokens"] == 0
        assert result["reasoning_tokens"] == 0

    def test_none_token_values_default_to_zero(self):
        response = MagicMock()
        response.usage.input_tokens = None
        response.usage.output_tokens = None
        response.usage.input_tokens_details.cached_tokens = None
        response.usage.output_tokens_details.reasoning_tokens = None
        result = extract_usage(response)
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["cached_tokens"] == 0
        assert result["reasoning_tokens"] == 0

    def test_no_details(self):
        """When input/output details are missing, cached/reasoning should be 0."""
        response = MagicMock()
        response.usage.input_tokens = 500
        response.usage.output_tokens = 300
        response.usage.input_tokens_details = None
        response.usage.output_tokens_details = None
        result = extract_usage(response)
        assert result["input_tokens"] == 500
        assert result["output_tokens"] == 300
        assert result["cached_tokens"] == 0
        assert result["reasoning_tokens"] == 0


class TestBuildInputContent:
    def test_text_only_no_attachments(self):
        """Plain text with no attachments returns a string."""
        result = build_input_content("Hello", [])
        assert result == "Hello"

    def test_none_text_no_attachments(self):
        result = build_input_content(None, [])
        assert result == ""

    def test_empty_text_no_attachments(self):
        result = build_input_content("", [])
        assert result == ""

    def test_text_with_image_attachment(self):
        att = MagicMock()
        att.content_type = "image/png"
        att.url = "https://cdn.example.com/photo.png"
        result = build_input_content("Describe this", [att])
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"type": "text", "text": "Describe this"}
        assert result[1]["type"] == "image_url"
        assert result[1]["image_url"] == "https://cdn.example.com/photo.png"

    def test_text_with_file_attachment(self):
        att = MagicMock()
        att.content_type = "application/pdf"
        att.url = "https://cdn.example.com/doc.pdf"
        result = build_input_content("Read this", [att])
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[1]["type"] == "input_file"
        assert result[1]["file_url"] == "https://cdn.example.com/doc.pdf"

    def test_no_text_with_attachment(self):
        att = MagicMock()
        att.content_type = "image/jpeg"
        att.url = "https://cdn.example.com/img.jpg"
        result = build_input_content(None, [att])
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "image_url"

    def test_multiple_attachments(self):
        att1 = MagicMock()
        att1.content_type = "image/png"
        att1.url = "https://cdn.example.com/a.png"
        att2 = MagicMock()
        att2.content_type = "application/pdf"
        att2.url = "https://cdn.example.com/b.pdf"
        result = build_input_content("Check these", [att1, att2])
        assert isinstance(result, list)
        assert len(result) == 3  # text + 2 attachments

    def test_attachment_missing_url_skipped(self):
        att = MagicMock()
        att.content_type = "image/png"
        att.url = None
        result = build_input_content("Hello", [att])
        # Attachment with None url is skipped, only text remains
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"

    def test_attachment_missing_content_type_skipped(self):
        att = MagicMock()
        att.content_type = None
        att.url = "https://cdn.example.com/mystery"
        result = build_input_content("Hello", [att])
        # content_type is None, so the `content_type and url` check fails
        assert isinstance(result, list)
        assert len(result) == 1

    def test_all_attachments_invalid_falls_back(self):
        """If all attachments are skipped, returns text or empty string."""
        att = MagicMock()
        att.content_type = None
        att.url = None
        result = build_input_content(None, [att])
        # content is empty list, falls back to text or ""
        assert result == ""


class TestParseErrorPayload:
    def test_standard_openai_error_body(self):
        payload = {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit",
                "param": None,
            }
        }
        result = _parse_error_payload(payload)
        assert result["message"] == "Rate limit exceeded"
        assert result["type"] == "rate_limit_error"
        assert result["code"] == "rate_limit"
        assert "param" not in result  # None is not a str, so excluded

    def test_flat_error_fields(self):
        payload = {
            "message": "Something went wrong",
            "type": "server_error",
        }
        result = _parse_error_payload(payload)
        assert result["message"] == "Something went wrong"
        assert result["type"] == "server_error"

    def test_non_dict_returns_empty(self):
        assert _parse_error_payload("not a dict") == {}
        assert _parse_error_payload(None) == {}
        assert _parse_error_payload(42) == {}

    def test_empty_dict(self):
        assert _parse_error_payload({}) == {}

    def test_whitespace_values_excluded(self):
        payload = {"message": "  ", "type": "valid_type"}
        result = _parse_error_payload(payload)
        assert "message" not in result
        assert result["type"] == "valid_type"


class TestExtractResponseErrorInfo:
    def test_none_response(self):
        assert _extract_response_error_info(None) == {}

    def test_json_with_standard_error(self):
        response = MagicMock()
        response.json.return_value = {
            "error": {
                "message": "Invalid API key",
                "type": "auth_error",
            }
        }
        result = _extract_response_error_info(response)
        assert result["message"] == "Invalid API key"
        assert result["type"] == "auth_error"

    def test_json_with_detail_fallback(self):
        response = MagicMock()
        response.json.return_value = {"detail": "Not found"}
        result = _extract_response_error_info(response)
        assert result["message"] == "Not found"

    def test_json_parse_failure_falls_back_to_text(self):
        response = MagicMock()
        response.json.side_effect = ValueError("No JSON")
        response.text = "Internal Server Error"
        result = _extract_response_error_info(response)
        assert result["message"] == "Internal Server Error"

    def test_no_json_method_uses_text(self):
        class SimpleResponse:
            text = "Bad Gateway"

        result = _extract_response_error_info(SimpleResponse())
        assert result["message"] == "Bad Gateway"

    def test_empty_text_returns_empty(self):
        response = MagicMock()
        response.json.side_effect = ValueError()
        response.text = "   "
        result = _extract_response_error_info(response)
        assert result == {}
