from datetime import date, datetime, timedelta, timezone
from typing import Any, TypeAlias

from discord import Member, Message, User

from ...config.auth import SHOW_COST_EMBEDS
from ...util import ResponseParameters, calculate_cost, calculate_tool_cost
from .embeds import append_pricing_embed
from .responses import get_usage
from .tooling import ToolInfo, resolve_selected_tools
from .views import ButtonView, McpApprovalView

UserId: TypeAlias = int
ConversationId: TypeAlias = int
ConversationStore: TypeAlias = dict[ConversationId, ResponseParameters]
ViewStore: TypeAlias = dict[ConversationId, tuple[UserId, ButtonView | McpApprovalView, datetime]]
ViewMessageStore: TypeAlias = dict[ConversationId, tuple[UserId, Message, datetime]]
DailyCostStore: TypeAlias = dict[tuple[UserId, str], tuple[float, datetime]]

MAX_ACTIVE_CONVERSATIONS = 100
MAX_VIEW_STATES = 200
CONVERSATION_TTL = timedelta(hours=12)
VIEW_STATE_TTL = timedelta(hours=12)
DAILY_COST_RETENTION_DAYS = 30


def _user_state_key(user_or_id: Member | User | int) -> int:
    return user_or_id if isinstance(user_or_id, int) else user_or_id.id


def _conversation_timestamp(conversation: ResponseParameters) -> datetime:
    updated_at = conversation.updated_at
    if updated_at.tzinfo is None:
        return updated_at.replace(tzinfo=timezone.utc)
    return updated_at


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_daily_total(value: float | tuple[float, datetime]) -> float:
    return value[0] if isinstance(value, tuple) else value


def remember_view_state(
    cog,
    user_or_id: Member | User | int,
    conversation_id: ConversationId,
    view: ButtonView | McpApprovalView,
    message: Message,
) -> None:
    """Store interactive view/message state by stable conversation and user IDs."""
    user_id = _user_state_key(user_or_id)
    now = _now_utc()
    cog.views[conversation_id] = (user_id, view, now)
    cog.last_view_messages[conversation_id] = (user_id, message, now)


async def strip_previous_view(cog, conversation_id: ConversationId) -> None:
    """Edit the previous message for a conversation to remove its view."""
    message_state = cog.last_view_messages.pop(conversation_id, None)
    if message_state is None:
        return

    _, prev_message, _ = message_state
    try:
        await prev_message.edit(view=None)
    except Exception as e:
        cog.logger.debug(f"Could not edit previous message: {e}")


def prune_daily_costs(cog) -> None:
    """Discard daily cost entries older than DAILY_COST_RETENTION_DAYS days."""
    cutoff = date.today() - timedelta(days=DAILY_COST_RETENTION_DAYS)
    expired_keys = [key for key in cog.daily_costs if date.fromisoformat(key[1]) < cutoff]
    for key in expired_keys:
        cog.daily_costs.pop(key, None)


async def _drop_conversation_view_state(cog, conversation_id: ConversationId) -> None:
    await strip_previous_view(cog, conversation_id)
    cog.views.pop(conversation_id, None)


async def prune_runtime_state(cog) -> None:
    """Prune stale conversations, stale view state, and aged daily-cost entries."""
    now = _now_utc()
    stale_conversation_ids = [
        conversation_id
        for conversation_id, conversation in cog.conversation_histories.items()
        if now - _conversation_timestamp(conversation) > CONVERSATION_TTL
    ]

    active_conversations = [
        (conversation_id, conversation)
        for conversation_id, conversation in cog.conversation_histories.items()
        if conversation_id not in stale_conversation_ids
    ]
    overflow = len(active_conversations) - MAX_ACTIVE_CONVERSATIONS
    if overflow > 0:
        active_conversations.sort(key=lambda item: _conversation_timestamp(item[1]))
        stale_conversation_ids.extend(
            conversation_id for conversation_id, _ in active_conversations[:overflow]
        )

    for conversation_id in dict.fromkeys(stale_conversation_ids):
        cog.conversation_histories.pop(conversation_id, None)

    tracked_conversation_ids = set(cog.views) | set(cog.last_view_messages)
    stale_view_conversation_ids = []
    for conversation_id in tracked_conversation_ids:
        if conversation_id not in cog.conversation_histories:
            stale_view_conversation_ids.append(conversation_id)
            continue
        message_state = cog.last_view_messages.get(conversation_id)
        if message_state and now - message_state[2] > VIEW_STATE_TTL:
            stale_view_conversation_ids.append(conversation_id)

    for conversation_id in dict.fromkeys(stale_view_conversation_ids):
        await _drop_conversation_view_state(cog, conversation_id)

    overflow_view_states = len(cog.views) - MAX_VIEW_STATES
    if overflow_view_states > 0:
        sorted_view_ids = sorted(
            cog.views,
            key=lambda conversation_id: cog.views[conversation_id][2],
        )
        for conversation_id in sorted_view_ids[:overflow_view_states]:
            await _drop_conversation_view_state(cog, conversation_id)

    prune_daily_costs(cog)


async def cleanup_conversation(
    cog,
    user_or_id: Member | User | int,
    conversation_id: int | None = None,
) -> None:
    """Remove view state and optionally drop conversations from history."""
    user_id = _user_state_key(user_or_id)
    if conversation_id is not None:
        cog.conversation_histories.pop(conversation_id, None)
        await _drop_conversation_view_state(cog, conversation_id)
    else:
        matching_conversation_ids = [
            convo_id
            for convo_id, (stored_user_id, _, _) in cog.views.items()
            if stored_user_id == user_id
        ]
        for convo_id in matching_conversation_ids:
            await _drop_conversation_view_state(cog, convo_id)
    await prune_runtime_state(cog)


async def stop_conversation(
    cog,
    conversation_id: int,
    user_or_id: Member | User | int,
) -> None:
    """Stop callback for ButtonView: delete conversation and clean up."""
    await cleanup_conversation(cog, user_or_id, conversation_id)


def create_button_view(
    cog,
    user_or_id: Member | User | int,
    conversation_id: int,
    tools=None,
) -> ButtonView:
    """Create a ButtonView wired to the cog's callbacks."""
    return ButtonView(
        conversation_starter_id=_user_state_key(user_or_id),
        conversation_id=conversation_id,
        initial_tools=tools,
        get_conversation=lambda cid: cog.conversation_histories.get(cid),
        on_regenerate=cog.regenerate_conversation_response,
        on_stop=cog._stop_conversation,
        on_tools_changed=lambda selected_values, conversation: handle_tools_changed(
            cog, selected_values, conversation
        ),
    )


def create_mcp_approval_view(
    cog,
    user_or_id: Member | User | int,
    conversation_id: int,
) -> McpApprovalView:
    """Create the approval-only view used while an MCP approval request is pending."""
    return McpApprovalView(
        conversation_starter_id=_user_state_key(user_or_id),
        conversation_id=conversation_id,
        get_conversation=lambda cid: cog.conversation_histories.get(cid),
        on_approve=cog.handle_mcp_approval,
        on_deny=cog.handle_mcp_denial,
        on_stop=cog._stop_conversation,
    )


def handle_tools_changed(
    cog,
    selected_values: list[str],
    conversation,
) -> tuple[set[str], str | None]:
    """Resolve tools, update conversation state, and return active names."""
    tools, error = resolve_selected_tools(
        selected_values,
        conversation.model,
        mcp_preset_names=conversation.mcp_preset_names,
    )
    if error:
        return set(), error
    conversation.tool_names = list(selected_values)
    conversation.tools = tools
    conversation.touch()
    active_names = {tool["type"] for tool in tools if isinstance(tool, dict)}
    active_names -= {"mcp"}
    return active_names, None


def track_daily_cost(
    cog,
    user_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    tool_call_counts: dict[str, int] | None = None,
    command: str = "chat",
) -> float:
    """Add this request's cost to the user's daily total and return the new daily total."""
    prune_daily_costs(cog)
    cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens)
    tool_cost = 0.0
    if tool_call_counts:
        tool_cost = calculate_tool_cost(tool_call_counts)
        cost += tool_cost
    key = (user_id, date.today().isoformat())
    current_total = _extract_daily_total(cog.daily_costs.get(key, 0.0))
    new_total = current_total + cost
    cog.daily_costs[key] = (new_total, _now_utc())
    cog.logger.info(
        f"COST | command={command} | user={user_id} | model={model}"
        f" | input_tokens={input_tokens} | output_tokens={output_tokens}"
        f" | cached_tokens={cached_tokens}"
        + (f" | tools={tool_call_counts} | tool_cost=${tool_cost:.4f}" if tool_call_counts else "")
        + f" | cost=${cost:.4f} | daily=${new_total:.4f}"
    )
    return new_total


def track_daily_cost_direct(
    cog,
    user_id: int,
    command: str,
    model: str,
    cost: float,
    details: str = "",
) -> float:
    """Track a pre-computed cost and return the new daily total."""
    prune_daily_costs(cog)
    key = (user_id, date.today().isoformat())
    current_total = _extract_daily_total(cog.daily_costs.get(key, 0.0))
    new_total = current_total + cost
    cog.daily_costs[key] = (new_total, _now_utc())
    cog.logger.info(
        f"COST | command={command} | user={user_id} | model={model}"
        f" | cost=${cost:.4f} | daily=${new_total:.4f}" + (f" | {details}" if details else "")
    )
    return new_total


def track_and_append_cost(
    cog,
    embeds: list,
    user_id: int,
    model: str,
    response: Any,
    tool_info: ToolInfo,
    command: str = "chat",
) -> None:
    """Extract usage, track daily cost, and append a pricing embed."""
    usage = get_usage(response)
    tool_call_counts = tool_info["tool_call_counts"] or None
    daily_cost = track_daily_cost(
        cog,
        user_id,
        model,
        usage["input_tokens"],
        usage["output_tokens"],
        usage["cached_tokens"],
        tool_call_counts,
        command=command,
    )
    if SHOW_COST_EMBEDS:
        append_pricing_embed(
            embeds,
            model,
            usage["input_tokens"],
            usage["output_tokens"],
            daily_cost,
            usage["cached_tokens"],
            usage["reasoning_tokens"],
            tool_call_counts,
        )


__all__ = [
    "ConversationStore",
    "DailyCostStore",
    "ViewMessageStore",
    "ViewStore",
    "cleanup_conversation",
    "create_button_view",
    "create_mcp_approval_view",
    "handle_tools_changed",
    "prune_daily_costs",
    "prune_runtime_state",
    "remember_view_state",
    "stop_conversation",
    "strip_previous_view",
    "track_and_append_cost",
    "track_daily_cost",
    "track_daily_cost_direct",
]
