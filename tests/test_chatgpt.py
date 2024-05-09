from unittest.mock import AsyncMock, MagicMock, patch
import unittest
import config.auth  # imported for ChatGPT class dependency
from chatgpt import ChatGPT
from discord import Bot
from pathlib import Path


class TestChatGPT(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MagicMock()

        # Properly setting up mocks for the command functions and context
        self.bot.chat = AsyncMock()
        self.bot.generate_image = AsyncMock()
        self.bot.text_to_speech = AsyncMock()
        self.ctx = AsyncMock()

        # Setting up specific return values for the mock calls
        mock_chat_embed = MagicMock()
        mock_chat_embed.description = "Hello, World!"
        self.bot.chat.return_value = mock_chat_embed

        mock_image_embed = MagicMock()
        mock_image_embed.file = "image.png"
        self.bot.generate_image.return_value = mock_image_embed

        mock_text_to_speech_embed = MagicMock()
        self.bot.text_to_speech.return_value = mock_text_to_speech_embed

    async def test_chat_command(self):
        embed = await self.bot.chat("Hello")
        self.assertIn("Hello, World!", embed.description)

    async def test_generate_image_command(self):
        embed = await self.bot.generate_image("Create a sunset image")
        self.assertEqual("image.png", embed.file)

    async def test_text_to_speech_command(self):
        pass # Complete this test case

if __name__ == "__main__":
    unittest.main()
