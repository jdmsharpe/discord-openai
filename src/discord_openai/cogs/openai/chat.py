import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from discord import ApplicationContext, Attachment, Colour, Embed, Interaction

from ...config.auth import SHOW_COST_EMBEDS
from ...config.mcp import parse_mcp_preset_names
from ...util import (
    PendingMcpApproval,
    ResponseParameters,
    UsageInfo,
    build_input_content,
    extract_usage,
    format_openai_error,
    hash_user_id,
    truncate_text,
)
from .embeds import (
    append_pricing_embed,
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
    error_embed,
)
from .models import PermissionAwareChannel
from .responses import build_reasoning_config, extract_summary_text, get_response_text
from .state import remember_view_state
from .tooling import ToolInfo, extract_tool_info


def _merge_tool_call_counts(*counts: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in counts:
        for tool_name, count in item.items():
            merged[tool_name] = merged.get(tool_name, 0) + count
    return merged


def _require_conversation_id(conversation: ResponseParameters) -> int:
    conversation_id = conversation.conversation_id
    if conversation_id is None:
        raise RuntimeError("Conversation ID is required for interactive view state.")
    return conversation_id


def _build_intro_embeds(
    title: str | None,
    description: str | None,
    attachment_url: str | None = None,
) -> list[Embed]:
    embeds: list[Embed] = []
    if title and description:
        embeds.append(
            Embed(
                title=title,
                description=description,
                color=Colour.green(),
            )
        )
    if attachment_url:
        embeds.append(
            Embed(
                title="Attachment",
                description=attachment_url,
                color=Colour.green(),
            )
        )
    return embeds


def _build_mcp_approval_embeds(
    *,
    intro_title: str | None,
    intro_description: str | None,
    attachment_url: str | None,
    pending: PendingMcpApproval,
    response: Any,
) -> list[Embed]:
    embeds = _build_intro_embeds(intro_title, intro_description, attachment_url)
    append_thinking_embeds(embeds, extract_summary_text(response))

    server_label = pending["server_label"] or "unknown server"
    tool_name = pending["tool_name"] or "unknown tool"
    arguments = pending["arguments"] or "{}"
    description = (
        f"**Server:** {server_label}\n"
        f"**Tool:** {tool_name}\n"
        f"**Arguments:**\n```json\n{truncate_text(arguments, 1200)}\n```\n"
        "Approving this will allow data from this conversation to be sent to the configured third-party MCP server or connector."
    )
    embeds.append(
        Embed(
            title="MCP Approval Required",
            description=description,
            color=Colour.orange(),
        )
    )
    return embeds


def _append_public_pricing_embed(
    embeds: list[Embed],
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    reasoning_tokens: int,
    tool_call_counts: dict[str, int],
    daily_cost: float,
) -> None:
    if not SHOW_COST_EMBEDS:
        return
    append_pricing_embed(
        embeds,
        model,
        input_tokens,
        output_tokens,
        daily_cost,
        cached_tokens,
        reasoning_tokens,
        tool_call_counts or None,
    )


def _resolve_conversation_tools(
    cog,
    conversation: ResponseParameters,
) -> tuple[list[dict[str, Any]], str | None]:
    tools, error = cog.resolve_selected_tools(
        conversation.tool_names,
        conversation.model,
        conversation.mcp_preset_names,
    )
    if error:
        return [], error
    conversation.tools = tools
    return tools, None


def _build_pending_mcp_approval(
    *,
    tool_info: ToolInfo,
    usage: UsageInfo,
    response_id: str,
    existing_pending: PendingMcpApproval | None = None,
    intro_title: str | None = None,
    intro_description: str | None = None,
    attachment_url: str | None = None,
) -> PendingMcpApproval:
    raw_pending = tool_info["pending_mcp_approval"] or {}
    prior_counts = existing_pending["tool_call_counts"] if existing_pending else {}
    merged_counts = _merge_tool_call_counts(
        prior_counts,
        dict(tool_info["tool_call_counts"]),
    )
    return {
        "approval_request_id": raw_pending.get("approval_request_id", ""),
        "request_response_id": response_id,
        "server_label": raw_pending.get("server_label", ""),
        "tool_name": raw_pending.get("tool_name", ""),
        "arguments": raw_pending.get("arguments", ""),
        "intro_title": existing_pending["intro_title"] if existing_pending else intro_title,
        "intro_description": (
            existing_pending["intro_description"] if existing_pending else intro_description
        ),
        "attachment_url": existing_pending["attachment_url"]
        if existing_pending
        else attachment_url,
        "input_tokens": (existing_pending["input_tokens"] if existing_pending else 0)
        + usage["input_tokens"],
        "output_tokens": (existing_pending["output_tokens"] if existing_pending else 0)
        + usage["output_tokens"],
        "cached_tokens": (existing_pending["cached_tokens"] if existing_pending else 0)
        + usage["cached_tokens"],
        "reasoning_tokens": (existing_pending["reasoning_tokens"] if existing_pending else 0)
        + usage["reasoning_tokens"],
        "tool_call_counts": merged_counts,
    }


async def _send_conversation_reply(
    cog,
    *,
    user_id: int,
    conversation: ResponseParameters,
    send_reply: Callable[..., Awaitable[Any]],
    embeds: list[Embed],
    view,
) -> Any:
    conversation_id = _require_conversation_id(conversation)
    await cog._strip_previous_view(conversation_id)

    if embeds:
        reply_msg = await send_reply(embeds=embeds, view=view)
    else:
        cog.logger.warning("No embeds to send in the reply.")
        reply_msg = await send_reply(
            content="An error occurred: No content to send.",
            view=view,
        )

    remember_view_state(cog, user_id, conversation_id, view, reply_msg)
    return reply_msg


async def _run_followup_response(
    cog,
    *,
    conversation: ResponseParameters,
    input_content,
    user_id: int,
    channel,
    send_reply: Callable[..., Awaitable[Any]],
    message_id: int | None = None,
) -> None:
    typing_task = asyncio.create_task(keep_typing(channel))
    conversation_id = _require_conversation_id(conversation)

    try:
        tools, tool_error = _resolve_conversation_tools(cog, conversation)
        if tool_error:
            await send_reply(embed=error_embed(tool_error))
            return

        conversation.input = input_content
        conversation.set_last_user_input(input_content, message_id)
        response = await cog.openai_client.responses.create(**conversation.to_dict())
        response_text = get_response_text(response)
        tool_info = extract_tool_info(response)
        usage = extract_usage(response)

        if tool_info["pending_mcp_approval"] is not None:
            daily_cost = cog._track_daily_cost(
                user_id,
                conversation.model,
                usage["input_tokens"],
                usage["output_tokens"],
                usage["cached_tokens"],
                dict(tool_info["tool_call_counts"]) or None,
            )
            conversation.pending_mcp_approval = _build_pending_mcp_approval(
                tool_info=tool_info,
                usage=usage,
                response_id=response.id,
            )
            conversation.input = []
            conversation.touch()
            embeds = _build_mcp_approval_embeds(
                intro_title=None,
                intro_description=None,
                attachment_url=None,
                pending=conversation.pending_mcp_approval,
                response=response,
            )
            if SHOW_COST_EMBEDS:
                embeds.append(
                    Embed(
                        description=(
                            "Usage for this pre-approval step has already been counted toward your daily total. "
                            f"Current daily total: ${daily_cost:.2f}"
                        ),
                        color=Colour.blue(),
                    )
                )
            reply_view = cog._create_mcp_approval_view(user_id, conversation_id)
            await _send_conversation_reply(
                cog,
                user_id=user_id,
                conversation=conversation,
                send_reply=send_reply,
                embeds=embeds,
                view=reply_view,
            )
            await cog._prune_runtime_state()
            return

        conversation.previous_response_id = response.id
        conversation.response_id_history.append(response.id)
        conversation.pending_mcp_approval = None
        conversation.input = []
        conversation.touch()

        embeds: list[Embed] = []
        append_thinking_embeds(embeds, extract_summary_text(response))
        append_response_embeds(embeds, response_text)
        if tool_info["citations"] or tool_info["file_citations"]:
            append_sources_embed(embeds, tool_info["citations"], tool_info["file_citations"])
        cog._track_and_append_cost(embeds, user_id, conversation.model, response, tool_info)

        reply_view = cog._create_button_view(user_id, conversation_id, tools)
        await _send_conversation_reply(
            cog,
            user_id=user_id,
            conversation=conversation,
            send_reply=send_reply,
            embeds=embeds,
            view=reply_view,
        )
        await cog._prune_runtime_state()
    finally:
        typing_task.cancel()


async def handle_new_message_in_conversation(
    cog, message, conversation: ResponseParameters
) -> None:
    """Handle a follow-up message for an existing conversation."""
    cog.logger.info("Handling new message in conversation %s", conversation.conversation_id)

    if conversation.pending_mcp_approval is not None:
        await message.reply(
            embed=error_embed(
                "This conversation is waiting on an MCP approval decision. Approve, deny, or end it before sending another message."
            )
        )
        return

    try:
        await _run_followup_response(
            cog,
            conversation=conversation,
            input_content=build_input_content(message.content, message.attachments),
            user_id=message.author.id,
            channel=message.channel,
            send_reply=message.reply,
            message_id=message.id,
        )
    except Exception as error:
        description = format_openai_error(error)
        cog.logger.error(
            "Error in handle_new_message_in_conversation: %s",
            description,
            exc_info=True,
        )
        await cog._cleanup_conversation(message.author.id, conversation.conversation_id)
        removed_conversation = cog.conversation_histories.pop(conversation.conversation_id, None)
        if removed_conversation is not None:
            cog.logger.info(
                "Cleanup removed stale conversation id %s after follow-up failure.",
                conversation.conversation_id,
            )
        await message.reply(embed=error_embed(description))


async def regenerate_conversation_response(cog, interaction: Interaction, conversation) -> None:
    """Replay the last saved user input for a conversation."""
    user = interaction.user
    if user is None:
        raise RuntimeError("Cannot resolve the user for this interaction.")
    channel = interaction.channel
    if channel is None:
        raise RuntimeError("Cannot access the current channel to regenerate the response.")
    channel_send = getattr(channel, "send", None)
    if channel_send is None:
        raise RuntimeError("Cannot send a regenerated response in this channel type.")
    if conversation.last_user_input is None:
        raise RuntimeError("No saved prompt was found for this conversation.")

    await _run_followup_response(
        cog,
        conversation=conversation,
        input_content=conversation.last_user_input,
        user_id=user.id,
        channel=channel,
        send_reply=channel_send,
        message_id=conversation.last_user_message_id,
    )


async def handle_mcp_approval_action(
    cog,
    interaction: Interaction,
    conversation: ResponseParameters,
    approve: bool,
) -> None:
    user = interaction.user
    if user is None:
        await interaction.followup.send(
            "Cannot resolve the user for this interaction.",
            ephemeral=True,
        )
        return
    user_id = user.id
    pending = conversation.pending_mcp_approval
    if pending is None:
        await interaction.followup.send(
            "No pending MCP approval request was found.", ephemeral=True
        )
        return

    if interaction.message is None:
        await interaction.followup.send(
            "The approval message is no longer available, so this request can't continue.",
            ephemeral=True,
        )
        return

    tools, tool_error = _resolve_conversation_tools(cog, conversation)
    if tool_error:
        await interaction.followup.send(tool_error, ephemeral=True)
        return

    channel = interaction.channel
    if channel is None:
        await interaction.followup.send(
            "Cannot access the current channel to continue the MCP request.",
            ephemeral=True,
        )
        return

    typing_task = asyncio.create_task(keep_typing(channel))
    try:
        conversation_id = _require_conversation_id(conversation)
        approval_input = [
            {
                "type": "mcp_approval_response",
                "approve": approve,
                "approval_request_id": pending["approval_request_id"],
            }
        ]

        request_payload = conversation.to_dict()
        request_payload["tools"] = tools
        request_payload["previous_response_id"] = pending["request_response_id"]
        request_payload["input"] = approval_input

        response = await cog.openai_client.responses.create(**request_payload)
        response_text = get_response_text(response)
        tool_info = extract_tool_info(response)
        usage = extract_usage(response)
        combined_tool_counts = _merge_tool_call_counts(
            pending["tool_call_counts"],
            dict(tool_info["tool_call_counts"]),
        )

        daily_cost = cog._track_daily_cost(
            user_id,
            conversation.model,
            usage["input_tokens"],
            usage["output_tokens"],
            usage["cached_tokens"],
            dict(tool_info["tool_call_counts"]) or None,
        )

        if tool_info["pending_mcp_approval"] is not None:
            conversation.pending_mcp_approval = _build_pending_mcp_approval(
                tool_info=tool_info,
                usage=usage,
                response_id=response.id,
                existing_pending=pending,
            )
            conversation.input = []
            conversation.touch()

            embeds = _build_mcp_approval_embeds(
                intro_title=conversation.pending_mcp_approval["intro_title"],
                intro_description=conversation.pending_mcp_approval["intro_description"],
                attachment_url=conversation.pending_mcp_approval["attachment_url"],
                pending=conversation.pending_mcp_approval,
                response=response,
            )
            if SHOW_COST_EMBEDS:
                embeds.append(
                    Embed(
                        description=(
                            "Another MCP approval is required before the assistant can continue. "
                            f"Current daily total: ${daily_cost:.2f}"
                        ),
                        color=Colour.blue(),
                    )
                )
            approval_view = cog._create_mcp_approval_view(
                user_id,
                conversation_id,
            )
            await interaction.message.edit(embeds=embeds, view=approval_view)
            remember_view_state(cog, user_id, conversation_id, approval_view, interaction.message)
            await interaction.followup.send(
                "Another MCP approval is required before this conversation can continue.",
                ephemeral=True,
            )
            await cog._prune_runtime_state()
            return

        conversation.previous_response_id = response.id
        conversation.response_id_history.append(response.id)
        conversation.pending_mcp_approval = None
        conversation.input = []
        conversation.touch()

        embeds = _build_intro_embeds(
            pending["intro_title"],
            pending["intro_description"],
            pending["attachment_url"],
        )
        append_thinking_embeds(embeds, extract_summary_text(response))
        final_text = response_text
        if final_text == "No response." and not approve:
            final_text = "MCP tool call was denied."
        append_response_embeds(embeds, final_text)
        if tool_info["citations"] or tool_info["file_citations"]:
            append_sources_embed(embeds, tool_info["citations"], tool_info["file_citations"])
        _append_public_pricing_embed(
            embeds,
            model=conversation.model,
            input_tokens=pending["input_tokens"] + usage["input_tokens"],
            output_tokens=pending["output_tokens"] + usage["output_tokens"],
            cached_tokens=pending["cached_tokens"] + usage["cached_tokens"],
            reasoning_tokens=pending["reasoning_tokens"] + usage["reasoning_tokens"],
            tool_call_counts=combined_tool_counts,
            daily_cost=daily_cost,
        )

        reply_view = cog._create_button_view(
            user_id,
            conversation_id,
            tools,
        )
        await interaction.message.edit(embeds=embeds, view=reply_view)
        remember_view_state(cog, user_id, conversation_id, reply_view, interaction.message)
        await interaction.followup.send(
            "MCP request approved." if approve else "MCP request denied.",
            ephemeral=True,
            delete_after=3,
        )
        await cog._prune_runtime_state()
    except Exception as error:
        cog.logger.error("Error continuing MCP approval flow", exc_info=True)
        await interaction.followup.send(format_openai_error(error), ephemeral=True)
    finally:
        typing_task.cancel()


async def keep_typing(channel) -> None:
    """Keep the Discord typing indicator alive while a request is running."""
    while True:
        async with channel.typing():
            await asyncio.sleep(5)


async def handle_on_message(cog, message) -> None:
    """Process follow-up user messages for active conversations."""
    if message.author == cog.bot.user:
        return

    await cog._prune_runtime_state()
    for conversation in cog.conversation_histories.values():
        if (
            message.channel.id == conversation.channel_id
            and message.author.id == conversation.conversation_starter_id
        ):
            if conversation.paused:
                cog.logger.debug(
                    "Ignoring message because conversation %s is paused.",
                    conversation.conversation_id,
                )
                return
            if conversation.pending_mcp_approval is not None:
                await message.reply(
                    embed=error_embed(
                        "This conversation is waiting on an MCP approval decision. Approve, deny, or end it before sending another message."
                    )
                )
                return
            await handle_new_message_in_conversation(cog, message, conversation)
            break


async def handle_check_permissions(cog, ctx: ApplicationContext) -> None:
    """Check whether the bot can read the current channel."""
    guild = ctx.guild
    channel = ctx.channel

    if guild is None or channel is None:
        await ctx.respond("This command can only be used in a server channel.")
        return

    me = guild.me
    if me is None:
        await ctx.respond("Unable to resolve bot member for this server.")
        return

    if not hasattr(channel, "permissions_for"):
        await ctx.respond("Cannot check permissions for this channel type.")
        return

    permissions = cast(PermissionAwareChannel, channel).permissions_for(me)
    if permissions.read_messages and permissions.read_message_history:
        await ctx.respond("Bot has permission to read messages and message history.")
    else:
        await ctx.respond("Bot is missing necessary permissions in this channel.")


async def run_chat_command(
    cog,
    ctx: ApplicationContext,
    prompt: str,
    persona: str,
    model: str,
    attachment: Attachment | None,
    frequency_penalty: float | None,
    presence_penalty: float | None,
    temperature: float | None,
    top_p: float | None,
    reasoning_effort: str | None,
    verbosity: str | None,
    web_search: bool,
    code_interpreter: bool,
    file_search: bool,
    shell: bool,
    mcp: str | None = None,
) -> None:
    """Run the /openai chat command."""
    await ctx.defer()
    await cog._prune_runtime_state()
    author = ctx.author
    interaction = ctx.interaction
    channel_id = ctx.channel_id
    if author is None or interaction is None or channel_id is None:
        await ctx.send_followup(
            embed=error_embed("This command requires a normal Discord interaction context.")
        )
        return

    for conversation in cog.conversation_histories.values():
        if (
            conversation.conversation_starter_id == author.id
            and conversation.channel_id == channel_id
        ):
            await ctx.send_followup(
                embed=error_embed(
                    "You already have an active conversation in this channel. Please finish it before starting a new one."
                )
            )
            return

    input_content = build_input_content(prompt, [attachment] if attachment else [])
    selected_tool_names: list[str] = []
    if web_search:
        selected_tool_names.append("web_search")
    if code_interpreter:
        selected_tool_names.append("code_interpreter")
    if file_search:
        selected_tool_names.append("file_search")
    if shell:
        selected_tool_names.append("shell")
    mcp_preset_names = parse_mcp_preset_names(mcp)

    tools, tool_error = cog.resolve_selected_tools(
        selected_tool_names,
        model,
        mcp_preset_names,
    )
    if tool_error:
        await ctx.send_followup(embed=error_embed(tool_error))
        return

    params = ResponseParameters(
        model=model,
        instructions=persona,
        input=input_content,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        temperature=temperature,
        top_p=top_p,
        reasoning=build_reasoning_config(model, reasoning_effort),
        verbosity=verbosity,
        tools=tools,
        tool_names=selected_tool_names,
        mcp_preset_names=mcp_preset_names,
        conversation_starter=author,
        conversation_starter_id=author.id,
        conversation_id=interaction.id,
        channel_id=channel_id,
        response_id_history=[],
        safety_identifier=hash_user_id(author.id),
    )
    params.set_last_user_input(input_content)

    try:
        description = ""
        description += f"**Prompt:** {truncate_text(prompt, 2000)}\n"
        description += f"**Model:** {params.model}\n"
        description += f"**Persona:** {params.instructions}\n"
        active_tool_labels = [tool["type"] for tool in params.tools if tool["type"] != "mcp"]
        if active_tool_labels:
            description += f"**Tools:** {', '.join(active_tool_labels)}\n"
        if params.mcp_preset_names:
            description += f"**MCP Presets:** {', '.join(params.mcp_preset_names)}\n"
        if params.frequency_penalty is not None:
            description += f"**Frequency Penalty:** {params.frequency_penalty}\n"
        if params.presence_penalty is not None:
            description += f"**Presence Penalty:** {params.presence_penalty}\n"
        if params.temperature is not None:
            description += f"**Temperature:** {params.temperature}\n"
        if params.top_p is not None:
            description += f"**Nucleus Sampling:** {params.top_p}\n"
        if params.reasoning:
            description += f"**Reasoning Effort:** {params.reasoning.get('effort', 'medium')}\n"
        if params.verbosity:
            description += f"**Verbosity:** {params.verbosity}\n"

        response = await cog.openai_client.responses.create(**params.to_dict())
        response_text = get_response_text(response)
        tool_info = extract_tool_info(response)
        usage = extract_usage(response)

        embeds = _build_intro_embeds(
            "Conversation Started",
            description,
            attachment.url if attachment is not None else None,
        )

        if tool_info["pending_mcp_approval"] is not None:
            daily_cost = cog._track_daily_cost(
                author.id,
                model,
                usage["input_tokens"],
                usage["output_tokens"],
                usage["cached_tokens"],
                dict(tool_info["tool_call_counts"]) or None,
            )
            params.pending_mcp_approval = _build_pending_mcp_approval(
                tool_info=tool_info,
                usage=usage,
                response_id=response.id,
                intro_title="Conversation Started",
                intro_description=description,
                attachment_url=attachment.url if attachment is not None else None,
            )
            params.input = []
            params.touch()
            embeds.extend(
                _build_mcp_approval_embeds(
                    intro_title=None,
                    intro_description=None,
                    attachment_url=None,
                    pending=params.pending_mcp_approval,
                    response=response,
                )
            )
            if SHOW_COST_EMBEDS:
                embeds.append(
                    Embed(
                        description=(
                            "Usage for this pre-approval step has already been counted toward your daily total. "
                            f"Current daily total: ${daily_cost:.2f}"
                        ),
                        color=Colour.blue(),
                    )
                )
            reply_view = cog._create_mcp_approval_view(author.id, interaction.id)
        else:
            params.previous_response_id = response.id
            params.response_id_history.append(response.id)
            params.pending_mcp_approval = None
            params.input = []
            params.touch()
            append_thinking_embeds(embeds, extract_summary_text(response))
            append_response_embeds(embeds, response_text)
            if tool_info["citations"] or tool_info["file_citations"]:
                append_sources_embed(embeds, tool_info["citations"], tool_info["file_citations"])
            cog._track_and_append_cost(embeds, author.id, model, response, tool_info)
            reply_view = cog._create_button_view(author.id, interaction.id, tools)

        reply_msg = await ctx.send_followup(embeds=embeds, view=reply_view)

        cog.conversation_histories[interaction.id] = params
        remember_view_state(cog, author.id, interaction.id, reply_view, reply_msg)
        await cog._prune_runtime_state()
    except Exception as error:
        await cog._cleanup_conversation(author.id, interaction.id)
        await ctx.send_followup(embed=error_embed(format_openai_error(error)))


__all__ = [
    "handle_check_permissions",
    "handle_mcp_approval_action",
    "handle_new_message_in_conversation",
    "handle_on_message",
    "keep_typing",
    "regenerate_conversation_response",
    "run_chat_command",
]
