from discord import (
    ButtonStyle,
    Interaction,
    SelectOption,
)
from discord.ui import button, Button, Select, View
import logging
from typing import Any, AsyncIterator, Protocol, cast
from util import AVAILABLE_TOOLS


class HistoryReadableChannel(Protocol):
    def history(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        ...


class ButtonView(View):
    def __init__(self, cog, conversation_starter, conversation_id, initial_tools=None):
        """
        Initialize the ButtonView class.
        """
        super().__init__(timeout=None)
        self.cog = cog
        self.conversation_starter = conversation_starter
        self.conversation_id = conversation_id
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
        if interaction.user != self.conversation_starter:
            await interaction.response.send_message(
                "You are not allowed to change tools for this conversation.",
                ephemeral=True,
            )
            return

        if self.conversation_id not in self.cog.conversation_histories:
            await interaction.response.send_message(
                "No active conversation found.", ephemeral=True
            )
            return

        selected_values = [
            value for value in tool_select.values if value in AVAILABLE_TOOLS
        ]
        conversation = self.cog.conversation_histories[self.conversation_id]
        if not hasattr(self.cog, "resolve_selected_tools"):
            await interaction.response.send_message(
                "Tool configuration is unavailable.",
                ephemeral=True,
            )
            return

        tools, error_message = self.cog.resolve_selected_tools(
            selected_values, conversation.model
        )
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

    @button(emoji="🔄", style=ButtonStyle.green, row=0)
    async def regenerate_button(self, _: Button, interaction: Interaction):
        """
        Regenerate the last response for the current conversation.

        Args:
            button (Button): The button that was clicked.
            interaction (Interaction): The interaction object.
        """
        logging.info("Regenerate button clicked.")
        try:
            # Check if the interaction user is the one who started the conversation
            if interaction.user != self.conversation_starter:
                await interaction.response.send_message(
                    "You are not allowed to regenerate the response.", ephemeral=True
                )
                return

            if self.conversation_id not in self.cog.conversation_histories:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Get the conversation and revert to previous response state
            conversation = self.cog.conversation_histories[self.conversation_id]

            # Go back to the previous response ID (skip the last exchange)
            if len(conversation.response_id_history) >= 1:
                # Remove the last response ID
                conversation.response_id_history.pop()
                # Set previous_response_id to the one before that (or None if at start)
                conversation.previous_response_id = (
                    conversation.response_id_history[-1]
                    if conversation.response_id_history
                    else None
                )

            # For now, get the last user message from the channel history
            channel = interaction.channel
            if channel is None or not hasattr(channel, "history"):
                await interaction.followup.send(
                    "Cannot access channel history.", ephemeral=True
                )
                return
            history_channel = cast(HistoryReadableChannel, channel)
            messages = [m async for m in history_channel.history(limit=2)]
            if len(messages) < 2:
                await interaction.followup.send(
                    "Couldn't find the message to regenerate.", ephemeral=True
                )
                return

            user_message = messages[1]

            await self.cog.handle_new_message_in_conversation(
                user_message, conversation
            )
            await interaction.followup.send(
                "Response regenerated.", ephemeral=True, delete_after=3
            )
        except Exception as e:
            logging.error(f"Error in regenerate_button: {str(e)}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(
                    "An error occurred while regenerating the response.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "An error occurred while regenerating the response.", ephemeral=True
                )

    @button(emoji="⏯️", style=ButtonStyle.gray, row=0)
    async def play_pause_button(self, _: Button, interaction: Interaction):
        """
        Pause or resume the conversation.

        Args:
            button (Button): The button that was clicked.
            interaction (Interaction): The interaction object.
        """
        # Check if the interaction user is the one who started the conversation
        if interaction.user != self.conversation_starter:
            await interaction.response.send_message(
                "You are not allowed to pause the conversation.", ephemeral=True
            )
            return

        # Toggle the paused state
        if self.conversation_id in self.cog.conversation_histories:
            conversation = self.cog.conversation_histories[self.conversation_id]
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

    @button(emoji="⏹️", style=ButtonStyle.blurple, row=0)
    async def stop_button(self, button: Button, interaction: Interaction):
        """
        End the conversation.

        Args:
            button (Button): The button that was clicked.
            interaction (Interaction): The interaction object.
        """
        # Check if the interaction user is the one who started the conversation
        if interaction.user != self.conversation_starter:
            await interaction.response.send_message(
                "You are not allowed to end this conversation.", ephemeral=True
            )
            return

        # End the conversation
        if self.conversation_id in self.cog.conversation_histories:
            del self.cog.conversation_histories[self.conversation_id]
            button.disabled = True  # Disable the button
            await interaction.response.send_message(
                "Conversation ended.", ephemeral=True, delete_after=3
            )
        else:
            await interaction.response.send_message(
                "No active conversation found.", ephemeral=True
            )

