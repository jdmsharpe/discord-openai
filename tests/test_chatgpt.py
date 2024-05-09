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

    async def test_chat_command_with_personality(self):
        embed = await self.bot.chat("Hello", personality="You are a friendly assistant.")
        self.assertIn("Hello, World!", embed.description)
        self.assertEqual("You are a friendly assistant.", embed.fields[0].value)

    async def test_chat_command_with_model(self):
        embed = await self.bot.chat("Hello", model="gpt-3.5-turbo-0125")
        self.assertIn("Hello, World!", embed.description)
        self.assertEqual("gpt-3.5-turbo-0125", embed.fields[1].value)

    async def test_chat_command_with_message_history(self):
        message_history = '[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]'
        embed = await self.bot.chat("How are you?", message_history=message_history)
        self.assertIn("Hello, World!", embed.description)
        self.assertEqual(message_history, embed.fields[2].value)

    async def test_generate_image_command_with_model(self):
        embed = await self.bot.generate_image("Create a sunset image", model="dall-e-2")
        self.assertEqual("image.png", embed.file)
        self.assertEqual("dall-e-2", embed.fields[0].value)

    async def test_generate_image_command_with_n(self):
        embed = await self.bot.generate_image("Create a sunset image", n=3)
        self.assertEqual("image.png", embed.file)
        self.assertEqual(3, embed.fields[1].value)

    async def test_text_to_speech_command_with_model(self):
        embed = await self.bot.text_to_speech("Hello", model="tts-1-hd")
        self.assertEqual("tts-1-hd", embed.fields[0].value)
        self.assertEqual("mp3", embed.fields[1].value)

    async def test_text_to_speech_command_with_voice(self):
        embed = await self.bot.text_to_speech("Hello", voice="echo")
        self.assertEqual("echo", embed.fields[2].value)
        self.assertEqual("mp3", embed.fields[1].value)

if __name__ == "__main__":
    unittest.main()
