from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discord_openai.cogs.openai.chat import (
    handle_mcp_approval_action,
    handle_on_message,
    run_chat_command,
)
from discord_openai.util import ResponseParameters


def _make_usage(
    *,
    input_tokens: int = 100,
    output_tokens: int = 25,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
    )


def _make_response(
    *,
    response_id: str,
    output: list[dict],
    output_text: str = "",
    usage=None,
):
    return SimpleNamespace(
        id=response_id,
        output=output,
        output_text=output_text,
        usage=usage or _make_usage(),
    )


class TestRunChatCommand:
    @pytest.mark.asyncio
    async def test_chat_command_stores_pending_mcp_approval(self):
        reply_message = MagicMock()
        approval_view = MagicMock()
        response = _make_response(
            response_id="resp_pending",
            output=[
                {
                    "type": "mcp_approval_request",
                    "id": "mcpr_1",
                    "server_label": "GitHub",
                    "name": "create_issue",
                    "arguments": "{\"title\":\"Bug\"}",
                }
            ],
        )

        cog = SimpleNamespace(
            conversation_histories={},
            views={},
            last_view_messages={},
            daily_costs={},
            logger=MagicMock(),
            openai_client=SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response))),
            resolve_selected_tools=MagicMock(
                return_value=([{"type": "web_search"}, {"type": "mcp", "server_label": "GitHub"}], None)
            ),
            _prune_runtime_state=AsyncMock(),
            _cleanup_conversation=AsyncMock(),
            _create_mcp_approval_view=MagicMock(return_value=approval_view),
            _create_button_view=MagicMock(),
            _track_daily_cost=MagicMock(return_value=1.23),
        )

        ctx = SimpleNamespace(
            author=SimpleNamespace(id=123),
            channel_id=456,
            interaction=SimpleNamespace(id=789),
            defer=AsyncMock(),
            send_followup=AsyncMock(return_value=reply_message),
        )

        await run_chat_command(
            cog,
            ctx,
            prompt="Open an issue",
            persona="You are helpful.",
            model="gpt-5.4",
            attachment=None,
            frequency_penalty=None,
            presence_penalty=None,
            temperature=None,
            top_p=None,
            reasoning_effort=None,
            verbosity=None,
            web_search=True,
            code_interpreter=False,
            file_search=False,
            shell=False,
            mcp="github",
        )

        conversation = cog.conversation_histories[789]
        assert conversation.pending_mcp_approval is not None
        assert conversation.pending_mcp_approval["approval_request_id"] == "mcpr_1"
        assert conversation.previous_response_id is None
        assert conversation.response_id_history == []
        assert conversation.mcp_preset_names == ["github"]
        ctx.send_followup.assert_awaited_once()
        assert ctx.send_followup.await_args.kwargs["view"] is approval_view
        assert cog.views[123] is approval_view
        assert cog.last_view_messages[123] is reply_message


class TestHandleOnMessage:
    @pytest.mark.asyncio
    async def test_blocks_followup_while_mcp_approval_pending(self):
        conversation = ResponseParameters(
            model="gpt-5.4",
            input=[],
            conversation_starter_id=123,
            channel_id=456,
            conversation_id=789,
            pending_mcp_approval={
                "approval_request_id": "mcpr_1",
                "request_response_id": "resp_pending",
                "server_label": "GitHub",
                "tool_name": "create_issue",
                "arguments": "{}",
                "intro_title": None,
                "intro_description": None,
                "attachment_url": None,
                "input_tokens": 10,
                "output_tokens": 5,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
                "tool_call_counts": {},
            },
        )
        message = SimpleNamespace(
            author=SimpleNamespace(id=123),
            channel=SimpleNamespace(id=456),
            reply=AsyncMock(),
        )
        cog = SimpleNamespace(
            bot=SimpleNamespace(user=SimpleNamespace(id=999)),
            conversation_histories={789: conversation},
            _prune_runtime_state=AsyncMock(),
            logger=MagicMock(),
        )

        await handle_on_message(cog, message)

        message.reply.assert_awaited_once()


class TestHandleMcpApprovalAction:
    @pytest.mark.asyncio
    async def test_approval_updates_response_chain_and_edits_message(self):
        conversation = ResponseParameters(
            model="gpt-5.4",
            input=[],
            tools=[{"type": "web_search"}],
            tool_names=["web_search"],
            mcp_preset_names=["github"],
            conversation_id=42,
            response_id_history=[],
            pending_mcp_approval={
                "approval_request_id": "mcpr_1",
                "request_response_id": "resp_pending",
                "server_label": "GitHub",
                "tool_name": "create_issue",
                "arguments": "{\"title\":\"Bug\"}",
                "intro_title": "Conversation Started",
                "intro_description": "**Prompt:** hi",
                "attachment_url": None,
                "input_tokens": 100,
                "output_tokens": 25,
                "cached_tokens": 5,
                "reasoning_tokens": 3,
                "tool_call_counts": {},
            },
        )
        final_response = _make_response(
            response_id="resp_final",
            output=[],
            output_text="Created the issue.",
            usage=_make_usage(input_tokens=20, output_tokens=10, cached_tokens=2, reasoning_tokens=1),
        )
        reply_view = MagicMock()
        message = MagicMock()
        message.edit = AsyncMock()

        cog = SimpleNamespace(
            views={},
            last_view_messages={},
            logger=MagicMock(),
            openai_client=SimpleNamespace(
                responses=SimpleNamespace(create=AsyncMock(return_value=final_response))
            ),
            resolve_selected_tools=MagicMock(
                return_value=([{"type": "web_search"}, {"type": "mcp", "server_label": "GitHub"}], None)
            ),
            _track_daily_cost=MagicMock(return_value=2.34),
            _create_button_view=MagicMock(return_value=reply_view),
            _create_mcp_approval_view=MagicMock(),
            _prune_runtime_state=AsyncMock(),
        )
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=123),
            channel=SimpleNamespace(),
            message=message,
            followup=SimpleNamespace(send=AsyncMock()),
        )

        with patch("discord_openai.cogs.openai.chat.keep_typing", new=AsyncMock()):
            await handle_mcp_approval_action(cog, interaction, conversation, approve=True)

        request_payload = cog.openai_client.responses.create.await_args.kwargs
        assert request_payload["previous_response_id"] == "resp_pending"
        assert request_payload["input"] == [
            {
                "type": "mcp_approval_response",
                "approve": True,
                "approval_request_id": "mcpr_1",
            }
        ]
        assert conversation.previous_response_id == "resp_final"
        assert conversation.response_id_history == ["resp_final"]
        assert conversation.pending_mcp_approval is None
        message.edit.assert_awaited_once()
        assert message.edit.await_args.kwargs["view"] is reply_view
        assert cog.views[123] is reply_view
        assert cog.last_view_messages[123] is message
