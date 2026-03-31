import asyncio
from typing import cast

from discord import ApplicationContext, Attachment, Colour, Embed

from ...util import (
    ResponseParameters,
    build_input_content,
    format_openai_error,
    hash_user_id,
    truncate_text,
)
from .embeds import (
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
    error_embed,
)
from .models import PermissionAwareChannel
from .responses import build_reasoning_config, extract_summary_text, get_response_text
from .tooling import extract_tool_info


async def handle_new_message_in_conversation(
    cog, message, conversation: ResponseParameters
) -> None:
    """Handle a follow-up message for an existing conversation."""
    cog.logger.info(f"Handling new message in conversation {conversation.conversation_id}")
    typing_task = None
    embeds = []

    try:
        typing_task = asyncio.create_task(keep_typing(message.channel))
        conversation.input = build_input_content(message.content, message.attachments)
        cog.logger.debug(f"Built input content: {conversation.input}")

        response = await cog.openai_client.responses.create(**conversation.to_dict())
        response_text = get_response_text(response)
        tool_info = extract_tool_info(response)

        conversation.previous_response_id = response.id
        conversation.response_id_history.append(response.id)
        conversation.input = []

        append_thinking_embeds(embeds, extract_summary_text(response))
        append_response_embeds(embeds, response_text)
        if tool_info["citations"] or tool_info["file_citations"]:
            append_sources_embed(embeds, tool_info["citations"], tool_info["file_citations"])
        cog._track_and_append_cost(
            embeds, message.author.id, conversation.model, response, tool_info
        )

        await cog._strip_previous_view(message.author)
        cog.views[message.author] = cog._create_button_view(
            message.author,
            conversation.conversation_id,
            conversation.tools,
        )

        if embeds:
            reply_msg = await message.reply(embeds=embeds, view=cog.views[message.author])
        else:
            cog.logger.warning("No embeds to send in the reply.")
            reply_msg = await message.reply(
                content="An error occurred: No content to send.",
                view=cog.views[message.author],
            )
        cog.last_view_messages[message.author] = reply_msg
    except Exception as e:
        description = format_openai_error(e)
        cog.logger.error(
            f"Error in handle_new_message_in_conversation: {description}",
            exc_info=True,
        )
        await cog._cleanup_conversation(message.author)
        await message.reply(embed=error_embed(description))
    finally:
        if typing_task:
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

    for conversation in cog.conversation_histories.values():
        if (
            message.channel.id == conversation.channel_id
            and message.author == conversation.conversation_starter
        ):
            if conversation.paused:
                cog.logger.debug(
                    "Ignoring message because conversation %s is paused.",
                    conversation.conversation_id,
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
) -> None:
    """Run the /openai chat command."""
    await ctx.defer()

    for conversation in cog.conversation_histories.values():
        if (
            conversation.conversation_starter == ctx.author
            and conversation.channel_id == ctx.channel_id
        ):
            await ctx.send_followup(
                embed=error_embed(
                    "You already have an active conversation in this channel. Please finish it before starting a new one."
                )
            )
            return

    input_content = build_input_content(prompt, [attachment] if attachment else [])
    selected_tool_names = []
    if web_search:
        selected_tool_names.append("web_search")
    if code_interpreter:
        selected_tool_names.append("code_interpreter")
    if file_search:
        selected_tool_names.append("file_search")
    if shell:
        selected_tool_names.append("shell")

    tools, tool_error = cog.resolve_selected_tools(selected_tool_names, model)
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
        conversation_starter=ctx.author,
        conversation_id=ctx.interaction.id,
        channel_id=ctx.channel_id,
        response_id_history=[],
        safety_identifier=hash_user_id(ctx.author.id),
    )

    try:
        description = ""
        description += f"**Prompt:** {truncate_text(prompt, 2000)}\n"
        description += f"**Model:** {params.model}\n"
        description += f"**Persona:** {params.instructions}\n"
        if params.tools:
            description += f"**Tools:** {', '.join(tool['type'] for tool in params.tools)}\n"
        description += (
            f"**Frequency Penalty:** {params.frequency_penalty}\n"
            if params.frequency_penalty
            else ""
        )
        description += (
            f"**Presence Penalty:** {params.presence_penalty}\n" if params.presence_penalty else ""
        )
        description += f"**Temperature:** {params.temperature}\n" if params.temperature else ""
        description += f"**Nucleus Sampling:** {params.top_p}\n" if params.top_p else ""
        if params.reasoning:
            description += f"**Reasoning Effort:** {params.reasoning.get('effort', 'medium')}\n"
        if params.verbosity:
            description += f"**Verbosity:** {params.verbosity}\n"

        response = await cog.openai_client.responses.create(**params.to_dict())
        response_text = get_response_text(response)
        tool_info = extract_tool_info(response)

        params.previous_response_id = response.id
        params.response_id_history.append(response.id)
        params.input = []

        embeds = [
            Embed(
                title="Conversation Started",
                description=description,
                color=Colour.green(),
            ),
        ]
        if attachment is not None:
            embeds.append(
                Embed(
                    title="Attachment",
                    description=attachment.url,
                    color=Colour.green(),
                )
            )
        append_thinking_embeds(embeds, extract_summary_text(response))
        append_response_embeds(embeds, response_text)
        if tool_info["citations"] or tool_info["file_citations"]:
            append_sources_embed(embeds, tool_info["citations"], tool_info["file_citations"])

        cog._track_and_append_cost(embeds, ctx.author.id, model, response, tool_info)
        await cog._strip_previous_view(ctx.author)
        cog.views[ctx.author] = cog._create_button_view(ctx.author, ctx.interaction.id, tools)

        reply_msg = await ctx.send_followup(embeds=embeds, view=cog.views[ctx.author])
        cog.last_view_messages[ctx.author] = reply_msg
        cog.conversation_histories[ctx.interaction.id] = params
    except Exception as e:
        await cog._cleanup_conversation(ctx.author)
        await ctx.send_followup(embed=error_embed(format_openai_error(e)))
