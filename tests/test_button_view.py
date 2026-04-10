from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ui import Button, Select

from discord_openai.cogs.openai.tool_registry import TOOL_REGISTRY
from discord_openai.cogs.openai.tooling import (
    TOOL_CODE_INTERPRETER,
    TOOL_FILE_SEARCH,
    TOOL_SHELL,
    TOOL_WEB_SEARCH,
)
from discord_openai.cogs.openai.views import ButtonView, McpApprovalView


def _make_button_view(*, get_conversation=None, initial_tools=None, on_tools_changed=None):
    return ButtonView(
        conversation_starter_id=123,
        conversation_id=42,
        initial_tools=initial_tools,
        get_conversation=get_conversation or MagicMock(return_value=None),
        on_regenerate=AsyncMock(),
        on_stop=AsyncMock(),
        on_tools_changed=on_tools_changed or MagicMock(return_value=(set(), None)),
    )


def _make_approval_view(*, get_conversation=None, on_approve=None, on_deny=None):
    return McpApprovalView(
        conversation_starter_id=123,
        conversation_id=42,
        get_conversation=get_conversation or MagicMock(return_value=None),
        on_approve=on_approve or AsyncMock(),
        on_deny=on_deny or AsyncMock(),
        on_stop=AsyncMock(),
    )


def test_button_view_init_without_running_event_loop():
    view = _make_button_view()
    selects = [component for component in view.children if isinstance(component, Select)]
    assert len(selects) == 1
    assert selects[0].min_values == 0
    assert selects[0].max_values == len(TOOL_REGISTRY)


def test_mcp_approval_view_init_without_running_event_loop():
    view = _make_approval_view()
    buttons = [component for component in view.children if isinstance(component, Button)]
    assert len(buttons) == 3


class TestButtonView:
    @pytest.mark.asyncio
    async def test_tool_select_exists(self):
        view = _make_button_view()
        selects = [component for component in view.children if isinstance(component, Select)]
        assert len(selects) == 1
        assert selects[0].min_values == 0
        assert selects[0].max_values == len(TOOL_REGISTRY)

    @pytest.mark.asyncio
    async def test_tool_select_initial_defaults(self):
        view = _make_button_view(
            initial_tools=[
                TOOL_WEB_SEARCH,
                TOOL_CODE_INTERPRETER,
                TOOL_FILE_SEARCH,
                TOOL_SHELL,
            ]
        )
        tool_select = next(
            component for component in view.children if isinstance(component, Select)
        )
        option_defaults = {option.value: option.default for option in tool_select.options}
        assert option_defaults["web_search"] is True
        assert option_defaults["code_interpreter"] is True
        assert option_defaults["file_search"] is True
        assert option_defaults["shell"] is True

    @pytest.mark.asyncio
    async def test_tool_select_callback_updates_defaults(self):
        conversation = SimpleNamespace()
        active_names = {"web_search", "code_interpreter"}
        on_tools_changed = MagicMock(return_value=(active_names, None))
        view = _make_button_view(
            get_conversation=MagicMock(return_value=conversation),
            on_tools_changed=on_tools_changed,
        )
        tool_select = next(
            component for component in view.children if isinstance(component, Select)
        )

        selected = MagicMock()
        selected.values = ["web_search", "code_interpreter"]

        interaction = MagicMock()
        interaction.user.id = 123
        interaction.response.send_message = AsyncMock()

        await view.tool_select_callback(interaction, selected)

        option_defaults = {option.value: option.default for option in tool_select.options}
        assert option_defaults["web_search"] is True
        assert option_defaults["code_interpreter"] is True
        assert option_defaults["file_search"] is False
        assert option_defaults["shell"] is False
        on_tools_changed.assert_called_once_with(["web_search", "code_interpreter"], conversation)
        interaction.response.send_message.assert_awaited_once()


class TestMcpApprovalView:
    @pytest.mark.asyncio
    async def test_non_owner_cannot_approve(self):
        conversation = SimpleNamespace(pending_mcp_approval={"approval_request_id": "mcpr_1"})
        view = _make_approval_view(get_conversation=MagicMock(return_value=conversation))
        approve_button = next(
            component
            for component in view.children
            if isinstance(component, Button) and component.label == "Approve MCP"
        )

        interaction = MagicMock()
        interaction.user.id = 999
        interaction.response.send_message = AsyncMock()

        await approve_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_owner_can_approve_pending_request(self):
        conversation = SimpleNamespace(pending_mcp_approval={"approval_request_id": "mcpr_1"})
        on_approve = AsyncMock()
        view = _make_approval_view(
            get_conversation=MagicMock(return_value=conversation),
            on_approve=on_approve,
        )
        approve_button = next(
            component
            for component in view.children
            if isinstance(component, Button) and component.label == "Approve MCP"
        )

        interaction = MagicMock()
        interaction.user.id = 123
        interaction.response.defer = AsyncMock()

        await approve_button.callback(interaction)

        interaction.response.defer.assert_awaited_once()
        on_approve.assert_awaited_once_with(interaction, conversation)
