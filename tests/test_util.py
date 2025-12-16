import unittest
from openai import APIError
from util import (
    ChatCompletionParameters,
    ImageGenerationParameters,
    INPUT_IMAGE_TYPE,
    INPUT_TEXT_TYPE,
    REASONING_EFFORT_HIGH,
    REASONING_EFFORT_MEDIUM,
    ResponseParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
    chunk_text,
    extract_urls,
    format_openai_error,
    truncate_text,
)


class TestChatCompletionParameters(unittest.TestCase):
    def test_to_dict(self):
        params = ChatCompletionParameters(
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
            model="gpt-5.2",
            frequency_penalty=0.5,
            presence_penalty=0.5,
            seed=42,
            temperature=0.8,
            top_p=0.9,
        )
        result = params.to_dict()
        self.assertEqual(
            result["messages"],
            [{"role": "system", "content": ["You are a helpful assistant."]}],
        )
        self.assertEqual(result["model"], "gpt-5.2")
        self.assertEqual(result["frequency_penalty"], 0.5)
        self.assertEqual(result["presence_penalty"], 0.5)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["temperature"], 0.8)
        self.assertEqual(result["top_p"], 0.9)

    def test_reasoning_model_behavior(self):
        # Test that reasoning models force temperature=1.0 and ignore top_p
        params = ChatCompletionParameters(
            messages=[{"role": "user", "content": "Test message"}],
            model="o1",  # This is a reasoning model
            temperature=0.5,  # This should be overridden to 1.0
            top_p=0.8,  # This should be ignored (set to None)
        )
        result = params.to_dict()
        self.assertEqual(result["model"], "o1")
        self.assertEqual(result["temperature"], 1.0)  # Forced for reasoning models
        self.assertNotIn("top_p", result)  # Should not be included when None

    def test_non_reasoning_model_behavior(self):
        # Test that non-reasoning models use provided temperature and top_p
        params = ChatCompletionParameters(
            messages=[{"role": "user", "content": "Test message"}],
            model="gpt-5",  # This is NOT a reasoning model
            temperature=0.7,
            top_p=0.9,
        )
        result = params.to_dict()
        self.assertEqual(result["model"], "gpt-5")
        self.assertEqual(result["temperature"], 0.7)  # Should use provided value
        self.assertEqual(result["top_p"], 0.9)  # Should use provided value

    def test_messages_default_isolated(self):
        params_one = ChatCompletionParameters()
        params_one.messages.append(
            {"role": "user", "content": {"type": "text", "text": "hello"}}
        )
        params_two = ChatCompletionParameters()
        self.assertEqual(params_two.messages, [])
        self.assertIsNot(params_one.messages, params_two.messages)


class TestResponseParameters(unittest.TestCase):
    def test_to_dict_basic(self):
        """Test basic to_dict output for non-reasoning model."""
        params = ResponseParameters(
            model="gpt-5.2",
            instructions="You are a helpful assistant.",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Hello!"}],
            frequency_penalty=0.5,
            presence_penalty=0.3,
            seed=42,
            temperature=0.8,
            top_p=0.9,
        )
        result = params.to_dict()
        self.assertEqual(result["model"], "gpt-5.2")
        self.assertEqual(result["instructions"], "You are a helpful assistant.")
        self.assertEqual(result["input"], [{"type": INPUT_TEXT_TYPE, "text": "Hello!"}])
        self.assertEqual(result["frequency_penalty"], 0.5)
        self.assertEqual(result["presence_penalty"], 0.3)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["temperature"], 0.8)
        self.assertEqual(result["top_p"], 0.9)
        self.assertNotIn("reasoning", result)
        self.assertNotIn("previous_response_id", result)

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
        self.assertEqual(result["model"], "o1")
        self.assertNotIn("temperature", result)
        self.assertNotIn("top_p", result)
        self.assertIn("reasoning", result)
        self.assertEqual(result["reasoning"]["effort"], REASONING_EFFORT_MEDIUM)

    def test_reasoning_model_custom_effort(self):
        """Test that custom reasoning effort is respected."""
        params = ResponseParameters(
            model="o3",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            reasoning={"effort": REASONING_EFFORT_HIGH},
        )
        result = params.to_dict()
        self.assertEqual(result["reasoning"]["effort"], REASONING_EFFORT_HIGH)

    def test_non_reasoning_model_behavior(self):
        """Test that non-reasoning models use temperature and top_p."""
        params = ResponseParameters(
            model="gpt-5",  # Not a reasoning model
            input=[{"type": INPUT_TEXT_TYPE, "text": "Test"}],
            temperature=0.7,
            top_p=0.9,
        )
        result = params.to_dict()
        self.assertEqual(result["temperature"], 0.7)
        self.assertEqual(result["top_p"], 0.9)
        self.assertNotIn("reasoning", result)

    def test_previous_response_id(self):
        """Test that previous_response_id is included when set."""
        params = ResponseParameters(
            model="gpt-5.2",
            input=[{"type": INPUT_TEXT_TYPE, "text": "Follow-up"}],
            previous_response_id="resp_abc123",
        )
        result = params.to_dict()
        self.assertEqual(result["previous_response_id"], "resp_abc123")

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
        self.assertEqual(len(result["input"]), 2)
        self.assertEqual(result["input"][0]["type"], "text")
        self.assertEqual(result["input"][1]["type"], "image_url")

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
        )
        result = params.to_dict()
        self.assertNotIn("conversation_starter", result)
        self.assertNotIn("conversation_id", result)
        self.assertNotIn("channel_id", result)
        self.assertNotIn("paused", result)
        self.assertNotIn("response_id_history", result)

    def test_input_string_format(self):
        """Test that input can be a simple string."""
        params = ResponseParameters(
            model="gpt-5.2",
            input="Hello, world!",
        )
        result = params.to_dict()
        self.assertEqual(result["input"], "Hello, world!")

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
        self.assertEqual(len(result["input"]), 2)

    def test_response_id_history_default_isolated(self):
        """Test that response_id_history list is isolated between instances."""
        params_one = ResponseParameters()
        params_one.response_id_history.append("resp_123")
        params_two = ResponseParameters()
        self.assertEqual(params_two.response_id_history, [])
        self.assertIsNot(params_one.response_id_history, params_two.response_id_history)


class TestImageGenerationParameters(unittest.TestCase):
    def test_to_dict(self):
        params = ImageGenerationParameters(
            prompt="A house in the woods",
            model="dall-e-3",
            n=1,
            quality="standard",
            size="1024x1024",
            style="artistic",
        )
        result = params.to_dict()
        self.assertEqual(result["prompt"], "A house in the woods")
        self.assertEqual(result["model"], "dall-e-3")
        self.assertEqual(result["n"], 1)
        self.assertEqual(result["quality"], "standard")
        self.assertEqual(result["size"], "1024x1024")
        self.assertEqual(result["style"], "artistic")
        # response_format should not be included when not set
        self.assertNotIn("response_format", result)

    def test_quality_defaults_dalle3(self):
        # Test that DALL-E 3 converts "medium" default to "hd"
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="dall-e-3",
            quality="medium",  # This should become "hd"
        )
        result = params.to_dict()
        self.assertEqual(result["quality"], "hd")

    def test_quality_defaults_dalle2(self):
        # Test that DALL-E 2 converts "medium" default to "standard"
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="dall-e-2",
            quality="medium",  # This should become "standard"
        )
        result = params.to_dict()
        self.assertEqual(result["quality"], "standard")

    def test_quality_defaults_gpt_image(self):
        # Test that GPT Image models keep "medium" as is
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1.5",
            quality="medium",  # This should stay "medium"
        )
        result = params.to_dict()
        self.assertEqual(result["quality"], "medium")

    def test_response_format_dalle_models(self):
        # Test that response_format is included for DALL-E models when provided
        params = ImageGenerationParameters(
            prompt="Test prompt", model="dall-e-3", response_format="url"
        )
        result = params.to_dict()
        self.assertEqual(result["response_format"], "url")

    def test_response_format_gpt_image(self):
        # Test that response_format is NOT included for GPT Image models even when provided
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1.5",
            response_format="url",  # This should be ignored
        )
        result = params.to_dict()
        self.assertNotIn("response_format", result)

    def test_style_removal_gpt_image(self):
        # Test that style is set to None for GPT Image models in the constructor
        params = ImageGenerationParameters(
            prompt="Test prompt", model="gpt-image-1.5", style="natural"
        )
        # Style should be None, but let's verify the to_dict behavior
        result = params.to_dict()
        # Style should not be included when None
        if params.style is None:
            self.assertNotIn("style", result)
        else:
            self.assertIn("style", result)


class TestTextToSpeechParameters(unittest.TestCase):
    def test_to_dict(self):
        params = TextToSpeechParameters(
            input="Hello, world!",
            model="gpt-4o-mini-tts",
            voice="alloy",
            response_format="mp3",
            speed=1.0,
        )
        result = params.to_dict()
        self.assertEqual(result["input"], "Hello, world!")
        self.assertEqual(result["model"], "gpt-4o-mini-tts")
        self.assertEqual(result["voice"], "alloy")
        self.assertEqual(result["response_format"], "mp3")
        self.assertEqual(result["speed"], 1.0)

    def test_standard_voice_preserved_for_tts(self):
        params = TextToSpeechParameters(input="Hi", model="tts-1", voice="echo")
        self.assertEqual(params.voice, "echo")
        self.assertIsNone(params.instructions)

    def test_invalid_voice_falls_back_to_default(self):
        params = TextToSpeechParameters(input="Hi", model="tts-1", voice="ash")
        self.assertEqual(params.voice, "alloy")
        self.assertIsNone(params.instructions)

    def test_rich_model_retains_voice_and_instructions(self):
        params = TextToSpeechParameters(
            input="Hi",
            model="gpt-4o-mini-tts",
            voice="ash",
            instructions="whisper tone",
        )
        self.assertEqual(params.voice, "ash")
        self.assertEqual(params.instructions, "whisper tone")


class TestVideoGenerationParameters(unittest.TestCase):
    def test_to_dict(self):
        params = VideoGenerationParameters(
            prompt="A cat playing piano",
            model="sora-2",
            size="1280x720",
            seconds="8",
        )
        result = params.to_dict()
        self.assertEqual(result["prompt"], "A cat playing piano")
        self.assertEqual(result["model"], "sora-2")
        self.assertEqual(result["size"], "1280x720")
        self.assertEqual(result["seconds"], "8")

    def test_defaults(self):
        params = VideoGenerationParameters(prompt="Test video")
        result = params.to_dict()
        self.assertEqual(result["prompt"], "Test video")
        self.assertEqual(result["model"], "sora-2")
        self.assertEqual(result["size"], "1280x720")
        self.assertEqual(result["seconds"], "8")

    def test_sora_pro_model(self):
        params = VideoGenerationParameters(
            prompt="High quality video",
            model="sora-2-pro",
            size="1792x1024",
            seconds="12",
        )
        result = params.to_dict()
        self.assertEqual(result["model"], "sora-2-pro")
        self.assertEqual(result["size"], "1792x1024")
        self.assertEqual(result["seconds"], "12")

    def test_portrait_size(self):
        params = VideoGenerationParameters(
            prompt="Portrait video",
            size="720x1280",
        )
        result = params.to_dict()
        self.assertEqual(result["size"], "720x1280")

    def test_tall_portrait_size(self):
        params = VideoGenerationParameters(
            prompt="Tall portrait video",
            size="1024x1792",
        )
        result = params.to_dict()
        self.assertEqual(result["size"], "1024x1792")

    def test_four_seconds(self):
        params = VideoGenerationParameters(
            prompt="Short video",
            seconds="4",
        )
        result = params.to_dict()
        self.assertEqual(result["seconds"], "4")


class TestChunkText(unittest.TestCase):
    def test_chunk_text(self):
        text = "This is a test."
        size = 4
        result = list(chunk_text(text, size))
        # The text is split into chunks of size 4
        self.assertEqual(
            result,
            [
                "This",
                " is ",
                "a te",
                "st.",
            ],
        )

    def test_chunk_text_long(self):
        text = "This is a test. " * 64  # len(text) * 64 = 1024
        size = 1024
        result = list(chunk_text(text, size))
        self.assertEqual(len(result[0]), size)


class TestTruncateText(unittest.TestCase):
    def test_truncate_short_text(self):
        """Text under max_length should be returned unchanged."""
        text = "Hello, world!"
        result = truncate_text(text, 100)
        self.assertEqual(result, "Hello, world!")

    def test_truncate_exact_length(self):
        """Text exactly at max_length should be returned unchanged."""
        text = "12345"
        result = truncate_text(text, 5)
        self.assertEqual(result, "12345")

    def test_truncate_long_text(self):
        """Text over max_length should be truncated with suffix."""
        text = "This is a very long string that needs truncation"
        result = truncate_text(text, 10)
        self.assertEqual(result, "This is a ...")
        self.assertEqual(len(result), 13)  # 10 + len("...")

    def test_truncate_none(self):
        """None input should return None."""
        result = truncate_text(None, 100)
        self.assertIsNone(result)

    def test_truncate_custom_suffix(self):
        """Custom suffix should be used when truncating."""
        text = "This is a long string"
        result = truncate_text(text, 10, suffix="[...]")
        self.assertEqual(result, "This is a [...]")

    def test_truncate_empty_suffix(self):
        """Empty suffix should truncate without adding anything."""
        text = "Hello, world!"
        result = truncate_text(text, 5, suffix="")
        self.assertEqual(result, "Hello")

    def test_truncate_embed_prompt_limit(self):
        """Test with actual embed prompt limit (2000 chars)."""
        long_prompt = "x" * 2500
        result = truncate_text(long_prompt, 2000)
        self.assertEqual(len(result), 2003)  # 2000 + len("...")
        self.assertTrue(result.endswith("..."))

    def test_truncate_embed_response_limit(self):
        """Test with actual embed response limit (3500 chars)."""
        long_response = "y" * 4000
        result = truncate_text(long_response, 3500)
        self.assertEqual(len(result), 3503)  # 3500 + len("...")
        self.assertTrue(result.endswith("..."))


class TestExtractUrls(unittest.TestCase):
    def test_extract_urls(self):
        text = (
            "Check out https://www.example.com and http://example.org/?page=1&param=1"
        )
        result = extract_urls(text)
        self.assertEqual(
            result, ["https://www.example.com", "http://example.org/?page=1&param=1"]
        )


class TestFormatOpenAIError(unittest.TestCase):
    def test_format_openai_error_api_error(self):
        class DummyStatusError(APIError):
            def __init__(self, response_body):
                request = type(
                    "Request",
                    (),
                    {"method": "POST", "url": "https://api.example.com/test"},
                )()
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
        self.assertEqual(formatted, expected)

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
        self.assertEqual(formatted, expected)


if __name__ == "__main__":
    unittest.main()
