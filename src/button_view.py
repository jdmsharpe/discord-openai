import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import (
    Any,
    Protocol,
    cast,
)

from discord import (
    ButtonStyle,
    Interaction,
    SelectOption,
)
from discord.ui import Button, Select, View, button

from util import AVAILABLE_TOOLS


class HistoryReadableChannel(Protocol):
    def history(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]: ...


async def _send_interaction_error(interaction: Interaction, context: str, error: Exception) -> None:
    """Log an error and send the user a safe ephemeral message."""
    logging.error(f"Error in {context}: {error}", exc_info=True)
    msg = f"An error occurred while {context}."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


class ButtonView(View):
    def __init__(
        self,
        *,
        conversation_starter,
        conversation_id,
        initial_tools=None,
        get_conversation: Callable[[int], Any | None],
        on_regenerate: Callable[[Any, Any], Awaitable[None]],
        on_stop: Callable[[int, Any], Awaitable[None]],
        on_tools_changed: Callable[[list[str], str], tuple[list[dict[str, Any]], str | None]],
    ):
        super().__init__(timeout=None)
        self.conversation_starter = conversation_starter
        self.conversation_id = conversation_id
        self._get_conversation = get_conversation
        self._on_regenerate = on_regenerate
        self._on_stop = on_stop
        self._on_tools_changed = on_tools_changed
        self._add_tool_select(initial_tools)

    def _add_tool_select(self, initial_tools=None):
        selected_tool_types = {
            tool.get("type")
            for tool in (initial_tools or [])
            if isinstance(tool, dict) and tool.get("type")
        }

        tool_select = Select(
            placeholder="Tools",
            options=[
                SelectOption(
                    label="Web Search",
                    value="web_search",
                    description="Search the web for current information.",
                    default="web_search" in selected_tool_types,
                ),
                SelectOption(
                    label="Code Interpreter",
                    value="code_interpreter",
                    description="Run Python code in a sandbox.",
                    default="code_interpreter" in selected_tool_types,
                ),
                SelectOption(
                    label="File Search",
                    value="file_search",
                    description="Search your indexed vector store files.",
                    default="file_search" in selected_tool_types,
                ),
                SelectOption(
                    label="Shell",
                    value="shell",
                    description="Run commands in an OpenAI hosted container.",
                    default="shell" in selected_tool_types,
                ),
            ],
            min_values=0,
            max_values=4,
            row=1,
        )

        async def _tool_callback(interaction: Interaction):
            await self.tool_select_callback(interaction, tool_select)

        tool_select.callback = _tool_callback
        self.add_item(tool_select)

    async def tool_select_callback(self, interaction: Interaction, tool_select: Select):
        try:
            if interaction.user != self.conversation_starter:
                await interaction.response.send_message(
                    "You are not allowed to change tools for this conversation.",
                    ephemeral=True,
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is None:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
                return

            selected_values = [value for value in tool_select.values if value in AVAILABLE_TOOLS]

            tools, error_message = self._on_tools_changed(selected_values, conversation.model)
            if error_message:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            conversation.tools = tools

            status = ", ".join(selected_values) if selected_values else "none"
            await interaction.response.send_message(
                f"Tools updated: {status}.",
                ephemeral=True,
                delete_after=3,
            )
        except Exception as e:
            await _send_interaction_error(interaction, "updating tools", e)

    @button(emoji="🔄", style=ButtonStyle.green, row=0)
    async def regenerate_button(self, _: Button, interaction: Interaction):
        """Regenerate the last response for the current conversation."""
        logging.info("Regenerate button clicked.")
        try:
            if interaction.user != self.conversation_starter:
                await interaction.response.send_message(
                    "You are not allowed to regenerate the response.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is None:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Go back to the previous response ID (skip the last exchange)
            if len(conversation.response_id_history) >= 1:
                conversation.response_id_history.pop()
                conversation.previous_response_id = (
                    conversation.response_id_history[-1]
                    if conversation.response_id_history
                    else None
                )

            # Get the last user message from the channel history
            channel = interaction.channel
            if channel is None or not hasattr(channel, "history"):
                await interaction.followup.send("Cannot access channel history.", ephemeral=True)
                return
            history_channel = cast(HistoryReadableChannel, channel)
            messages = [m async for m in history_channel.history(limit=2)]
            if len(messages) < 2:
                await interaction.followup.send(
                    "Couldn't find the message to regenerate.", ephemeral=True
                )
                return

            user_message = messages[1]

            await self._on_regenerate(user_message, conversation)
            await interaction.followup.send("Response regenerated.", ephemeral=True, delete_after=3)
        except Exception as e:
            await _send_interaction_error(interaction, "regenerating the response", e)

    @button(emoji="⏯️", style=ButtonStyle.gray, row=0)
    async def play_pause_button(self, _: Button, interaction: Interaction):
        """Pause or resume the conversation."""
        try:
            if interaction.user != self.conversation_starter:
                await interaction.response.send_message(
                    "You are not allowed to pause the conversation.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is not None:
                conversation.paused = not conversation.paused
                status = "paused" if conversation.paused else "resumed"
                await interaction.response.send_message(
                    f"Conversation {status}. Press again to toggle.",
                    ephemeral=True,
                    delete_after=3,
                )
            else:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
        except Exception as e:
            await _send_interaction_error(interaction, "toggling pause", e)

    @button(emoji="⏹️", style=ButtonStyle.blurple, row=0)
    async def stop_button(self, _: Button, interaction: Interaction):
        """End the conversation."""
        try:
            if interaction.user != self.conversation_starter:
                await interaction.response.send_message(
                    "You are not allowed to end this conversation.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is not None:
                await self._on_stop(self.conversation_id, self.conversation_starter)
                await interaction.response.send_message(
                    "Conversation ended.", ephemeral=True, delete_after=3
                )
            else:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
        except Exception as e:
            await _send_interaction_error(interaction, "ending the conversation", e)
