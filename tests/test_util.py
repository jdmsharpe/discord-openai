import unittest
from util import (
    ChatCompletionParameters,
    ImageGenerationParameters,
    TextToSpeechParameters,
    chunk_text,
    extract_urls,
)


class TestChatCompletionParameters(unittest.TestCase):
    def test_to_dict(self):
        params = ChatCompletionParameters(
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
            model="chatgpt-4o-latest",
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
        self.assertEqual(result["model"], "chatgpt-4o-latest")
        self.assertEqual(result["frequency_penalty"], 0.5)
        self.assertEqual(result["presence_penalty"], 0.5)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["temperature"], 0.8)
        self.assertEqual(result["top_p"], 0.9)


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


if __name__ == "__main__":
    unittest.main()
