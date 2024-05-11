from unittest.mock import AsyncMock, MagicMock, patch
import unittest
import config.auth  # imported for OpenAIAPI class dependency
from openai_api import OpenAIAPI
from discord import Bot, Embed, Intents

class TestOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setting up the bot with the OpenAIAPI cog
        intents = Intents.default()
        intents.presences = False
        intents.members = True
        intents.message_content = True
        self.bot = Bot(intents=intents)
        self.bot.add_cog(OpenAIAPI(bot=self.bot))
        self.bot.owner_id = 1234567890

        # Properly setting up mocks for the command functions and context
        self.bot.sync_commands = AsyncMock()
        self.bot.chat = AsyncMock()
        self.bot.generate_image = AsyncMock()
        self.bot.text_to_speech = AsyncMock()

        # Setting up specific return values for the mock calls
        mock_chat_embed = MagicMock(Embed)
        mock_chat_embed.description = "Hello, World!"
        self.bot.chat.return_value = mock_chat_embed

        mock_image_embed = MagicMock(Embed)
        mock_image_embed.file = "image.png"
        self.bot.generate_image.return_value = mock_image_embed

        mock_text_to_speech_embed = MagicMock(Embed)
        mock_text_to_speech_embed.file = "alloy_speech.mp3"
        self.bot.text_to_speech.return_value = mock_text_to_speech_embed

    async def test_on_ready(self):
        await self.bot.on_ready()
        self.bot.sync_commands.assert_called_once()

    async def test_chat_command(self):
        embed = await self.bot.chat("Hello")
        self.assertIn("Hello, World!", embed.description)

    async def test_generate_image_command(self):
        embed = await self.bot.generate_image("Create a sunset image")
        self.assertEqual("image.png", embed.file)

    async def test_text_to_speech_command(self):
        embed = await self.bot.text_to_speech("Hello")
        self.assertEqual("alloy_speech.mp3", embed.file)

    async def test_on_ready(self):
        await self.bot.cogs["OpenAIAPI"].on_ready()
        self.bot.sync_commands.assert_called_once()


if __name__ == "__main__":
    unittest.main()
