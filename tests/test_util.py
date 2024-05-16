import unittest
from util import (
    ChatCompletionParameters,
)  # adjust import according to your project structure


class TestChatCompletionParameters(unittest.TestCase):
    def test_to_dict_basic(self):
        """Test to_dict with basic input."""
        params = ChatCompletionParameters(
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "System message"}],
                },
                {"role": "user", "content": [{"type": "text", "text": "User query"}]},
            ],
            model="gpt-4o",
        )
        result = params.to_dict()
        self.assertIn("messages", result)
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][0]["content"][0]["text"], "System message")
        self.assertEqual(result["model"], "gpt-4o")

    def test_to_dict_with_attachment(self):
        """Test to_dict with an attachment included."""
        params = ChatCompletionParameters(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Check out this image:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "http://example.com/image.png"},
                        },
                    ],
                }
            ],
            model="gpt-4o",
        )
        result = params.to_dict()
        self.assertEqual(
            result["messages"][0]["content"][1]["image_url"]["url"],
            "http://example.com/image.png",
        )

    def test_to_dict_with_advanced_parameters(self):
        """Test to_dict including advanced configuration parameters."""
        params = ChatCompletionParameters(
            messages=[
                {"role": "user", "content": [{"type": "text", "text": "Hello, world!"}]}
            ],
            model="gpt-4o",
            frequency_penalty=0.5,
            presence_penalty=0.5,
            temperature=0.7,
            top_p=0.9,
        )
        result = params.to_dict()
        self.assertEqual(result["frequency_penalty"], 0.5)
        self.assertEqual(result["presence_penalty"], 0.5)
        self.assertEqual(result["temperature"], 0.7)
        self.assertEqual(result["top_p"], 0.9)
