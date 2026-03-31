from typing import Any, cast
from unittest.mock import patch

import pytest
from discord import Bot, Intents

from discord_openai import OpenAICog


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
        with patch("discord_openai.cogs.openai.tooling.OPENAI_VECTOR_STORE_IDS", []):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        assert tools == []
        assert "OPENAI_VECTOR_STORE_IDS" in error

    async def test_resolve_selected_tools_file_search_success(self):
        cog = cast(OpenAICog, self.bot.cogs["OpenAICog"])
        with patch("discord_openai.cogs.openai.tooling.OPENAI_VECTOR_STORE_IDS", ["vs_123"]):
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
