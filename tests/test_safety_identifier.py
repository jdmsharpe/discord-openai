"""The keyed safety identifier reaches every request body that accepts one."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discord_openai.cogs.openai.chat import (
    handle_mcp_approval_action,
    handle_new_message_in_conversation,
    run_chat_command,
)
from discord_openai.cogs.openai.image import run_image_command
from discord_openai.cogs.openai.research import run_research_command
from discord_openai.util import ResponseParameters

USER_ID = 987654321098765432
KEY = b"test-safety-identifier-secret"
EXPECTED_IDENTIFIER = hmac.new(KEY, str(USER_ID).encode(), hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _fixed_key(monkeypatch):
    monkeypatch.setattr("discord_openai.util.SAFETY_IDENTIFIER_KEY", KEY)


def _ctx():
    return SimpleNamespace(
        author=SimpleNamespace(id=USER_ID),
        channel_id=456,
        interaction=SimpleNamespace(id=789),
        defer=AsyncMock(),
        send_followup=AsyncMock(return_value=MagicMock()),
    )


def _assert_body_carries_identifier_only(body: dict, field: str) -> None:
    assert body[field] == EXPECTED_IDENTIFIER
    serialized = json.dumps(body, default=repr)
    assert str(USER_ID) not in serialized
    assert format(USER_ID, "x") not in serialized


def _chat_cog(create):
    return SimpleNamespace(
        conversation_histories={},
        views={},
        last_view_messages={},
        daily_costs={},
        logger=MagicMock(),
        openai_client=SimpleNamespace(responses=SimpleNamespace(create=create)),
        resolve_selected_tools=MagicMock(return_value=([], None)),
        _prune_runtime_state=AsyncMock(),
        _cleanup_conversation=AsyncMock(),
        _create_mcp_approval_view=MagicMock(),
        _create_button_view=MagicMock(),
        _track_and_append_cost=MagicMock(),
    )


@pytest.mark.asyncio
async def test_chat_request_sends_keyed_safety_identifier():
    create = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_chat_command(
        _chat_cog(create),
        _ctx(),
        prompt="Hello",
        persona="You are helpful.",
        model="gpt-6-astra",
        attachment=None,
        temperature=None,
        top_p=None,
        reasoning_effort=None,
        verbosity=None,
        web_search=False,
        code_interpreter=False,
        file_search=False,
        shell=False,
        mcp=None,
    )

    _assert_body_carries_identifier_only(create.await_args.kwargs, "safety_identifier")


@pytest.mark.asyncio
async def test_chat_request_omits_safety_identifier_without_a_key(monkeypatch):
    monkeypatch.setattr("discord_openai.util.SAFETY_IDENTIFIER_KEY", None)
    create = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_chat_command(
        _chat_cog(create),
        _ctx(),
        prompt="Hello",
        persona="You are helpful.",
        model="gpt-6-astra",
        attachment=None,
        temperature=None,
        top_p=None,
        reasoning_effort=None,
        verbosity=None,
        web_search=False,
        code_interpreter=False,
        file_search=False,
        shell=False,
        mcp=None,
    )

    assert "safety_identifier" not in create.await_args.kwargs


@pytest.mark.asyncio
async def test_chat_followup_request_keeps_keyed_safety_identifier():
    conversation = ResponseParameters(
        model="gpt-6-astra",
        input=[],
        conversation_starter_id=USER_ID,
        channel_id=456,
        conversation_id=789,
        safety_identifier=EXPECTED_IDENTIFIER,
    )
    message = SimpleNamespace(
        author=SimpleNamespace(id=USER_ID),
        channel=SimpleNamespace(),
        content="and then?",
        attachments=[],
        id=111,
        reply=AsyncMock(),
    )
    create = AsyncMock(side_effect=RuntimeError("stop after request"))
    cog = SimpleNamespace(
        logger=MagicMock(),
        conversation_histories={789: conversation},
        openai_client=SimpleNamespace(responses=SimpleNamespace(create=create)),
        resolve_selected_tools=MagicMock(return_value=([], None)),
        _cleanup_conversation=AsyncMock(),
    )

    with patch("discord_openai.cogs.openai.chat.keep_typing", new=AsyncMock()):
        await handle_new_message_in_conversation(cog, message, conversation)

    body = create.await_args.kwargs
    assert body["safety_identifier"] == EXPECTED_IDENTIFIER
    # The follow-up body carries the conversation's input history, which holds no IDs.
    assert str(USER_ID) not in json.dumps(body, default=repr)


@pytest.mark.asyncio
async def test_mcp_approval_request_keeps_keyed_safety_identifier():
    conversation = ResponseParameters(
        model="gpt-6-astra",
        input=[],
        conversation_starter_id=USER_ID,
        channel_id=456,
        conversation_id=789,
        safety_identifier=EXPECTED_IDENTIFIER,
        pending_mcp_approval={
            "approval_request_id": "mcpr_1",
            "request_response_id": "resp_pending",
            "server_label": "GitHub",
            "tool_name": "create_issue",
            "arguments": "{}",
            "intro_title": "Conversation Started",
            "intro_description": "**Prompt:** hi",
            "attachment_url": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "tool_call_counts": {},
        },
    )
    create = AsyncMock(side_effect=RuntimeError("stop after request"))
    cog = SimpleNamespace(
        logger=MagicMock(),
        openai_client=SimpleNamespace(responses=SimpleNamespace(create=create)),
        resolve_selected_tools=MagicMock(return_value=([], None)),
    )
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=USER_ID),
        channel=SimpleNamespace(),
        message=MagicMock(),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    with patch("discord_openai.cogs.openai.chat.keep_typing", new=AsyncMock()):
        await handle_mcp_approval_action(cog, interaction, conversation, approve=True)

    _assert_body_carries_identifier_only(create.await_args.kwargs, "safety_identifier")


def _research_cog(create):
    return SimpleNamespace(
        logger=MagicMock(),
        openai_client=SimpleNamespace(responses=SimpleNamespace(create=create)),
        resolve_selected_tools=MagicMock(return_value=([{"type": "web_search"}], None)),
    )


@pytest.mark.asyncio
async def test_research_request_sends_keyed_safety_identifier():
    create = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_research_command(
        _research_cog(create),
        _ctx(),
        prompt="Research this",
        model="gpt-6-astra",
        file_search=False,
        code_interpreter=False,
    )

    _assert_body_carries_identifier_only(create.await_args.kwargs, "safety_identifier")


@pytest.mark.asyncio
async def test_research_request_omits_safety_identifier_without_a_key(monkeypatch):
    monkeypatch.setattr("discord_openai.util.SAFETY_IDENTIFIER_KEY", None)
    create = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_research_command(
        _research_cog(create),
        _ctx(),
        prompt="Research this",
        model="gpt-6-astra",
        file_search=False,
        code_interpreter=False,
    )

    assert "safety_identifier" not in create.await_args.kwargs


def _image_cog(generate=None, edit=None):
    return SimpleNamespace(
        logger=MagicMock(),
        openai_client=SimpleNamespace(images=SimpleNamespace(generate=generate, edit=edit)),
    )


@pytest.mark.asyncio
async def test_image_generate_request_sends_keyed_user():
    generate = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_image_command(
        _image_cog(generate=generate),
        _ctx(),
        prompt="A lighthouse",
        model="gpt-image-2.5-sunburst",
        quality="low",
        size="1024x1024",
        attachment=None,
    )

    body = generate.await_args.kwargs
    _assert_body_carries_identifier_only(body, "user")
    assert "safety_identifier" not in body


@pytest.mark.asyncio
async def test_image_edit_request_sends_keyed_user():
    edit = AsyncMock(side_effect=RuntimeError("stop after request"))
    attachment = SimpleNamespace(
        url="https://cdn.example/source.png",
        filename="source.png",
        content_type="image/png",
    )

    with patch(
        "discord_openai.cogs.openai.image.fetch_attachment_bytes",
        new=AsyncMock(return_value=b"\x89PNG\r\n\x1a\n"),
    ):
        await run_image_command(
            _image_cog(edit=edit),
            _ctx(),
            prompt="Make it blue",
            model="gpt-image-2.5-sunburst",
            quality="low",
            size="1024x1024",
            attachment=attachment,
        )

    body = edit.await_args.kwargs
    _assert_body_carries_identifier_only(body, "user")
    assert "safety_identifier" not in body


@pytest.mark.asyncio
async def test_image_request_omits_user_without_a_key(monkeypatch):
    monkeypatch.setattr("discord_openai.util.SAFETY_IDENTIFIER_KEY", None)
    generate = AsyncMock(side_effect=RuntimeError("stop after request"))

    await run_image_command(
        _image_cog(generate=generate),
        _ctx(),
        prompt="A lighthouse",
        model="gpt-image-2.5-sunburst",
        quality="low",
        size="1024x1024",
        attachment=None,
    )

    assert "user" not in generate.await_args.kwargs
