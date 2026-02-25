from button_view import ButtonView
import unittest
from unittest.mock import AsyncMock, MagicMock
from discord.ui import Select
from util import (
    TOOL_CODE_INTERPRETER,
    TOOL_FILE_SEARCH,
    TOOL_SHELL,
    TOOL_WEB_SEARCH,
)


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

    async def test_tool_select_exists(self):
        selects = [component for component in self.view.children if isinstance(component, Select)]
        self.assertEqual(len(selects), 1)
        self.assertEqual(selects[0].min_values, 0)
        self.assertEqual(selects[0].max_values, 4)

    async def test_tool_select_initial_defaults(self):
        view = ButtonView(
            self.cog,
            self.conversation_starter,
            self.conversation_id,
            initial_tools=[
                TOOL_WEB_SEARCH,
                TOOL_CODE_INTERPRETER,
                TOOL_FILE_SEARCH,
                TOOL_SHELL,
            ],
        )
        selects = [component for component in view.children if isinstance(component, Select)]
        self.assertEqual(len(selects), 1)
        option_defaults = {option.value: option.default for option in selects[0].options}
        self.assertTrue(option_defaults["web_search"])
        self.assertTrue(option_defaults["code_interpreter"])
        self.assertTrue(option_defaults["file_search"])
        self.assertTrue(option_defaults["shell"])

    async def test_regenerate_button(self):
        await self.view.regenerate_button(None, None)
        self.view.regenerate_button.assert_called_once()

    async def test_play_pause_button(self):
        await self.view.play_pause_button(None, None)
        self.view.play_pause_button.assert_called_once()

    async def test_stop_button(self):
        await self.view.stop_button(None, None)
        self.view.stop_button.assert_called_once()


if __name__ == "__main__":
    unittest.main()
