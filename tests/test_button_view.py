from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ui import Select

from discord_openai.cogs.openai.views import ButtonView
from discord_openai.util import (
    TOOL_CODE_INTERPRETER,
    TOOL_FILE_SEARCH,
    TOOL_SHELL,
    TOOL_WEB_SEARCH,
)


def _make_view(conversation_starter=None, conversation_id=None, initial_tools=None):
    """Create a ButtonView with mock callbacks for testing."""
    return ButtonView(
        conversation_starter=conversation_starter or MagicMock(),
        conversation_id=conversation_id or MagicMock(),
        initial_tools=initial_tools,
        get_conversation=MagicMock(return_value=None),
        on_regenerate=AsyncMock(),
        on_stop=AsyncMock(),
        on_tools_changed=MagicMock(return_value=(set(), None)),
    )


class TestButtonView:
    @pytest.fixture(autouse=True)
    async def setup(self):
        self.conversation_starter = MagicMock()
        self.conversation_id = MagicMock()
        self.view = _make_view(self.conversation_starter, self.conversation_id)
        self.view.regenerate_button = AsyncMock()
        self.view.play_pause_button = AsyncMock()
        self.view.stop_button = AsyncMock()

    async def test_init(self):
        assert self.view.conversation_starter == self.conversation_starter
        assert self.view.conversation_id == self.conversation_id

    async def test_tool_select_exists(self):
        selects = [component for component in self.view.children if isinstance(component, Select)]
        assert len(selects) == 1
        assert selects[0].min_values == 0
        assert selects[0].max_values == 4

    async def test_tool_select_initial_defaults(self):
        view = _make_view(
            initial_tools=[
                TOOL_WEB_SEARCH,
                TOOL_CODE_INTERPRETER,
                TOOL_FILE_SEARCH,
                TOOL_SHELL,
            ],
        )
        selects = [component for component in view.children if isinstance(component, Select)]
        assert len(selects) == 1
        option_defaults = {option.value: option.default for option in selects[0].options}
        assert option_defaults["web_search"] is True
        assert option_defaults["code_interpreter"] is True
        assert option_defaults["file_search"] is True
        assert option_defaults["shell"] is True

    async def test_tool_select_updates_defaults_after_callback(self):
        """After tool_select_callback, Select option defaults reflect active tools."""
        user = MagicMock()
        conversation = MagicMock()
        active_names = {"web_search", "code_interpreter"}
        view = ButtonView(
            conversation_starter=user,
            conversation_id=42,
            initial_tools=None,
            get_conversation=MagicMock(return_value=conversation),
            on_regenerate=AsyncMock(),
            on_stop=AsyncMock(),
            on_tools_changed=MagicMock(return_value=(active_names, None)),
        )
        # Find the real Select (to check defaults after callback)
        tool_select = next(c for c in view.children if isinstance(c, Select))

        # Create a mock select whose .values returns the user's selection
        mock_select = MagicMock()
        mock_select.values = ["web_search", "code_interpreter"]

        interaction = AsyncMock()
        interaction.user = user
        interaction.response.is_done.return_value = False

        await view.tool_select_callback(interaction, mock_select)

        # Verify Select defaults were updated
        option_defaults = {opt.value: opt.default for opt in tool_select.options}
        assert option_defaults["web_search"] is True
        assert option_defaults["code_interpreter"] is True
        assert option_defaults["file_search"] is False
        assert option_defaults["shell"] is False

        # Verify the status message
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        assert "code_interpreter" in call_args[0][0]
        assert "web_search" in call_args[0][0]

    async def test_regenerate_button(self):
        await self.view.regenerate_button(None, None)
        self.view.regenerate_button.assert_called_once()

    async def test_play_pause_button(self):
        await self.view.play_pause_button(None, None)
        self.view.play_pause_button.assert_called_once()

    async def test_stop_button(self):
        await self.view.stop_button(None, None)
        self.view.stop_button.assert_called_once()
