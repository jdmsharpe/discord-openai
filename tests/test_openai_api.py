from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from discord import Bot, Colour, Embed, Intents

from openai_api import (
    OpenAIAPI,
    _error_embed,
    append_flat_pricing_embed,
    append_pricing_embed,
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
    extract_summary_text,
    extract_tool_info,
)


class TestOpenAIAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Setting up the bot with the OpenAIAPI cog
        intents = Intents.default()
        intents.presences = False
        intents.members = True
        intents.message_content = True
        self.bot: Any = Bot(intents=intents)
        self.bot.add_cog(OpenAIAPI(bot=self.bot))
        self.bot.owner_id = 1234567890

    async def test_resolve_selected_tools_file_search_requires_vector_store(self):
        cog = cast(OpenAIAPI, self.bot.cogs["OpenAIAPI"])
        with patch("openai_api.OPENAI_VECTOR_STORE_IDS", []):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        assert tools == []
        assert "OPENAI_VECTOR_STORE_IDS" in error

    async def test_resolve_selected_tools_file_search_success(self):
        cog = cast(OpenAIAPI, self.bot.cogs["OpenAIAPI"])
        with patch("openai_api.OPENAI_VECTOR_STORE_IDS", ["vs_123"]):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        assert error is None
        assert tools[0]["type"] == "file_search"
        assert tools[0]["vector_store_ids"] == ["vs_123"]
        assert tools[0]["max_num_results"] == 5

    async def test_resolve_selected_tools_shell_model_guard(self):
        cog = cast(OpenAIAPI, self.bot.cogs["OpenAIAPI"])
        tools, error = cog.resolve_selected_tools(["shell"], "gpt-4.1")
        assert tools == []
        assert "GPT-5" in error

        tools, error = cog.resolve_selected_tools(["shell"], "gpt-5.2")
        assert error is None
        assert tools[0]["type"] == "shell"


class TestAppendResponseEmbeds:
    def test_append_short_response(self):
        """Short responses should be added as a single embed."""
        embeds = []
        append_response_embeds(embeds, "Hello, world!")
        assert len(embeds) == 1
        assert embeds[0].title == "Response"
        assert embeds[0].description == "Hello, world!"

    def test_append_to_existing_embeds(self):
        """Response should be appended to existing embeds list."""
        embeds = [Embed(title="Prompt", description="Test prompt", color=Colour.green())]
        append_response_embeds(embeds, "Response text")
        assert len(embeds) == 2
        assert embeds[1].title == "Response"

    def test_chunk_long_response(self):
        """Responses over 3500 chars should be chunked into multiple embeds."""
        embeds = []
        long_response = "x" * 4000  # Over 3500 char chunk size
        append_response_embeds(embeds, long_response)
        assert len(embeds) == 2
        assert embeds[0].title == "Response"
        assert embeds[1].title == "Response (Part 2)"

    def test_truncates_at_discord_limit(self):
        """Responses over Discord's ~5500 char budget should be truncated."""
        embeds = []
        long_response = "y" * 25000
        append_response_embeds(embeds, long_response)
        total_chars = sum(len(embed.description or "") for embed in embeds)
        assert total_chars <= 5503  # 5500 available + "..."

    def test_no_truncation_under_limit(self):
        """Responses under Discord's ~5500 char budget should not be truncated."""
        embeds = []
        response = "y" * 5000
        append_response_embeds(embeds, response)
        total_chars = sum(len(embed.description or "") for embed in embeds)
        assert total_chars == 5000

    def test_empty_response(self):
        """Empty response should not create an embed."""
        embeds = []
        append_response_embeds(embeds, "")
        # chunk_text("") returns [], so no embed is created
        assert len(embeds) == 0

    def test_multiple_chunks_numbered(self):
        """Multiple chunks should be numbered correctly."""
        embeds = []
        long_response = "z" * 7000
        append_response_embeds(embeds, long_response)
        assert embeds[0].title == "Response"
        assert embeds[1].title == "Response (Part 2)"


class TestExtractToolInfo:
    def test_extract_tool_info_empty_output(self):
        response = MagicMock()
        response.output = []

        result = extract_tool_info(response)

        assert result["tool_types"] == []
        assert result["citations"] == []
        assert result["file_citations"] == []

    def test_extract_tool_info_web_search(self):
        response = MagicMock()
        response.output = [
            {"type": "web_search_call"},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "Example Source",
                                "url": "https://example.com",
                            }
                        ],
                    }
                ],
            },
        ]

        result = extract_tool_info(response)

        assert "web_search" in result["tool_types"]
        assert len(result["citations"]) == 1
        assert result["citations"][0]["title"] == "Example Source"
        assert result["citations"][0]["url"] == "https://example.com"

    def test_extract_tool_info_code_interpreter(self):
        response = MagicMock()
        response.output = [{"type": "code_interpreter_call"}]

        result = extract_tool_info(response)

        assert "code_interpreter" in result["tool_types"]
        assert result["citations"] == []

    def test_extract_tool_info_file_search(self):
        response = MagicMock()
        response.output = [{"type": "file_search_call"}]

        result = extract_tool_info(response)

        assert "file_search" in result["tool_types"]
        assert result["citations"] == []
        assert result["file_citations"] == []

    def test_extract_tool_info_file_search_with_citations(self):
        response = MagicMock()
        response.output = [
            {"type": "file_search_call"},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [
                            {
                                "type": "file_citation",
                                "file_id": "file-abc123",
                                "filename": "report.pdf",
                                "index": 42,
                            },
                            {
                                "type": "file_citation",
                                "file_id": "file-def456",
                                "filename": "notes.txt",
                                "index": 100,
                            },
                        ],
                    }
                ],
            },
        ]

        result = extract_tool_info(response)

        assert "file_search" in result["tool_types"]
        assert len(result["file_citations"]) == 2
        assert result["file_citations"][0]["filename"] == "report.pdf"
        assert result["file_citations"][0]["file_id"] == "file-abc123"
        assert result["file_citations"][1]["filename"] == "notes.txt"

    def test_extract_tool_info_file_citations_deduplicated(self):
        response = MagicMock()
        response.output = [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [
                            {
                                "type": "file_citation",
                                "file_id": "file-abc123",
                                "filename": "report.pdf",
                                "index": 10,
                            },
                            {
                                "type": "file_citation",
                                "file_id": "file-abc123",
                                "filename": "report.pdf",
                                "index": 50,
                            },
                        ],
                    }
                ],
            },
        ]

        result = extract_tool_info(response)

        assert len(result["file_citations"]) == 1

    def test_extract_tool_info_shell(self):
        response = MagicMock()
        response.output = [{"type": "shell_call"}]

        result = extract_tool_info(response)

        assert "shell" in result["tool_types"]
        assert result["citations"] == []


class TestAppendSourcesEmbed:
    def test_web_citations_only(self):
        embeds = []
        citations = [{"title": "Example", "url": "https://example.com"}]
        append_sources_embed(embeds, citations)
        assert len(embeds) == 1
        assert embeds[0].title == "Sources"
        assert "Example" in embeds[0].description
        assert "https://example.com" in embeds[0].description

    def test_file_citations_only(self):
        embeds = []
        file_citations = [
            {"filename": "report.pdf", "file_id": "file-abc"},
            {"filename": "notes.txt", "file_id": "file-def"},
        ]
        append_sources_embed(embeds, [], file_citations)
        assert len(embeds) == 1
        assert "Files referenced" in embeds[0].description
        assert "report.pdf" in embeds[0].description
        assert "notes.txt" in embeds[0].description

    def test_web_and_file_citations_combined(self):
        embeds = []
        citations = [{"title": "Web Source", "url": "https://example.com"}]
        file_citations = [{"filename": "data.csv", "file_id": "file-123"}]
        append_sources_embed(embeds, citations, file_citations)
        assert len(embeds) == 1
        assert "Web Source" in embeds[0].description
        assert "data.csv" in embeds[0].description

    def test_no_citations(self):
        embeds = []
        append_sources_embed(embeds, [], [])
        assert len(embeds) == 0

    def test_no_embed_when_no_space(self):
        embeds = [Embed(title="Big", description="x" * 5950)]
        file_citations = [{"filename": "report.pdf", "file_id": "file-abc"}]
        append_sources_embed(embeds, [], file_citations)
        # Should not add since no remaining space
        assert len(embeds) == 1


class TestAppendPricingEmbed:
    def test_appends_embed(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1000, 500, 0.05)
        assert len(embeds) == 1
        assert embeds[0].color == Colour.blue()

    def test_description_contains_tokens(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1_234, 567, 0.42)
        desc = embeds[0].description
        assert "1,234 in" in desc
        assert "567 out" in desc

    def test_description_contains_daily_cost(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 100, 50, 1.23)
        assert "daily $1.23" in embeds[0].description

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Response", description="Hello")]
        append_pricing_embed(embeds, "gpt-4o", 100, 50, 0.01)
        assert len(embeds) == 2
        assert embeds[1].color == Colour.blue()


class TestAppendFlatPricingEmbed:
    def test_appends_embed(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.034, 0.15)
        assert len(embeds) == 1
        assert embeds[0].color == Colour.blue()

    def test_description_contains_cost_and_daily(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.034, 1.23)
        desc = embeds[0].description
        assert "$0.0340" in desc
        assert "daily $1.23" in desc

    def test_description_contains_details(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.133, 0.50, "high · 1024x1024 · 1 image(s)")
        desc = embeds[0].description
        assert "high" in desc
        assert "1024x1024" in desc

    def test_no_details(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.01, 0.01)
        desc = embeds[0].description
        # Should just be cost · daily (no extra details)
        assert desc == "$0.0100 · daily $0.01"

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Image", description="A cat")]
        append_flat_pricing_embed(embeds, 0.034, 0.05, "auto · auto")
        assert len(embeds) == 2
        assert embeds[0].title == "Image"
        assert embeds[1].color == Colour.blue()


class TestExtractSummaryText:
    def test_single_reasoning_block(self):
        response = MagicMock()
        summary_block = MagicMock()
        summary_block.type = "summary_text"
        summary_block.text = "The model considered multiple approaches."
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [summary_block]
        response.output = [reasoning_item]
        result = extract_summary_text(response)
        assert result == "The model considered multiple approaches."

    def test_multiple_summary_blocks(self):
        response = MagicMock()
        block1 = MagicMock()
        block1.type = "summary_text"
        block1.text = "First thought."
        block2 = MagicMock()
        block2.type = "summary_text"
        block2.text = "Second thought."
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block1, block2]
        response.output = [reasoning_item]
        result = extract_summary_text(response)
        assert result == "First thought.\n\nSecond thought."

    def test_no_reasoning_items(self):
        response = MagicMock()
        message_item = MagicMock()
        message_item.type = "message"
        response.output = [message_item]
        assert extract_summary_text(response) == ""

    def test_empty_output(self):
        response = MagicMock()
        response.output = []
        assert extract_summary_text(response) == ""

    def test_none_output(self):
        response = MagicMock()
        response.output = None
        assert extract_summary_text(response) == ""

    def test_reasoning_with_none_summary(self):
        response = MagicMock()
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = None
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_summary_block_with_none_text(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "summary_text"
        block.text = None
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_non_summary_text_blocks_ignored(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "other_type"
        block.text = "Should be ignored"
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_mixed_output_items(self):
        """Only reasoning items are processed, message items are skipped."""
        response = MagicMock()
        block = MagicMock()
        block.type = "summary_text"
        block.text = "Reasoning output"
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        message_item = MagicMock()
        message_item.type = "message"
        response.output = [reasoning_item, message_item]
        assert extract_summary_text(response) == "Reasoning output"


class TestAppendThinkingEmbeds:
    def test_short_thinking_text(self):
        embeds = []
        append_thinking_embeds(embeds, "Quick thought")
        assert len(embeds) == 1
        assert embeds[0].title == "Thinking"
        assert "Quick thought" in embeds[0].description
        # Should be wrapped in spoiler tags
        assert embeds[0].description.startswith("||") is True
        assert embeds[0].description.endswith("||") is True

    def test_empty_thinking_text(self):
        embeds = []
        append_thinking_embeds(embeds, "")
        assert len(embeds) == 0

    def test_truncation_at_3500_chars(self):
        embeds = []
        long_text = "x" * 4000
        append_thinking_embeds(embeds, long_text)
        assert len(embeds) == 1
        desc = embeds[0].description
        # Remove spoiler tags to check inner content
        inner = desc[2:-2]  # strip leading/trailing ||
        assert "[thinking truncated]" in inner
        assert len(inner) <= 3500

    def test_under_3500_not_truncated(self):
        embeds = []
        text = "y" * 3000
        append_thinking_embeds(embeds, text)
        inner = embeds[0].description[2:-2]
        assert len(inner) == 3000
        assert "truncated" not in inner

    def test_embed_color(self):
        embeds = []
        append_thinking_embeds(embeds, "Some thought")
        assert embeds[0].color == Colour.light_grey()

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Prompt", description="User question")]
        append_thinking_embeds(embeds, "Reasoning here")
        assert len(embeds) == 2
        assert embeds[0].title == "Prompt"
        assert embeds[1].title == "Thinking"


class TestErrorEmbed:
    def test_creates_red_embed(self):
        embed = _error_embed("Something went wrong")
        assert embed.title == "Error"
        assert embed.description == "Something went wrong"
        assert embed.color == Colour.red()

    def test_empty_description(self):
        embed = _error_embed("")
        assert embed.description == ""
