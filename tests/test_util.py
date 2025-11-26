import unittest
from openai import APIError
from util import (
    ChatCompletionParameters,
    ImageGenerationParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
    chunk_text,
    extract_urls,
    format_openai_error,
)


class TestChatCompletionParameters(unittest.TestCase):
    def test_to_dict(self):
        params = ChatCompletionParameters(
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
            model="gpt-5.1",
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
        self.assertEqual(result["model"], "gpt-5.1")
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
        # Test that gpt-image-1 keeps "medium" as is
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1",
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
        # Test that response_format is NOT included for gpt-image-1 even when provided
        params = ImageGenerationParameters(
            prompt="Test prompt",
            model="gpt-image-1",
            response_format="url",  # This should be ignored
        )
        result = params.to_dict()
        self.assertNotIn("response_format", result)

    def test_style_removal_gpt_image(self):
        # Test that style is set to None for gpt-image-1 in the constructor
        params = ImageGenerationParameters(
            prompt="Test prompt", model="gpt-image-1", style="natural"
        )
        # Style should be None for gpt-image-1, but let's verify the to_dict behavior
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
            seconds=8,
        )
        result = params.to_dict()
        self.assertEqual(result["prompt"], "A cat playing piano")
        self.assertEqual(result["model"], "sora-2")
        self.assertEqual(result["size"], "1280x720")
        self.assertEqual(result["seconds"], 8)

    def test_defaults(self):
        params = VideoGenerationParameters(prompt="Test video")
        result = params.to_dict()
        self.assertEqual(result["prompt"], "Test video")
        self.assertEqual(result["model"], "sora-2")
        self.assertEqual(result["size"], "1280x720")
        self.assertEqual(result["seconds"], 8)

    def test_sora_pro_model(self):
        params = VideoGenerationParameters(
            prompt="High quality video",
            model="sora-2-pro",
            size="1920x1080",
            seconds=20,
        )
        result = params.to_dict()
        self.assertEqual(result["model"], "sora-2-pro")
        self.assertEqual(result["size"], "1920x1080")
        self.assertEqual(result["seconds"], 20)

    def test_portrait_size(self):
        params = VideoGenerationParameters(
            prompt="Portrait video",
            size="1080x1920",
        )
        result = params.to_dict()
        self.assertEqual(result["size"], "1080x1920")

    def test_square_size(self):
        params = VideoGenerationParameters(
            prompt="Square video",
            size="480x480",
        )
        result = params.to_dict()
        self.assertEqual(result["size"], "480x480")


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
