from datetime import date
from typing import Any, TypeAlias

from discord import Member, Message, User

from ...config.auth import SHOW_COST_EMBEDS
from ...util import ResponseParameters, calculate_cost, calculate_tool_cost
from .embeds import append_pricing_embed
from .responses import get_usage
from .tooling import ToolInfo, resolve_selected_tools
from .views import ButtonView

ConversationStore: TypeAlias = dict[int, ResponseParameters]
ViewStore: TypeAlias = dict[Member | User, ButtonView]
ViewMessageStore: TypeAlias = dict[Member | User, Message]
DailyCostStore: TypeAlias = dict[tuple[int, str], float]


async def strip_previous_view(cog, user) -> None:
    """Edit the last message that had buttons to remove its view."""
    prev = cog.last_view_messages.pop(user, None)
    if prev is not None:
        try:
            await prev.edit(view=None)
        except Exception as e:
            cog.logger.debug(f"Could not edit previous message: {e}")


async def cleanup_conversation(cog, user) -> None:
    """Remove button view from the last message and clean up view state."""
    await strip_previous_view(cog, user)
    cog.views.pop(user, None)


async def stop_conversation(cog, conversation_id: int, user) -> None:
    """Stop callback for ButtonView: delete conversation and clean up."""
    cog.conversation_histories.pop(conversation_id, None)
    await cleanup_conversation(cog, user)


def create_button_view(cog, user, conversation_id: int, tools=None) -> ButtonView:
    """Create a ButtonView wired to the cog's callbacks."""
    return ButtonView(
        conversation_starter=user,
        conversation_id=conversation_id,
        initial_tools=tools,
        get_conversation=lambda cid: cog.conversation_histories.get(cid),
        on_regenerate=cog.handle_new_message_in_conversation,
        on_stop=cog._stop_conversation,
        on_tools_changed=lambda selected_values, conversation: handle_tools_changed(
            cog, selected_values, conversation
        ),
    )


def handle_tools_changed(
    cog,
    selected_values: list[str],
    conversation,
) -> tuple[set[str], str | None]:
    """Resolve tools, update conversation state, and return active names."""
    tools, error = resolve_selected_tools(selected_values, conversation.model)
    if error:
        return set(), error
    conversation.tools = tools
    active_names = {tool["type"] for tool in tools if isinstance(tool, dict)}
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
    cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens)
    tool_cost = 0.0
    if tool_call_counts:
        tool_cost = calculate_tool_cost(tool_call_counts)
        cost += tool_cost
    key = (user_id, date.today().isoformat())
    cog.daily_costs[key] = cog.daily_costs.get(key, 0.0) + cost
    cog.logger.info(
        f"COST | command={command} | user={user_id} | model={model}"
        f" | input_tokens={input_tokens} | output_tokens={output_tokens}"
        f" | cached_tokens={cached_tokens}"
        + (f" | tools={tool_call_counts} | tool_cost=${tool_cost:.4f}" if tool_call_counts else "")
        + f" | cost=${cost:.4f} | daily=${cog.daily_costs[key]:.4f}"
    )
    return cog.daily_costs[key]


def track_daily_cost_direct(
    cog,
    user_id: int,
    command: str,
    model: str,
    cost: float,
    details: str = "",
) -> float:
    """Track a pre-computed cost and return the new daily total."""
    key = (user_id, date.today().isoformat())
    cog.daily_costs[key] = cog.daily_costs.get(key, 0.0) + cost
    cog.logger.info(
        f"COST | command={command} | user={user_id} | model={model}"
        f" | cost=${cost:.4f} | daily=${cog.daily_costs[key]:.4f}"
        + (f" | {details}" if details else "")
    )
    return cog.daily_costs[key]


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
    "handle_tools_changed",
    "stop_conversation",
    "strip_previous_view",
    "track_and_append_cost",
    "track_daily_cost",
    "track_daily_cost_direct",
]
