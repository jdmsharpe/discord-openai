import unittest
from unittest.mock import AsyncMock, patch
import config.auth
from chatgpt import ChatGPT
from discord import Bot


class TestChatGPT(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot()
        self.cog = ChatGPT(self.bot)
        self.bot.add_cog(self.cog)
        self.ctx = AsyncMock()  # Mocking the context

    @patch("openai.chat.completions.create")
    async def test_chat_command(self, mock_openai):
        # Setup
        mock_openai.return_value = {
            "choices": [{"message": {"content": "Hello, World!"}}]
        }
        self.ctx.interaction = AsyncMock()

        # Execute
        await self.cog.chat(self.ctx, "Hello", "GPT-4 Turbo")

        # Verify
        self.ctx.followup.send.assert_awaited_once()
        _, kwargs = self.ctx.followup.send.call_args
        self.assertIn("Hello, World!", kwargs["embed"].description)

    @patch("openai.images.generate")
    async def test_generate_image_command(self, mock_openai):
        # Setup
        mock_openai.return_value = {"data": [{"url": "http://example.com/image.png"}]}
        self.ctx.interaction = AsyncMock()

        # Execute
        await self.cog.generate_image(self.ctx, "Create a landscape", "1024x1024")

        # Verify
        self.ctx.followup.send.assert_awaited_once()
        _, kwargs = self.ctx.followup.send.call_args
        self.assertIn("http://example.com/image.png", kwargs["embed"].image.url)


if __name__ == "__main__":
    unittest.main()
