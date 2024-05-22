from button_view import ButtonView
import unittest
from unittest.mock import AsyncMock, MagicMock


class TestOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cog = AsyncMock()
        self.conversation_starter = MagicMock()
        self.conversation_id = MagicMock()
        self.view = ButtonView(
            self.cog, self.conversation_starter, self.conversation_id
        )
        self.view.regenerate_button = AsyncMock()
        self.view.play_pause_button = AsyncMock()
        self.view.stop_button = AsyncMock()

    async def test_init(self):
        self.assertEqual(self.view.cog, self.cog)
        self.assertEqual(self.view.conversation_starter, self.conversation_starter)
        self.assertEqual(self.view.conversation_id, self.conversation_id)

    async def test_regenerate_button(self):
        await self.view.regenerate_button(None, None)
        self.view.regenerate_button.assert_called()

    async def test_play_pause_button(self):
        await self.view.play_pause_button(None, None)
        self.view.play_pause_button.assert_called()

    async def test_stop_button(self):
        await self.view.stop_button(None, None)
        self.view.stop_button.assert_called()


if __name__ == "__main__":
    unittest.main()
