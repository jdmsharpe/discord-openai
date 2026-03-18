import aiohttp
import asyncio
import base64
import tempfile
from button_view import ButtonView
import hashlib
import logging
import io
from openai import AsyncOpenAI
from discord import (
    ApplicationContext,
    Attachment,
    Colour,
    Embed,
    File,
)
from discord.ext import commands
from discord.commands import option, OptionChoice, SlashCommandGroup
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Protocol, Tuple, TypedDict, cast
import time
from util import (
    AVAILABLE_TOOLS,
    CONTEXT_MANAGEMENT,
    DEEP_RESEARCH_MODELS,
    GPT5_NO_TEMP_MODELS,
    PROMPT_CACHE_RETENTION,
    INPUT_TEXT_TYPE,
    REASONING_EFFORT_MEDIUM,
    REASONING_EFFORT_NONE,
    REASONING_MODELS,
    TOOL_FILE_SEARCH,
    TOOL_SHELL,
    TOOL_WEB_SEARCH,
    TOOL_CODE_INTERPRETER,
    ImageGenerationParameters,
    ResearchParameters,
    ResponseParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
    build_attachment_content_block,
    calculate_cost,
    calculate_image_cost,
    calculate_stt_cost,
    calculate_tool_cost,
    calculate_tts_cost,
    calculate_video_cost,
    chunk_text,
    estimate_audio_duration_seconds,
    format_openai_error,
    truncate_text,
)
from config.auth import GUILD_IDS, OPENAI_API_KEY, OPENAI_VECTOR_STORE_IDS, SHOW_COST_EMBEDS


class ToolInfo(TypedDict):
    tool_types: List[str]
    tool_call_counts: Dict[str, int]
    citations: List[Dict[str, str]]
    file_citations: List[Dict[str, str]]


class PermissionAwareChannel(Protocol):
    def permissions_for(self, member: Any) -> Any:
        ...


def append_response_embeds(embeds, response_text):
    # Respect Discord's 6000-char per-message total across all embeds.
    # Reserve 500 chars for citations/pricing embeds that may be appended after.
    used = sum(len(e.description or "") for e in embeds)
    available = max(500, 6000 - used - 500)
    if len(response_text) > available:
        response_text = truncate_text(response_text, available)

    for index, chunk in enumerate(chunk_text(response_text), start=1):
        embeds.append(
            Embed(
                title="Response" + (f" (Part {index})" if index > 1 else ""),
                description=chunk,
                color=Colour.blue(),
            )
        )


def extract_tool_info(response: Any) -> ToolInfo:
    """Extract tool usage, web citations, and file citations from a Responses API object."""

    def get_value(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    citations: List[Dict[str, str]] = []
    file_citations: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_file_ids: set[str] = set()
    tools_used: set[str] = set()
    tool_call_counts: Dict[str, int] = {}

    CALL_TYPE_MAP = {
        "web_search_call": "web_search",
        "file_search_call": "file_search",
        "code_interpreter_call": "code_interpreter",
        "shell_call": "shell",
    }

    output_items = get_value(response, "output", []) or []
    for output_item in output_items:
        output_type = get_value(output_item, "type")
        item_name = get_value(output_item, "name")

        tool_key = CALL_TYPE_MAP.get(output_type) or (item_name if item_name in AVAILABLE_TOOLS else None)
        if tool_key:
            tools_used.add(tool_key)
            tool_call_counts[tool_key] = tool_call_counts.get(tool_key, 0) + 1

        content_blocks = get_value(output_item, "content", []) or []
        for content_block in content_blocks:
            annotations = get_value(content_block, "annotations", []) or []
            for annotation in annotations:
                annotation_type = get_value(annotation, "type")

                if annotation_type == "url_citation":
                    url = get_value(annotation, "url")
                    title = get_value(annotation, "title") or url
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    citations.append({"title": title, "url": url})
                    tools_used.add("web_search")

                elif annotation_type == "file_citation":
                    file_id = get_value(annotation, "file_id") or ""
                    filename = get_value(annotation, "filename") or file_id
                    if not file_id or file_id in seen_file_ids:
                        continue
                    seen_file_ids.add(file_id)
                    file_citations.append(
                        {"filename": filename, "file_id": file_id}
                    )

    return {
        "tool_types": sorted(tools_used),
        "tool_call_counts": tool_call_counts,
        "citations": citations,
        "file_citations": file_citations,
    }


def append_sources_embed(
    embeds: List[Embed],
    citations: List[Dict[str, str]],
    file_citations: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Append a sources embed listing web links and/or file citations."""
    if not citations and not file_citations:
        return

    parts: List[str] = []

    # Web citations as numbered links
    if citations:
        web_lines = [
            f"{index}. [{citation['title']}]({citation['url']})"
            for index, citation in enumerate(citations[:20], start=1)
        ]
        parts.append("\n".join(web_lines))

    # File citations as numbered filenames
    if file_citations:
        file_lines = [
            f"{index}. {citation['filename']}"
            for index, citation in enumerate(file_citations[:20], start=1)
        ]
        parts.append("**Files referenced:**\n" + "\n".join(file_lines))

    description = "\n\n".join(parts)

    current_total = sum(
        len(embed.description or "") + len(embed.title or "") for embed in embeds
    )
    remaining_chars = 6000 - current_total - len("Sources")

    if remaining_chars < 50:
        return

    max_description_length = min(4096, remaining_chars)
    if max_description_length <= 0:
        return

    if len(description) > max_description_length:
        description = truncate_text(description, max_description_length - 3)

    embeds.append(
        Embed(
            title="Sources",
            description=description,
            color=Colour.blue(),
        )
    )


def append_pricing_embed(
    embeds: List[Embed],
    model: str,
    input_tokens: int,
    output_tokens: int,
    daily_cost: float,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
    tool_call_counts: Optional[Dict[str, int]] = None,
) -> None:
    """Append a compact pricing embed showing model, cost, and token usage."""
    tool_cost = calculate_tool_cost(tool_call_counts) if tool_call_counts else 0.0
    cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens) + tool_cost
    in_part = f"{input_tokens:,} in"
    if cached_tokens:
        in_part += f" ({cached_tokens:,} cached)"
    out_part = f"{output_tokens:,} out"
    if reasoning_tokens:
        out_part += f" ({reasoning_tokens:,} thinking)"
    parts = [f"${cost:.4f}", f"{in_part} / {out_part}"]
    if tool_call_counts:
        tool_str = " + ".join(
            f"{tool.replace('_', ' ')} ×{count}"
            for tool, count in sorted(tool_call_counts.items())
        )
        parts.append(f"tools: {tool_str} (${tool_cost:.4f})")
    parts.append(f"daily ${daily_cost:.2f}")
    embeds.append(Embed(description=" · ".join(parts), color=Colour.blue()))


def append_flat_pricing_embed(
    embeds: List[Embed],
    cost: float,
    daily_cost: float,
    details: str = "",
) -> None:
    """Append a compact pricing embed for non-token-based commands (image/TTS/STT/video)."""
    parts = [f"${cost:.4f}"]
    if details:
        parts.append(details)
    parts.append(f"daily ${daily_cost:.2f}")
    embeds.append(Embed(description=" · ".join(parts), color=Colour.blue()))


class OpenAIAPI(commands.Cog):
    openai = SlashCommandGroup("openai", "OpenAI commands", guild_ids=GUILD_IDS)

    def __init__(self, bot):
        """
        Initialize the OpenAIAPI class.

        Args:
            bot: The bot instance.
        """
        logging.basicConfig(
            level=logging.DEBUG,  # Capture all levels of logs
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)
        self.bot = bot
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # Dictionary to store conversation histories for each chat interaction
        self.conversation_histories = {}
        # Dictionary to store UI views for each conversation
        self.views = {}
        # Last message with a ButtonView attached, keyed by user — used to strip old buttons
        self.last_view_messages = {}
        # Daily cost accumulator keyed by (user_id, date_iso)
        self.daily_costs = {}

    async def _strip_previous_view(self, user) -> None:
        """Edit the last message that had buttons to remove its view."""
        prev = self.last_view_messages.pop(user, None)
        if prev is not None:
            try:
                await prev.edit(view=None)
            except Exception as e:
                self.logger.debug(f"Could not edit previous message: {e}")

    async def _cleanup_conversation(self, user) -> None:
        """Remove button view from the last message and clean up view state."""
        await self._strip_previous_view(user)
        self.views.pop(user, None)

    def _track_daily_cost(
        self,
        user_id: int,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        tool_call_counts: Optional[Dict[str, int]] = None,
        command: str = "chat",
    ) -> float:
        """Add this request's cost to the user's daily total and return the new daily total."""
        cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens)
        tool_cost = 0.0
        if tool_call_counts:
            tool_cost = calculate_tool_cost(tool_call_counts)
            cost += tool_cost
        key = (user_id, date.today().isoformat())
        self.daily_costs[key] = self.daily_costs.get(key, 0.0) + cost
        self.logger.info(
            f"COST | command={command} | user={user_id} | model={model}"
            f" | input_tokens={input_tokens} | output_tokens={output_tokens}"
            f" | cached_tokens={cached_tokens}"
            + (f" | tools={tool_call_counts} | tool_cost=${tool_cost:.4f}" if tool_call_counts else "")
            + f" | cost=${cost:.4f} | daily=${self.daily_costs[key]:.4f}"
        )
        return self.daily_costs[key]

    def _track_daily_cost_direct(
        self,
        user_id: int,
        command: str,
        model: str,
        cost: float,
        details: str = "",
    ) -> float:
        """Track a pre-computed cost (image/TTS/STT/video) and return the new daily total."""
        key = (user_id, date.today().isoformat())
        self.daily_costs[key] = self.daily_costs.get(key, 0.0) + cost
        self.logger.info(
            f"COST | command={command} | user={user_id} | model={model}"
            f" | cost=${cost:.4f} | daily=${self.daily_costs[key]:.4f}"
            + (f" | {details}" if details else "")
        )
        return self.daily_costs[key]

    def resolve_selected_tools(
        self, selected_tool_names: List[str], model: str
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Build tool payloads for selected tool names and model constraints."""
        tools: List[Dict[str, Any]] = []

        for tool_name in selected_tool_names:
            if tool_name == "file_search":
                if not OPENAI_VECTOR_STORE_IDS:
                    return (
                        [],
                        "File search requires OPENAI_VECTOR_STORE_IDS to be set in your .env.",
                    )
                tool: Dict[str, Any] = TOOL_FILE_SEARCH.copy()
                tool["vector_store_ids"] = OPENAI_VECTOR_STORE_IDS.copy()
                tools.append(tool)
                continue

            if tool_name == "shell":
                # Hosted shell examples and current reliability are strongest on GPT-5 series.
                if not model.startswith("gpt-5"):
                    return (
                        [],
                        "Shell currently requires a GPT-5 series model in this bot configuration.",
                    )
                tools.append(TOOL_SHELL.copy())
                continue

            if tool_name in AVAILABLE_TOOLS:
                tools.append(AVAILABLE_TOOLS[tool_name].copy())

        return tools, None

    async def handle_new_message_in_conversation(self, message, conversation):
        """
        Handles a new message in an ongoing conversation using the Responses API.

        Args:
            message: The incoming Discord Message object.
            conversation: The conversation object, which is of type ResponseParameters.
        """
        self.logger.info(
            f"Handling new message in conversation {conversation.conversation_id}"
        )
        typing_task = None
        embeds = []

        try:
            # Start typing indicator
            typing_task = asyncio.create_task(self.keep_typing(message.channel))

            # Build input for Responses API
            # For text-only, use a simple string. For multimodal, use content array.
            if message.attachments:
                input_content = []
                if message.content:
                    input_content.append({"type": INPUT_TEXT_TYPE, "text": message.content})
                for attachment in message.attachments:
                    input_content.append(
                        build_attachment_content_block(
                            attachment.content_type, attachment.url
                        )
                    )
            else:
                input_content = message.content  # Simple string for text-only
            self.logger.debug(f"Built input content: {input_content}")

            # Build API call parameters
            api_params = {
                "model": conversation.model,
                "input": input_content,
            }

            # Add previous_response_id for conversation chaining
            if conversation.previous_response_id:
                api_params["previous_response_id"] = conversation.previous_response_id

            # Add optional parameters if set
            if conversation.frequency_penalty is not None:
                api_params["frequency_penalty"] = conversation.frequency_penalty
            if conversation.presence_penalty is not None:
                api_params["presence_penalty"] = conversation.presence_penalty
            if conversation.temperature is not None:
                api_params["temperature"] = conversation.temperature
            if conversation.top_p is not None:
                api_params["top_p"] = conversation.top_p
            if conversation.reasoning is not None:
                api_params["reasoning"] = conversation.reasoning
            if conversation.verbosity:
                api_params["text"] = {"verbosity": conversation.verbosity}
            if conversation.tools:
                api_params["tools"] = conversation.tools
            api_params["context_management"] = CONTEXT_MANAGEMENT
            api_params["prompt_cache_retention"] = PROMPT_CACHE_RETENTION
            if conversation.instructions:
                api_params["instructions"] = conversation.instructions
                api_params["prompt_cache_key"] = hashlib.sha256(
                    conversation.instructions.encode()
                ).hexdigest()[:16]

            # API call using Responses API
            self.logger.debug("Making API call to OpenAI Responses API.")
            response = await self.openai_client.responses.create(**api_params)
            response_text = (
                response.output_text if response.output_text else "No response."
            )
            self.logger.debug(f"Received response from OpenAI: {response_text}")
            tool_info = extract_tool_info(response)

            # Update conversation state with new response ID
            conversation.previous_response_id = response.id
            conversation.response_id_history.append(response.id)
            self.logger.debug(f"Updated previous_response_id to: {response.id}")

            # Assemble the response embeds (view attaches to these)
            append_response_embeds(embeds, response_text)

            if tool_info["citations"] or tool_info["file_citations"]:
                append_sources_embed(
                    embeds, tool_info["citations"], tool_info["file_citations"]
                )

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            input_details = getattr(usage, "input_tokens_details", None)
            output_details = getattr(usage, "output_tokens_details", None)
            cached_tokens = getattr(input_details, "cached_tokens", 0) or 0
            reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0
            tool_call_counts = tool_info["tool_call_counts"] or None
            daily_cost = self._track_daily_cost(
                message.author.id, conversation.model, input_tokens, output_tokens,
                cached_tokens, tool_call_counts
            )
            if SHOW_COST_EMBEDS:
                append_pricing_embed(
                    embeds, conversation.model, input_tokens, output_tokens, daily_cost,
                    cached_tokens, reasoning_tokens, tool_call_counts
                )

            # Strip buttons from previous turn's message
            await self._strip_previous_view(message.author)

            # Recreate the ButtonView so the tool select reflects current state
            self.views[message.author] = ButtonView(
                self,
                message.author,
                conversation.conversation_id,
                initial_tools=conversation.tools,
            )

            if embeds:
                reply_msg = await message.reply(
                    embeds=embeds,
                    view=self.views[message.author],
                )
                self.last_view_messages[message.author] = reply_msg
                self.logger.debug("Replied with generated response.")
            else:
                self.logger.warning("No embeds to send in the reply.")
                reply_msg = await message.reply(
                    content="An error occurred: No content to send.",
                    view=self.views[message.author],
                )
                self.last_view_messages[message.author] = reply_msg

        except Exception as e:
            description = format_openai_error(e)
            self.logger.error(
                f"Error in handle_new_message_in_conversation: {description}",
                exc_info=True,
            )
            await self._cleanup_conversation(message.author)
            await message.reply(
                embed=Embed(title="Error", description=description, color=Colour.red())
            )

        finally:
            if typing_task:
                typing_task.cancel()

    async def keep_typing(self, channel):
        """
        Coroutine to keep the typing indicator alive in a channel.

        Args:
            channel: The Discord channel object.
        """
        while True:
            async with channel.typing():
                await asyncio.sleep(5)  # Resend typing indicator every 5 seconds

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener that runs when the bot is ready.
        Logs bot details and attempts to synchronize commands.
        """
        self.logger.info(f"Logged in as {self.bot.user} (ID: {self.bot.owner_id})")
        self.logger.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            self.logger.info("Commands synchronized successfully.")
        except Exception as e:
            self.logger.error(
                f"Error during command synchronization: {e}", exc_info=True
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Event listener that runs when a message is sent.
        Generates a response using chat completion API when a new message from the conversation author is detected.

        Args:
            message: The incoming Discord Message object.
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # Look for a conversation that matches BOTH the channel AND the user
        for conversation in self.conversation_histories.values():
            # Check if message is in the same channel AND from the conversation starter
            if (
                message.channel.id == conversation.channel_id
                and message.author == conversation.conversation_starter
            ):
                if conversation.paused:
                    self.logger.debug(
                        "Ignoring message because conversation %s is paused.",
                        conversation.conversation_id,
                    )
                    return
                # Process the message for the matching conversation
                await self.handle_new_message_in_conversation(message, conversation)
                break  # Stop looping once we've handled the message

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """
        Event listener that runs when an error occurs.

        Args:
            event: The name of the event that raised the error.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.logger.error(f"Error in event {event}: {args} {kwargs}", exc_info=True)

    @openai.command(
        name="check_permissions",
        description="Check if bot has necessary permissions in this channel",
    )
    async def check_permissions(self, ctx: ApplicationContext):
        """
        Checks and reports the bot's permissions in the current channel.
        """
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
            await ctx.respond(
                "Bot has permission to read messages and message history."
            )
        else:
            await ctx.respond("Bot is missing necessary permissions in this channel.")

    @openai.command(
        name="chat",
        description="Starts a conversation with a model.",
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "persona",
        description="What role you want the model to emulate. (default: You are a helpful assistant.)",
        required=False,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following GPT models. (default: GPT-5.4)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-5.4 Pro", value="gpt-5.4-pro"),
            OptionChoice(name="GPT-5.4", value="gpt-5.4"),
            OptionChoice(name="GPT-5.3", value="gpt-5.3-chat-latest"),
            OptionChoice(name="GPT-5.2 Pro", value="gpt-5.2-pro"),
            OptionChoice(name="GPT-5.2", value="gpt-5.2"),
            OptionChoice(name="GPT-5.1", value="gpt-5.1"),
            OptionChoice(name="GPT-5 Pro", value="gpt-5-pro"),
            OptionChoice(name="GPT-5", value="gpt-5"),
            OptionChoice(name="GPT-5 Mini", value="gpt-5-mini"),
            OptionChoice(name="GPT-5 Nano", value="gpt-5-nano"),
            OptionChoice(name="GPT-4.1", value="gpt-4.1"),
            OptionChoice(name="GPT-4.1 Mini", value="gpt-4.1-mini"),
            OptionChoice(name="GPT-4.1 Nano", value="gpt-4.1-nano"),
            OptionChoice(name="o4 Mini", value="o4-mini"),
            OptionChoice(name="o3 Pro", value="o3-pro"),
            OptionChoice(name="o3", value="o3"),
            OptionChoice(name="o3 Mini", value="o3-mini"),
            OptionChoice(name="o1 Pro", value="o1-pro"),
            OptionChoice(name="o1", value="o1"),
            OptionChoice(name="GPT-4o", value="gpt-4o"),
            OptionChoice(name="GPT-4o Mini", value="gpt-4o-mini"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo"),
        ],
    )
    @option(
        "attachment",
        description="Attach an image, PDF, document, spreadsheet, or code file. (default: not set)",
        required=False,
        type=Attachment,
    )
    @option(
        "frequency_penalty",
        description="(Advanced) Controls how much the model should repeat itself. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "presence_penalty",
        description="(Advanced) Controls how much the model should talk about the prompt. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "temperature",
        description="(Advanced) Controls the randomness of the model. Set this or top_p, but not both. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "top_p",
        description="(Advanced) Nucleus sampling. Set this or temperature, but not both. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "web_search",
        description="Enable web search to find current information. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "code_interpreter",
        description="Enable code interpreter to run Python code. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "file_search",
        description="Enable file search over configured vector stores. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "shell",
        description="Enable hosted shell command execution (GPT-5 models). (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "reasoning_effort",
        description="(Advanced) Reasoning depth. none=fastest, xhigh=deepest (GPT-5.4 only). (default: not set)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="None (fastest, no reasoning)", value="none"),
            OptionChoice(name="Low", value="low"),
            OptionChoice(name="Medium", value="medium"),
            OptionChoice(name="High", value="high"),
            OptionChoice(name="Extra High (GPT-5.4 only)", value="xhigh"),
        ],
    )
    @option(
        "verbosity",
        description="(Advanced) Controls response length. low=concise, high=detailed. (default: medium)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Low (concise)", value="low"),
            OptionChoice(name="Medium (default)", value="medium"),
            OptionChoice(name="High (detailed)", value="high"),
        ],
    )
    async def chat(
        self,
        ctx: ApplicationContext,
        prompt: str,
        persona: str = "You are a helpful assistant.",
        model: str = "gpt-5.4",
        attachment: Optional[Attachment] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        web_search: bool = False,
        code_interpreter: bool = False,
        file_search: bool = False,
        shell: bool = False,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
    ):
        """
        Creates a model response for the given chat conversation.

        Args:
          prompt: The prompt to generate a response for.

          persona: The persona you want the model to emulate as a description. For example,
              "You are a helpful assistant." The maximum length is 1000 characters.

          model: ID of the model to use. See the
              [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
              table for details on which models work with the Chat API.

          attachment: Attach an image, PDF, document, spreadsheet, or code file.

          (Advanced) frequency_penalty: Controls how much the model should repeat itself.

          (Advanced) presence_penalty: Controls how much the model should talk about the prompt.

          (Advanced) temperature: Controls the randomness of the model.

          (Advanced) top_p: Nucleus sampling.

          web_search: Enable web search to find current information.

          code_interpreter: Enable code interpreter to run Python code.

          file_search: Enable file search over configured vector stores.

          shell: Enable hosted shell command execution (GPT-5 models).

          Please see https://platform.openai.com/docs/guides/text-generation for more information on advanced parameters.
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        for conversation in self.conversation_histories.values():
            if (
                conversation.conversation_starter == ctx.author
                and conversation.channel_id == ctx.channel_id
            ):
                await ctx.send_followup(
                    embed=Embed(
                        title="Error",
                        description="You already have an active conversation in this channel. Please finish it before starting a new one.",
                        color=Colour.red(),
                    )
                )
                return

        # Build input for Responses API
        # For text-only, use a simple string. For multimodal, use content array.
        if attachment is not None:
            input_content = [
                {"type": INPUT_TEXT_TYPE, "text": prompt},
                build_attachment_content_block(attachment.content_type, attachment.url),
            ]
        else:
            input_content = prompt  # Simple string for text-only input
        selected_tool_names = []
        if web_search:
            selected_tool_names.append("web_search")
        if code_interpreter:
            selected_tool_names.append("code_interpreter")
        if file_search:
            selected_tool_names.append("file_search")
        if shell:
            selected_tool_names.append("shell")

        tools, tool_error = self.resolve_selected_tools(selected_tool_names, model)
        if tool_error:
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=tool_error,
                    color=Colour.red(),
                )
            )
            return

        # Build reasoning dict: o-series always use reasoning (default medium);
        # GPT-5.x only send it when the user explicitly sets an effort level.
        if model in REASONING_MODELS:
            reasoning_dict = {"effort": reasoning_effort or REASONING_EFFORT_MEDIUM}
        elif reasoning_effort:
            reasoning_dict = {"effort": reasoning_effort}
        else:
            reasoning_dict = None

        # Create ResponseParameters for the new Responses API
        params = ResponseParameters(
            model=model,
            instructions=persona,
            input=input_content,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            temperature=temperature,
            top_p=top_p,
            reasoning=reasoning_dict,
            verbosity=verbosity,
            tools=tools,
            conversation_starter=ctx.author,
            conversation_id=ctx.interaction.id,
            channel_id=ctx.channel_id,
            response_id_history=[],
        )

        try:
            # Update initial response description based on input parameters
            # Truncate prompt to avoid exceeding Discord's 4096 char embed limit
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
                f"**Presence Penalty:** {params.presence_penalty}\n"
                if params.presence_penalty
                else ""
            )
            description += (
                f"**Temperature:** {params.temperature}\n" if params.temperature else ""
            )
            description += (
                f"**Nucleus Sampling:** {params.top_p}\n" if params.top_p else ""
            )
            if params.reasoning:
                description += f"**Reasoning Effort:** {params.reasoning.get('effort', 'medium')}\n"
            if params.verbosity:
                description += f"**Verbosity:** {params.verbosity}\n"

            self.logger.info(
                f"chat: Conversation parameters initialized for interaction ID {ctx.interaction.id}."
            )

            # API call using Responses API
            response = await self.openai_client.responses.create(**params.to_dict())
            response_text = (
                response.output_text if response.output_text else "No response."
            )
            tool_info = extract_tool_info(response)

            # Store response ID for conversation chaining
            params.previous_response_id = response.id
            params.response_id_history.append(response.id)
            # Clear input after first call (subsequent calls use previous_response_id)
            params.input = []

            # Assemble the response
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
            append_response_embeds(embeds, response_text)

            if tool_info["citations"] or tool_info["file_citations"]:
                append_sources_embed(
                    embeds, tool_info["citations"], tool_info["file_citations"]
                )

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            input_details = getattr(usage, "input_tokens_details", None)
            output_details = getattr(usage, "output_tokens_details", None)
            cached_tokens = getattr(input_details, "cached_tokens", 0) or 0
            reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0
            tool_call_counts = tool_info["tool_call_counts"] or None
            daily_cost = self._track_daily_cost(
                ctx.author.id, model, input_tokens, output_tokens, cached_tokens, tool_call_counts
            )
            if SHOW_COST_EMBEDS:
                append_pricing_embed(
                    embeds, model, input_tokens, output_tokens, daily_cost,
                    cached_tokens, reasoning_tokens, tool_call_counts
                )

            # Strip buttons from any prior conversation's last message
            await self._strip_previous_view(ctx.author)

            self.views[ctx.author] = ButtonView(
                self,
                ctx.author,
                ctx.interaction.id,
                initial_tools=tools,
            )

            reply_msg = await ctx.send_followup(
                embeds=embeds,
                view=self.views[ctx.author],
            )
            self.last_view_messages[ctx.author] = reply_msg

            # Store the conversation as a new entry in the dictionary
            self.conversation_histories[ctx.interaction.id] = params

        except Exception as e:
            error_message = format_openai_error(e)
            await self._cleanup_conversation(ctx.author)
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )

    @openai.command(
        name="image",
        description="Generates image from a prompt.",
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "model",
        description="Choose from the following image generation models. (default: GPT Image 1.5)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT Image 1.5", value="gpt-image-1.5"),
            OptionChoice(name="GPT Image 1", value="gpt-image-1"),
            OptionChoice(name="GPT Image 1 Mini", value="gpt-image-1-mini"),
        ],
    )
    @option(
        "quality",
        description="Image quality. (default: auto)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Auto", value="auto"),
            OptionChoice(name="Low", value="low"),
            OptionChoice(name="Medium", value="medium"),
            OptionChoice(name="High", value="high"),
        ],
    )
    @option(
        "size",
        description="Size of the image. (default: auto)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Auto", value="auto"),
            OptionChoice(name="1024x1024 (square)", value="1024x1024"),
            OptionChoice(name="1024x1536 (portrait)", value="1024x1536"),
            OptionChoice(name="1536x1024 (landscape)", value="1536x1024"),
        ],
    )
    async def image(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "gpt-image-1.5",
        quality: Optional[str] = "auto",
        size: Optional[str] = "auto",
    ):
        """
        Creates an image given a prompt.

        Args:
          prompt: A text description of the desired image(s).
          model: The GPT Image model to use. Defaults to `gpt-image-1.5`.
          quality: The quality of the image (low, medium, high, auto).
          size: The size of the generated image (auto, 1024x1024, 1024x1536, 1536x1024).
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        image_params = ImageGenerationParameters(
            prompt=prompt,
            model=model,
            quality=quality,
            size=size,
        )
        self.logger.info(f"Generating image with model {model}")

        try:
            response = await self.openai_client.images.generate(
                **image_params.to_dict()
            )

            # Extract base64 image data from response
            image_files = []
            for idx, data_item in enumerate(response.data):
                if hasattr(data_item, "b64_json") and data_item.b64_json:
                    image_bytes = base64.b64decode(data_item.b64_json)
                    data = io.BytesIO(image_bytes)
                    file_obj = File(data, f"image{idx}.png")
                    image_files.append(file_obj)

            if not image_files:
                raise Exception("No images were generated.")

            # Truncate prompt to avoid exceeding Discord's 4096 char embed limit
            description = (
                f"**Prompt:** {truncate_text(image_params.prompt, 2000)}\n"
                f"**Model:** {image_params.model}\n"
                f"**Quality:** {image_params.quality}\n"
                f"**Size:** {image_params.size}\n"
            )

            embed = Embed(
                title="Image Generation",
                description=description,
                color=Colour.blue(),
            )
            # Embed the first image inside the embed container
            if image_files:
                embed.set_image(url=f"attachment://{image_files[0].filename}")

            embeds = [embed]
            effective_quality = quality or "auto"
            effective_size = size or "auto"
            image_cost = calculate_image_cost(
                model, effective_quality, effective_size, len(image_files)
            )
            daily_cost = self._track_daily_cost_direct(
                ctx.author.id, "image", model, image_cost,
                f"quality={effective_quality} | size={effective_size} | n={len(image_files)}"
            )
            if SHOW_COST_EMBEDS:
                append_flat_pricing_embed(
                    embeds, image_cost, daily_cost,
                    f"{effective_quality} · {effective_size} · {len(image_files)} image(s)"
                )

            await ctx.send_followup(embeds=embeds, files=image_files)
            self.logger.info(
                f"Successfully generated and sent {len(image_files)} image(s)"
            )

        except Exception as e:
            description = format_openai_error(e)
            self.logger.error(f"Image generation failed: {description}", exc_info=True)
            await ctx.send_followup(
                embed=Embed(title="Error", description=description, color=Colour.red())
            )

    @openai.command(
        name="tts",
        description="Generates lifelike audio from the input text.",
    )
    @option(
        "input",
        description="Text to convert to speech. (max length 4096 characters)",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following TTS models. (default: GPT-4o Mini TTS)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-4o Mini TTS", value="gpt-4o-mini-tts"),
            OptionChoice(name="TTS-1", value="tts-1"),
            OptionChoice(name="TTS-1 HD", value="tts-1-hd"),
        ],
    )
    @option(
        "voice",
        description="The voice to use when generating the audio. (default: Marin)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Marin (Only supported with GPT-4o Mini TTS)", value="marin"),
            OptionChoice(name="Cedar (Only supported with GPT-4o Mini TTS)", value="cedar"),
            OptionChoice(name="Alloy", value="alloy"),
            OptionChoice(name="Ash", value="ash"),
            OptionChoice(
                name="Ballad (Only supported with GPT-4o Mini TTS)", value="ballad"
            ),
            OptionChoice(name="Coral", value="coral"),
            OptionChoice(name="Echo", value="echo"),
            OptionChoice(name="Fable", value="fable"),
            OptionChoice(name="Nova", value="nova"),
            OptionChoice(name="Onyx", value="onyx"),
            OptionChoice(name="Sage", value="sage"),
            OptionChoice(name="Shimmer", value="shimmer"),
            OptionChoice(
                name="Verse (Only supported with GPT-4o Mini TTS)", value="verse"
            ),
        ],
    )
    @option(
        "instructions",
        description="Control the voice of your generated audio with additional instructions. (default: not set)",
        required=False,
        type=str,
    )
    @option(
        "response_format",
        description="The format of the audio file output. (default: mp3)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="MP3", value="mp3"),
            OptionChoice(name="WAV", value="wav"),
            OptionChoice(name="Opus", value="opus"),
            OptionChoice(name="AAC", value="aac"),
            OptionChoice(name="FLAC", value="flac"),
            OptionChoice(name="PCM", value="pcm"),
        ],
    )
    @option(
        "speed",
        description="Speed of the generated audio. (default: 1.0)",
        required=False,
        type=float,
    )
    async def tts(
        self,
        ctx: ApplicationContext,
        input: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        instructions: str = "",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        """
        Generates lifelike audio from the provided text.

        Args:
          input: Text to convert (max 4096 chars).
          model: TTS model (e.g., gpt-4o-mini-tts, tts-1, tts-1-hd).
          voice: Voice to use.
          instructions: Extra voice style instructions (not for tts-1 / tts-1-hd).
          response_format: Audio file format.
          speed: Playback speed multiplier.
        """
        await ctx.defer()

        params = TextToSpeechParameters(
            input, model, voice, instructions, response_format, speed
        )
        speech_file_path = None
        try:
            response = await self.openai_client.audio.speech.create(**params.to_dict())
            speech_file_path = (
                Path(tempfile.gettempdir()) / f"{voice}_speech.{response_format}"
            )
            response.write_to_file(speech_file_path)

            # Truncate text and instructions to avoid exceeding Discord's 4096 char embed limit
            description = (
                f"**Text:** {truncate_text(params.input, 1500)}\n"
                f"**Model:** {params.model}\n"
                f"**Voice:** {params.voice}\n"
                + (
                    f"**Instructions:** {truncate_text(instructions, 500)}\n"
                    if params.instructions
                    else ""
                )
                + f"**Response Format:** {response_format}\n"
                + f"**Speed:** {params.speed}\n"
            )

            embed = Embed(
                title="Text-to-Speech Generation",
                description=description,
                color=Colour.blue(),
            )

            embeds = [embed]
            tts_cost = calculate_tts_cost(model, len(input))
            daily_cost = self._track_daily_cost_direct(
                ctx.author.id, "tts", model, tts_cost,
                f"characters={len(input)} | voice={params.voice}"
            )
            if SHOW_COST_EMBEDS:
                append_flat_pricing_embed(
                    embeds, tts_cost, daily_cost,
                    f"{len(input):,} chars · {params.voice}"
                )

            await ctx.send_followup(embeds=embeds, file=File(speech_file_path))
        except Exception as e:
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=format_openai_error(e),
                    color=Colour.red(),
                )
            )
        finally:
            if speech_file_path and speech_file_path.exists():
                speech_file_path.unlink(missing_ok=True)

    @openai.command(
        name="stt",
        description="Generates text from the input audio.",
    )
    @option(
        "attachment",
        description="Attachment audio file. Max size 25 MB. Supported types: mp3, mp4, mpeg, mpga, m4a, wav, and webm.",
        required=True,
        type=Attachment,
    )
    @option(
        "model",
        description="Model to use for speech-to-text conversion. (default: GPT-4o Transcribe)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-4o Transcribe", value="gpt-4o-transcribe"),
            OptionChoice(name="GPT-4o Mini Transcribe", value="gpt-4o-mini-transcribe"),
            OptionChoice(
                name="GPT-4o Transcribe Diarize", value="gpt-4o-transcribe-diarize"
            ),
            OptionChoice(name="Whisper", value="whisper-1"),
        ],
    )
    @option(
        "action",
        description="Action to perform. (default: Transcription)",
        required=False,
        type=str,
        choices=[
            OptionChoice(
                name="Transcription",
                value="transcription",
            ),
            OptionChoice(
                name="Translation (into English)",
                value="translation",
            ),
        ],
    )
    async def stt(
        self,
        ctx: ApplicationContext,
        attachment: Attachment,
        model: str = "gpt-4o-transcribe",
        action: str = "transcription",
    ):
        """
        Generates text from the input audio.

        Args:
          model: The model to use for speech-to-text conversion. Supported models are `whisper-1`,
                `gpt-4o-transcribe`, and `gpt-4o-mini-transcribe`.

          attachment: The audio file to generate text from. File uploads are currently limited
                to 25 MB and the following input file types are supported: mp3, mp4, mpeg, mpga,
                m4a, wav, and webm.

          action: The action to perform. Supported actions are `transcription` and `translation`.
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        speech_file_path = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as dl_resp:
                    if dl_resp.status != 200:
                        raise Exception("Failed to download the attachment")
                    speech_file_content = await dl_resp.read()

            speech_file_path = Path(tempfile.gettempdir()) / attachment.filename
            speech_file_path.write_bytes(speech_file_content)

            with open(speech_file_path, "rb") as speech_file:
                if action == "transcription":
                    # Diarization models require chunking_strategy
                    if model == "gpt-4o-transcribe-diarize":
                        response = await self.openai_client.audio.transcriptions.create(
                            model=model,
                            file=speech_file,
                            chunking_strategy="auto",
                            response_format="diarized_json",
                        )
                    else:
                        response = await self.openai_client.audio.transcriptions.create(
                            model=model, file=speech_file
                        )
                else:  # translation (only whisper-1 supports translations)
                    response = await self.openai_client.audio.translations.create(
                        model="whisper-1", file=speech_file
                    )

            # Format diarized output with speaker labels, or plain text for other models
            if model == "gpt-4o-transcribe-diarize" and hasattr(response, "segments"):
                lines = []
                for seg in response.segments:
                    speaker = getattr(seg, "speaker", "Unknown")
                    text = getattr(seg, "text", "").strip()
                    if text:
                        lines.append(f"**{speaker}:** {text}")
                transcription_text = truncate_text("\n".join(lines), 3500)
            else:
                transcription_text = truncate_text(
                    getattr(response, "text", None), 3500
                )
            description = (
                f"**Model:** {model}\n"
                + f"**Action:** {action}\n"
                + (f"**Output:**\n{transcription_text}\n" if transcription_text else "")
            )
            embed = Embed(
                title="Speech-to-Text", description=description, color=Colour.blue()
            )

            embeds = [embed]
            actual_model = "whisper-1" if action != "transcription" else model
            est_duration = estimate_audio_duration_seconds(
                attachment.size, attachment.filename
            )
            stt_cost = calculate_stt_cost(actual_model, est_duration)
            daily_cost = self._track_daily_cost_direct(
                ctx.author.id, "stt", actual_model, stt_cost,
                f"file={attachment.filename} | size={attachment.size}"
                f" | est_duration={est_duration:.1f}s"
            )
            if SHOW_COST_EMBEDS:
                append_flat_pricing_embed(
                    embeds, stt_cost, daily_cost,
                    f"~{est_duration:.0f}s audio · {actual_model}"
                )

            await ctx.send_followup(embeds=embeds, file=File(speech_file_path))
        except Exception as e:
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=format_openai_error(e),
                    color=Colour.red(),
                )
            )
        finally:
            if speech_file_path and speech_file_path.exists():
                speech_file_path.unlink(missing_ok=True)

    @openai.command(
        name="video",
        description="Generates a video based on a prompt using Sora.",
    )
    @option(
        "prompt",
        description="Prompt for video generation (describe shot type, subject, action, setting, lighting).",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose Sora model for video generation. (default: Sora 2)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Sora 2 (Fast)", value="sora-2"),
            OptionChoice(name="Sora 2 Pro (High Quality)", value="sora-2-pro"),
        ],
    )
    @option(
        "size",
        description="Resolution of the generated video. (default: 1280x720)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Landscape (1280x720)", value="1280x720"),
            OptionChoice(name="Portrait (720x1280)", value="720x1280"),
            OptionChoice(name="Wide Landscape (1792x1024)", value="1792x1024"),
            OptionChoice(name="Tall Portrait (1024x1792)", value="1024x1792"),
            OptionChoice(name="1080p Landscape (1920x1080, Pro only)", value="1920x1080"),
            OptionChoice(name="1080p Portrait (1080x1920, Pro only)", value="1080x1920"),
        ],
    )
    @option(
        "seconds",
        description="Duration of the video in seconds. (default: 8)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="4 seconds", value="4"),
            OptionChoice(name="8 seconds", value="8"),
            OptionChoice(name="12 seconds", value="12"),
            OptionChoice(name="16 seconds", value="16"),
            OptionChoice(name="20 seconds", value="20"),
        ],
    )
    async def video(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
    ):
        """
        Generates a video from a prompt using OpenAI's Sora model.

        Args:
            prompt: A text description of the desired video. For best results, describe
                shot type, subject, action, setting, and lighting.
            model: The Sora model to use. 'sora-2' is faster for iteration,
                'sora-2-pro' produces higher quality output.
            size: The resolution of the generated video.
            seconds: The duration of the video in seconds.
        """
        await ctx.defer()

        # 1080p sizes require sora-2-pro
        if size in ("1920x1080", "1080x1920") and model != "sora-2-pro":
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description="1080p resolutions (1920x1080, 1080x1920) are only supported with Sora 2 Pro.",
                    color=Colour.red(),
                )
            )
            return

        video_params = VideoGenerationParameters(
            prompt=prompt,
            model=model,
            size=size,
            seconds=seconds,
        )

        video_file_path = None
        try:
            # Start the video generation job
            self.logger.info(f"Starting video generation with model {model}")
            video = await self.openai_client.videos.create(**video_params.to_dict())

            self.logger.info(f"Video job started: {video.id}, status: {video.status}")

            # Poll for completion
            progress = (
                video.progress if hasattr(video, "progress") and video.progress else 0
            )
            poll_count = 0
            max_polls = 60  # 10 minutes with 10-second intervals

            while video.status in ("queued", "in_progress"):
                if poll_count >= max_polls:
                    raise Exception("Video generation timed out after 10 minutes")

                await asyncio.sleep(10)
                video = await self.openai_client.videos.retrieve(video.id)
                progress = (
                    video.progress
                    if hasattr(video, "progress") and video.progress
                    else 0
                )
                poll_count += 1
                self.logger.debug(
                    f"Poll {poll_count}: status={video.status}, progress={progress}%"
                )

            if video.status == "failed":
                raise Exception(
                    "Video generation failed. Please try a different prompt."
                )

            if video.status != "completed":
                raise Exception(f"Unexpected video status: {video.status}")

            self.logger.info(f"Video generation completed: {video.id}")

            # Download the video
            content = await self.openai_client.videos.download_content(video.id)
            video_bytes = await content.aread()

            video_file_path = Path(tempfile.gettempdir()) / f"video_{video.id}.mp4"
            video_file_path.write_bytes(video_bytes)

            # Build response embed
            # Truncate prompt to avoid exceeding Discord's 4096 char embed limit
            description = f"**Prompt:** {truncate_text(video_params.prompt, 2000)}\n"
            description += f"**Model:** {video_params.model}\n"
            description += f"**Size:** {video_params.size}\n"
            description += f"**Duration:** {video_params.seconds} seconds\n"

            embed = Embed(
                title="Video Generation",
                description=description,
                color=Colour.blue(),
            )

            embeds = [embed]
            vid_seconds = int(video_params.seconds)
            vid_cost = calculate_video_cost(model, vid_seconds)
            daily_cost = self._track_daily_cost_direct(
                ctx.author.id, "video", model, vid_cost,
                f"seconds={vid_seconds} | size={video_params.size}"
            )
            if SHOW_COST_EMBEDS:
                append_flat_pricing_embed(
                    embeds, vid_cost, daily_cost,
                    f"{vid_seconds}s · {video_params.size}"
                )

            await ctx.send_followup(embeds=embeds, file=File(video_file_path))
            self.logger.info("Successfully sent generated video")

        except Exception as e:
            error_message = format_openai_error(e)
            self.logger.error(
                f"Video generation failed: {error_message}", exc_info=True
            )
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )
        finally:
            if video_file_path and video_file_path.exists():
                video_file_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # /openai research — Deep Research via background Responses API
    # ------------------------------------------------------------------

    @openai.command(
        name="research",
        description="Run a deep research task that searches, reads, and synthesizes a detailed report.",
    )
    @option(
        "prompt",
        description="Research question or topic to investigate.",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose the deep research model. (default: o3 Deep Research)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="o3 Deep Research", value="o3-deep-research"),
            OptionChoice(name="o4 Mini Deep Research", value="o4-mini-deep-research"),
        ],
    )
    @option(
        "file_search",
        description="Also search your uploaded document stores (File Search / RAG). (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "code_interpreter",
        description="Allow the model to write and run code for analysis. (default: false)",
        required=False,
        type=bool,
    )
    async def research(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "o3-deep-research",
        file_search: bool = False,
        code_interpreter: bool = False,
    ):
        """
        Runs a deep research task using OpenAI's deep research models.

        The model autonomously searches the web, reads pages, and optionally
        queries your vector stores or runs code, then synthesizes a detailed
        report with inline citations.

        Args:
            prompt: Research question or topic to investigate.
            model: The deep research model to use.
            file_search: Whether to also search configured vector stores.
            code_interpreter: Whether to allow code execution for analysis.
        """
        await ctx.defer()

        research_params = ResearchParameters(
            prompt=prompt,
            model=model,
            file_search=file_search,
            code_interpreter=code_interpreter,
        )

        try:
            # Build tools list — web_search is always required
            tools: List[Dict[str, Any]] = [TOOL_WEB_SEARCH.copy()]

            if file_search:
                if not OPENAI_VECTOR_STORE_IDS:
                    await ctx.send_followup(
                        embed=Embed(
                            title="Error",
                            description="File search requires OPENAI_VECTOR_STORE_IDS to be set in your .env.",
                            color=Colour.red(),
                        )
                    )
                    return
                tool: Dict[str, Any] = TOOL_FILE_SEARCH.copy()
                tool["vector_store_ids"] = OPENAI_VECTOR_STORE_IDS.copy()
                tools.append(tool)

            if code_interpreter:
                tools.append(TOOL_CODE_INTERPRETER.copy())

            # Send initial "researching" embed so the user knows it's working
            description = f"**Prompt:** {truncate_text(prompt, 2000)}\n"
            description += f"**Model:** {model}\n"
            tool_names = ["web_search"]
            if file_search:
                tool_names.append("file_search")
            if code_interpreter:
                tool_names.append("code_interpreter")
            description += f"**Tools:** {', '.join(tool_names)}\n"
            description += "\nResearching... this may take several minutes."

            status_msg = await ctx.send_followup(
                embed=Embed(
                    title="Deep Research",
                    description=description,
                    color=Colour.green(),
                )
            )

            self.logger.info(f"Starting deep research with model {model}")

            # Create background research request
            response = await self.openai_client.responses.create(
                **research_params.to_dict(tools)
            )

            self.logger.info(
                f"Deep research started: {response.id}, status: {response.status}"
            )

            # Poll for completion
            max_wait_time = 1200  # 20 minutes
            start_time = time.time()
            poll_interval = 15

            while response.status in ("queued", "in_progress"):
                if time.time() - start_time > max_wait_time:
                    raise Exception("Deep research timed out after 20 minutes.")

                await asyncio.sleep(poll_interval)
                response = await self.openai_client.responses.retrieve(response.id)
                self.logger.debug(
                    f"Research poll: status={response.status}, "
                    f"elapsed={int(time.time() - start_time)}s"
                )

            if response.status == "failed":
                error = getattr(response, "error", None)
                error_msg = getattr(error, "message", None) if error else None
                raise Exception(
                    error_msg or "Deep research failed. Please try a different prompt."
                )

            if response.status == "cancelled":
                raise Exception("Deep research was cancelled.")

            if response.status != "completed":
                raise Exception(f"Unexpected research status: {response.status}")

            self.logger.info(
                f"Deep research completed: {response.id}, "
                f"elapsed={int(time.time() - start_time)}s"
            )

            # Extract the report text
            response_text = (
                response.output_text if response.output_text else None
            )

            if not response_text:
                await status_msg.edit(
                    embed=Embed(
                        title="Deep Research",
                        description="The research model did not produce any output. Please try again with a different prompt.",
                        color=Colour.orange(),
                    )
                )
                return

            # Extract citations
            tool_info = extract_tool_info(response)

            # Build header embed
            elapsed = int(time.time() - start_time)
            final_description = f"**Prompt:** {truncate_text(prompt, 2000)}\n"
            final_description += f"**Model:** {model}\n"
            final_description += f"**Tools:** {', '.join(tool_names)}\n"
            final_description += f"**Time:** {elapsed // 60}m {elapsed % 60}s\n"

            header_embed = Embed(
                title="Deep Research",
                description=final_description,
                color=Colour.blue(),
            )

            # Build supplementary embeds (sources, pricing)
            extra_embeds: List[Embed] = []

            if tool_info["citations"] or tool_info["file_citations"]:
                append_sources_embed(
                    extra_embeds, tool_info["citations"], tool_info["file_citations"]
                )

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            input_details = getattr(usage, "input_tokens_details", None)
            output_details = getattr(usage, "output_tokens_details", None)
            cached_tokens = getattr(input_details, "cached_tokens", 0) or 0
            reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0
            tool_call_counts = tool_info["tool_call_counts"] or None
            daily_cost = self._track_daily_cost(
                ctx.author.id, model, input_tokens, output_tokens, cached_tokens,
                tool_call_counts, command="research"
            )
            if SHOW_COST_EMBEDS:
                append_pricing_embed(
                    extra_embeds, model, input_tokens, output_tokens, daily_cost,
                    cached_tokens, reasoning_tokens, tool_call_counts
                )

            # Edit the original status message with the header embed
            await status_msg.edit(embed=header_embed)

            # Send the report as a downloadable .md file
            report_file = File(
                io.BytesIO(response_text.encode("utf-8")),
                filename="research_report.md",
            )
            await ctx.send_followup(
                embeds=extra_embeds if extra_embeds else [],
                file=report_file,
            )

        except Exception as e:
            error_message = format_openai_error(e)
            self.logger.error(
                f"Deep research failed: {error_message}", exc_info=True
            )
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )
