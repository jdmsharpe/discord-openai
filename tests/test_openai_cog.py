from typing import Any, cast
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from discord import Bot, Intents

from discord_openai import OpenAICog
from discord_openai.cogs.openai.command_options import (
    CHAT_MODEL_CHOICES,
    IMAGE_MODEL_CHOICES,
    REASONING_EFFORT_CHOICES,
    RESEARCH_MODEL_CHOICES,
    STT_MODEL_CHOICES,
    TTS_VOICE_CHOICES,
    VIDEO_MODEL_CHOICES,
)


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
            "gpt-5.4",
            None,
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
        )
        assert OpenAICog.image.callback.__defaults__ == ("gpt-image-1.5", "auto", "auto", None)
        assert OpenAICog.tts.callback.__defaults__ == ("gpt-4o-mini-tts", "marin", "", "mp3", 1.0)
        assert OpenAICog.stt.callback.__defaults__ == ("gpt-4o-transcribe", "transcription")
        assert OpenAICog.video.callback.__defaults__ == ("sora-2", "1280x720", "8")
        assert OpenAICog.research.callback.__defaults__ == ("o3-deep-research", False, False)

    def test_critical_choice_values_present(self):
        assert any(choice.value == "gpt-5.4" for choice in CHAT_MODEL_CHOICES)
        assert any(choice.value == "gpt-image-1.5" for choice in IMAGE_MODEL_CHOICES)
        assert any(choice.value == "marin" for choice in TTS_VOICE_CHOICES)
        assert any(choice.value == "gpt-4o-transcribe" for choice in STT_MODEL_CHOICES)
        assert any(choice.value == "sora-2" for choice in VIDEO_MODEL_CHOICES)
        assert any(choice.value == "o3-deep-research" for choice in RESEARCH_MODEL_CHOICES)

    def test_reasoning_effort_choice_set(self):
        values = {choice.value for choice in REASONING_EFFORT_CHOICES}
        assert values == {"none", "minimal", "low", "medium", "high", "xhigh"}
