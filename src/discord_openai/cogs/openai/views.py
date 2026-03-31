import logging
from collections.abc import Awaitable, Callable
from typing import (
    Any,
)

from discord import (
    ButtonStyle,
    Interaction,
    SelectOption,
)
from discord.ui import Button, Select, View, button

from .tooling import get_tool_select_max_values, get_tool_select_options, is_known_tool


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
        conversation_starter_id,
        conversation_id,
        initial_tools=None,
        get_conversation: Callable[[int], Any | None],
        on_regenerate: Callable[[Interaction, Any], Awaitable[None]],
        on_stop: Callable[[int, Any], Awaitable[None]],
        on_tools_changed: Callable[[list[str], Any], tuple[set[str], str | None]],
    ):
        super().__init__(timeout=None)
        self.conversation_starter_id = conversation_starter_id
        self.conversation_id = conversation_id
        self._get_conversation = get_conversation
        self._on_regenerate = on_regenerate
        self._on_stop = on_stop
        self._on_tools_changed = on_tools_changed
        self._add_tool_select(initial_tools)

    def _add_tool_select(self, initial_tools=None):
        selected_tool_types: set[str] = set()
        for tool in initial_tools or []:
            if not isinstance(tool, dict):
                continue
            tool_type = tool.get("type")
            if isinstance(tool_type, str):
                selected_tool_types.add(tool_type)

        tool_select = Select(
            placeholder="Tools",
            options=[
                SelectOption(**option)
                for option in get_tool_select_options(selected_tool_types)
            ],
            min_values=0,
            max_values=get_tool_select_max_values(),
            row=1,
        )

        async def _tool_callback(interaction: Interaction):
            await self.tool_select_callback(interaction, tool_select)

        tool_select.callback = _tool_callback
        self.add_item(tool_select)

    async def tool_select_callback(self, interaction: Interaction, tool_select: Select):
        try:
            user = interaction.user
            if user is None or user.id != self.conversation_starter_id:
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

            selected_values = [value for value in tool_select.values if is_known_tool(value)]

            active_names, error_message = self._on_tools_changed(selected_values, conversation)
            if error_message:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Update Select dropdown defaults
            for child in self.children:
                if isinstance(child, Select):
                    for option in child.options:
                        option.default = option.value in active_names
                    break

            status = ", ".join(sorted(active_names)) if active_names else "none"
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
            user = interaction.user
            if user is None or user.id != self.conversation_starter_id:
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

            if conversation.last_user_input is None:
                await interaction.followup.send(
                    "No saved prompt was found for this conversation.", ephemeral=True
                )
                return

            await self._on_regenerate(interaction, conversation)
            await interaction.followup.send("Response regenerated.", ephemeral=True, delete_after=3)
        except Exception as e:
            await _send_interaction_error(interaction, "regenerating the response", e)

    @button(emoji="⏯️", style=ButtonStyle.gray, row=0)
    async def play_pause_button(self, _: Button, interaction: Interaction):
        """Pause or resume the conversation."""
        try:
            user = interaction.user
            if user is None or user.id != self.conversation_starter_id:
                await interaction.response.send_message(
                    "You are not allowed to pause the conversation.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is not None:
                conversation.paused = not conversation.paused
                conversation.touch()
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
            user = interaction.user
            if user is None or user.id != self.conversation_starter_id:
                await interaction.response.send_message(
                    "You are not allowed to end this conversation.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is not None:
                await self._on_stop(self.conversation_id, self.conversation_starter_id)
                await interaction.response.send_message(
                    "Conversation ended.", ephemeral=True, delete_after=3
                )
            else:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
        except Exception as e:
            await _send_interaction_error(interaction, "ending the conversation", e)


class McpApprovalView(View):
    def __init__(
        self,
        *,
        conversation_starter_id,
        conversation_id,
        get_conversation: Callable[[int], Any | None],
        on_approve: Callable[[Interaction, Any], Awaitable[None]],
        on_deny: Callable[[Interaction, Any], Awaitable[None]],
        on_stop: Callable[[int, Any], Awaitable[None]],
    ):
        super().__init__(timeout=None)
        self.conversation_starter_id = conversation_starter_id
        self.conversation_id = conversation_id
        self._get_conversation = get_conversation
        self._on_approve = on_approve
        self._on_deny = on_deny
        self._on_stop = on_stop

    def _get_pending_conversation(self, interaction: Interaction):
        user = interaction.user
        if user is None or user.id != self.conversation_starter_id:
            return None, "You are not allowed to approve MCP tool calls for this conversation."

        conversation = self._get_conversation(self.conversation_id)
        if conversation is None:
            return None, "No active conversation found."
        if not getattr(conversation, "pending_mcp_approval", None):
            return None, "No pending MCP approval request was found."
        return conversation, None

    @button(label="Approve MCP", style=ButtonStyle.green, row=0)
    async def approve_button(self, _: Button, interaction: Interaction):
        try:
            conversation, error_message = self._get_pending_conversation(interaction)
            if error_message:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            await self._on_approve(interaction, conversation)
        except Exception as e:
            await _send_interaction_error(interaction, "approving the MCP request", e)

    @button(label="Deny MCP", style=ButtonStyle.red, row=0)
    async def deny_button(self, _: Button, interaction: Interaction):
        try:
            conversation, error_message = self._get_pending_conversation(interaction)
            if error_message:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            await self._on_deny(interaction, conversation)
        except Exception as e:
            await _send_interaction_error(interaction, "denying the MCP request", e)

    @button(emoji="⏹️", style=ButtonStyle.blurple, row=0)
    async def stop_button(self, _: Button, interaction: Interaction):
        try:
            user = interaction.user
            if user is None or user.id != self.conversation_starter_id:
                await interaction.response.send_message(
                    "You are not allowed to end this conversation.", ephemeral=True
                )
                return

            conversation = self._get_conversation(self.conversation_id)
            if conversation is not None:
                await self._on_stop(self.conversation_id, self.conversation_starter_id)
                await interaction.response.send_message(
                    "Conversation ended.", ephemeral=True, delete_after=3
                )
            else:
                await interaction.response.send_message(
                    "No active conversation found.", ephemeral=True
                )
        except Exception as e:
            await _send_interaction_error(interaction, "ending the conversation", e)
