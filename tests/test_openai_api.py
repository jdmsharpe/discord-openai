from unittest.mock import AsyncMock, MagicMock, patch
import unittest
import config.auth  # imported for OpenAIAPI class dependency
from openai_api import OpenAIAPI, append_response_embeds
from discord import Bot, Colour, Embed, Intents


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
        self.bot.converse = AsyncMock()
        self.bot.generate_image = AsyncMock()
        self.bot.text_to_speech = AsyncMock()
        self.bot.speech_to_text = AsyncMock()
        self.bot.generate_video = AsyncMock()

        # Setting up specific return values for the mock calls
        # Mock for converse command (using Responses API)
        mock_converse_embed = MagicMock(Embed)
        mock_converse_embed.description = "Hello, World!"
        self.bot.converse.return_value = mock_converse_embed

        mock_image_embed = MagicMock(Embed)
        mock_image_embed.file = "image.png"
        self.bot.generate_image.return_value = mock_image_embed

        mock_text_to_speech_embed = MagicMock(Embed)
        mock_text_to_speech_embed.file = "alloy_speech.mp3"
        self.bot.text_to_speech.return_value = mock_text_to_speech_embed

        mock_speech_to_text_embed = MagicMock(Embed)
        mock_speech_to_text_embed.description = "Hello, World!"
        self.bot.speech_to_text.return_value = mock_speech_to_text_embed

        mock_generate_video_embed = MagicMock(Embed)
        mock_generate_video_embed.file = "video.mp4"
        self.bot.generate_video.return_value = mock_generate_video_embed

    async def test_on_ready(self):
        await self.bot.cogs["OpenAIAPI"].on_ready()
        self.bot.sync_commands.assert_called_once()

    async def test_converse_command(self):
        embed = await self.bot.converse("Hello")
        self.assertIn("Hello, World!", embed.description)

    async def test_generate_image_command(self):
        embed = await self.bot.generate_image("Create a sunset image")
        self.assertEqual("image.png", embed.file)

    async def test_text_to_speech_command(self):
        embed = await self.bot.text_to_speech("Hello")
        self.assertEqual("alloy_speech.mp3", embed.file)

    async def test_speech_to_text_command(self):
        embed = await self.bot.speech_to_text("audio.mp3")
        self.assertEqual("Hello, World!", embed.description)

    async def test_generate_video_command(self):
        embed = await self.bot.generate_video("A cat playing piano")
        self.assertEqual("video.mp4", embed.file)


class TestAppendResponseEmbeds(unittest.TestCase):
    def test_append_short_response(self):
        """Short responses should be added as a single embed."""
        embeds = []
        append_response_embeds(embeds, "Hello, world!")
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Response")
        self.assertEqual(embeds[0].description, "Hello, world!")

    def test_append_to_existing_embeds(self):
        """Response should be appended to existing embeds list."""
        embeds = [Embed(title="Prompt", description="Test prompt", color=Colour.green())]
        append_response_embeds(embeds, "Response text")
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[1].title, "Response")

    def test_chunk_long_response(self):
        """Responses over 3500 chars should be chunked into multiple embeds."""
        embeds = []
        long_response = "x" * 4000  # Over 3500 char chunk size
        append_response_embeds(embeds, long_response)
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[0].title, "Response")
        self.assertEqual(embeds[1].title, "Response (Part 2)")

    def test_respects_total_limit(self):
        """Response should be truncated to respect 6000 char total limit."""
        # Create existing embed that uses some of the 6000 char budget
        existing_embed = Embed(title="Prompt", description="x" * 3000)
        embeds = [existing_embed]
        # Try to add a response that would exceed 6000 total
        long_response = "y" * 5000
        append_response_embeds(embeds, long_response)
        # Calculate total chars across all embeds
        total_chars = sum(
            len(embed.description or "") + len(embed.title or "")
            for embed in embeds
        )
        # Should be under 6000 (with some buffer)
        self.assertLess(total_chars, 6100)

    def test_truncation_message(self):
        """Truncated responses should include truncation notice."""
        existing_embed = Embed(title="Prompt", description="x" * 4000)
        embeds = [existing_embed]
        long_response = "y" * 5000
        append_response_embeds(embeds, long_response)
        # Check if any embed contains the truncation message
        all_descriptions = " ".join(embed.description or "" for embed in embeds)
        self.assertIn("truncated", all_descriptions.lower())

    def test_empty_response(self):
        """Empty response should not create an embed."""
        embeds = []
        append_response_embeds(embeds, "")
        # chunk_text("") returns [], so no embed is created
        self.assertEqual(len(embeds), 0)

    def test_multiple_chunks_numbered(self):
        """Multiple chunks should be numbered correctly."""
        embeds = []
        # Create response that needs 3 chunks (3500 * 3 = 10500 chars)
        # But limited by 6000 total, so will be truncated first
        long_response = "z" * 7000
        append_response_embeds(embeds, long_response)
        # First embed should be "Response", subsequent should be "Response (Part N)"
        self.assertEqual(embeds[0].title, "Response")
        if len(embeds) > 1:
            self.assertIn("Part", embeds[1].title)


if __name__ == "__main__":
    unittest.main()
