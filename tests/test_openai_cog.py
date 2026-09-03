import json
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from discord import Bot, Intents

from discord_openai import OpenAICog
from discord_openai.cogs.openai.command_options import (
    CHAT_MODEL_CHOICES,
    IMAGE_BACKGROUND_CHOICES,
    IMAGE_MODEL_CHOICES,
    REASONING_EFFORT_CHOICES,
    REASONING_MODE_CHOICES,
    RESEARCH_MODEL_CHOICES,
    SERVICE_TIER_CHOICES,
    STT_MODEL_CHOICES,
    TTS_MODEL_CHOICES,
    TTS_VOICE_CHOICES,
    VIDEO_MODEL_CHOICES,
)
from discord_openai.config.pricing import TTS_PRICING_PER_CHAR
from discord_openai.util import (
    MODEL_SUPPORTED_TTS_VOICES,
    PRO_MODE_MODELS,
    REASONING_MODELS,
    RICH_TTS_MODELS,
    SUPPORTED_REASONING_EFFORTS,
)


def _serialize_command_group_payload(group):
    return {
        "name": group.name,
        "description": group.description,
        "options": [
            {
                "name": command.name,
                "description": command.description,
                "options": [
                    option.to_dict() for option in command.options if option.input_type is not None
                ],
                "type": 1,
                "nsfw": False,
            }
            for command in group.subcommands
        ],
        "nsfw": False,
    }


class TestOpenAICog:
    @pytest.fixture(autouse=True)
    def setup(self):
        intents = Intents.default()
        intents.presences = False
        intents.members = True
        intents.message_content = True
        self.bot: Any = Bot(intents=intents)
        self.bot.add_cog(OpenAICog(bot=self.bot))
        self.bot.owner_id = 1234567890

    async def test_resolve_selected_tools_file_search_requires_vector_store(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        with patch("discord_openai.cogs.openai.tool_registry.OPENAI_VECTOR_STORE_IDS", []):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        assert tools == []
        assert "OPENAI_VECTOR_STORE_IDS" in error

    async def test_resolve_selected_tools_file_search_success(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        with patch("discord_openai.cogs.openai.tool_registry.OPENAI_VECTOR_STORE_IDS", ["vs_123"]):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        assert error is None
        assert tools[0]["type"] == "file_search"
        assert tools[0]["vector_store_ids"] == ["vs_123"]
        assert tools[0]["max_num_results"] == 5

    async def test_resolve_selected_tools_shell_model_guard(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        tools, error = cog.resolve_selected_tools(["shell"], "gpt-4.1")
        assert tools == []
        assert "GPT-5" in error

        tools, error = cog.resolve_selected_tools(["shell"], "gpt-5.2")
        assert error is None
        assert tools[0]["type"] == "shell"

    async def test_on_ready_logs_bot_user_id_instead_of_owner_id(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        cog.logger = Mock()
        self.bot.sync_commands = AsyncMock()
        cog._runtime_cleanup_task.start = Mock()
        cog._runtime_cleanup_task.is_running = Mock(return_value=False)

        self.bot.owner_id = 999888777
        bot_user = Mock(id=111222333)
        bot_user.__str__ = Mock(return_value="TestBot")

        with patch.object(type(self.bot), "user", new_callable=PropertyMock) as user_property:
            user_property.return_value = bot_user
            await cog.on_ready()

        assert any(
            "Logged in as TestBot (ID: 111222333)" in call.args[0]
            for call in cog.logger.info.call_args_list
        )
        assert not any(
            "Logged in as TestBot (ID: 999888777)" in call.args[0]
            for call in cog.logger.info.call_args_list
        )
        assert any(
            "Bot owner ID (diagnostic): 999888777" in call.args[0]
            for call in cog.logger.debug.call_args_list
        )

    async def test_on_ready_logs_unknown_user_id_when_bot_user_is_none(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        cog.logger = Mock()
        self.bot.sync_commands = AsyncMock()
        cog._runtime_cleanup_task.start = Mock()
        cog._runtime_cleanup_task.is_running = Mock(return_value=False)

        with patch.object(type(self.bot), "user", new_callable=PropertyMock) as user_property:
            user_property.return_value = None
            await cog.on_ready()

        assert any(
            "Logged in as None (ID: unknown)" in call.args[0]
            for call in cog.logger.info.call_args_list
        )

    def test_command_defaults_are_unchanged(self):
        assert OpenAICog.chat.callback.__defaults__ == (
            "You are a helpful assistant.",
            "gpt-5.6-sol",
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            False,
            False,
            False,
            None,
            None,
        )
        assert OpenAICog.image.callback.__defaults__ == (
            "gpt-image-2",
            "auto",
            "auto",
            "auto",
            None,
        )
        assert OpenAICog.tts.callback.__defaults__ == ("gpt-4o-mini-tts", "marin", "", "mp3", 1.0)
        assert OpenAICog.stt.callback.__defaults__ == ("gpt-transcribe", "transcription")
        assert OpenAICog.video.callback.__defaults__ == ("sora-2", "1280x720", "8")
        assert OpenAICog.research.callback.__defaults__ == ("gpt-5.6-sol", False, False)

    def test_registered_command_groups_fit_discord_size_limit(self):
        """Discord rejects any single top-level command payload over 8000 bytes."""

        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        commands_by_name = {command.name: command for command in cog.get_commands()}

        assert set(commands_by_name) == {"openai", "openai-media", "openai-tools"}
        assert [command.name for command in commands_by_name["openai"].subcommands] == [
            "check_permissions",
            "chat",
        ]
        assert [command.name for command in commands_by_name["openai-media"].subcommands] == [
            "image",
            "video",
        ]
        assert [command.name for command in commands_by_name["openai-tools"].subcommands] == [
            "tts",
            "stt",
            "research",
        ]

        payload_sizes = {
            name: len(
                json.dumps(
                    _serialize_command_group_payload(command),
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            for name, command in commands_by_name.items()
        }

        assert payload_sizes["openai"] < 8000
        assert payload_sizes["openai-media"] < 8000
        assert payload_sizes["openai-tools"] < 8000

    def test_critical_choice_values_present(self):
        assert any(choice.value == "gpt-5.6-sol" for choice in CHAT_MODEL_CHOICES)
        assert any(choice.value == "gpt-5.4" for choice in CHAT_MODEL_CHOICES)
        assert any(choice.value == "gpt-image-1.5" for choice in IMAGE_MODEL_CHOICES)
        assert any(choice.value == "marin" for choice in TTS_VOICE_CHOICES)
        assert any(choice.value == "gpt-transcribe" for choice in STT_MODEL_CHOICES)
        assert any(choice.value == "sora-2" for choice in VIDEO_MODEL_CHOICES)
        assert any(choice.value == "gpt-5.6-sol" for choice in RESEARCH_MODEL_CHOICES)
        assert any(choice.value == "gpt-5.5" for choice in RESEARCH_MODEL_CHOICES)

    def test_reasoning_effort_choice_set(self):
        values = {choice.value for choice in REASONING_EFFORT_CHOICES}
        assert values == {"none", "minimal", "low", "medium", "high", "xhigh", "max"}

    def test_reasoning_mode_choice_set(self):
        values = {choice.value for choice in REASONING_MODE_CHOICES}
        assert values == {"standard", "pro"}

    def test_service_tier_choice_set(self):
        """`standard` is never sent (mirrors reasoning_mode); `fast` is the only tier offered —
        `ultrafast` is Sol-only, access-controlled and unpriced."""
        values = [choice.value for choice in SERVICE_TIER_CHOICES]
        assert values == ["standard", "fast"]

    def test_image_background_choice_set(self):
        """Every GPT Image model returned an RGBA PNG for `transparent` (probed 2026-09-03)."""
        values = [choice.value for choice in IMAGE_BACKGROUND_CHOICES]
        assert values == ["auto", "opaque", "transparent"]
        image_options = [opt.name for opt in OpenAICog.image.options]
        assert "background" in image_options

    def test_reasoning_mode_option_is_on_chat_and_pro_models_are_menu_selectable(self):
        """The refusal message lists PRO_MODE_MODELS, so each must be a chat menu entry."""
        chat_options = [opt.name for opt in OpenAICog.chat.options]
        assert "reasoning_mode" in chat_options
        assert "service_tier" in chat_options
        assert len(chat_options) == 15
        assert {choice.value for choice in CHAT_MODEL_CHOICES} >= PRO_MODE_MODELS

    def test_every_menu_reasoning_model_has_an_effort_entry(self):
        """Every reasoning model the chat menu offers must be in SUPPORTED_REASONING_EFFORTS.

        The gate rejects unmapped ids, so a new GPT-5.x / o-series menu entry needs a
        probed row before users can select a reasoning effort for it.
        """
        menu = [choice.value for choice in CHAT_MODEL_CHOICES]
        reasoning_menu = [m for m in menu if m in REASONING_MODELS or m.startswith("gpt-5")]
        assert reasoning_menu, "menu lists no reasoning models"
        missing = [m for m in reasoning_menu if m not in SUPPORTED_REASONING_EFFORTS]
        assert not missing, f"{missing} lack a probed reasoning-effort entry"
        menu_efforts = {choice.value for choice in REASONING_EFFORT_CHOICES}
        for model, efforts in SUPPORTED_REASONING_EFFORTS.items():
            assert efforts <= menu_efforts, f"{model} maps efforts the menu cannot select"

    def test_tts_model_maps_only_cover_menu_models(self):
        """RICH_TTS_MODELS and the voice map name only menu-selectable TTS ids.

        Pricing may keep retired rows (house rule), so it is checked as a superset.
        """
        menu = {choice.value for choice in TTS_MODEL_CHOICES}
        assert RICH_TTS_MODELS == ["gpt-4o-mini-tts"]
        assert set(RICH_TTS_MODELS) <= menu
        assert set(MODEL_SUPPORTED_TTS_VOICES) == menu
        assert menu <= set(TTS_PRICING_PER_CHAR)
