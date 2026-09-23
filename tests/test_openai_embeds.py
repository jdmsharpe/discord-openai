from discord import Colour, Embed

from discord_openai.cogs.openai.embeds import (
    append_flat_pricing_embed,
    append_pricing_embed,
    append_research_sources_embed,
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
    error_embed,
)
from discord_openai.util import calculate_cost


class TestAppendResponseEmbeds:
    def test_append_short_response(self):
        embeds = []
        append_response_embeds(embeds, "Hello, world!")
        assert len(embeds) == 1
        assert embeds[0].title == "Response"
        assert embeds[0].description == "Hello, world!"

    def test_append_to_existing_embeds(self):
        embeds = [Embed(title="Prompt", description="Test prompt", color=Colour.green())]
        append_response_embeds(embeds, "Response text")
        assert len(embeds) == 2
        assert embeds[1].title == "Response"

    def test_chunk_long_response(self):
        embeds = []
        long_response = "x" * 4000
        append_response_embeds(embeds, long_response)
        assert len(embeds) == 2
        assert embeds[0].title == "Response"
        assert embeds[1].title == "Response (Part 2)"

    def test_preserves_full_response_for_delivery_batching(self):
        embeds = []
        long_response = "y" * 25000
        append_response_embeds(embeds, long_response)
        total_chars = sum(len(embed.description or "") for embed in embeds)
        assert total_chars == 25000

    def test_no_truncation_under_limit(self):
        embeds = []
        response = "y" * 5000
        append_response_embeds(embeds, response)
        total_chars = sum(len(embed.description or "") for embed in embeds)
        assert total_chars == 5000

    def test_empty_response(self):
        embeds = []
        append_response_embeds(embeds, "")
        assert len(embeds) == 0

    def test_multiple_chunks_numbered(self):
        embeds = []
        long_response = "z" * 7000
        append_response_embeds(embeds, long_response)
        assert embeds[0].title == "Response"
        assert embeds[1].title == "Response (Part 2)"


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

    def test_sources_preserved_for_delivery_batching(self):
        embeds = [
            Embed(title="Big 1", description="x" * 3500),
            Embed(title="Big 2", description="y" * 2500),
        ]
        file_citations = [{"filename": "report.pdf", "file_id": "file-abc"}]
        append_sources_embed(embeds, [], file_citations)
        assert len(embeds) == 3
        assert embeds[-1].title == "Sources"
        assert "report.pdf" in embeds[-1].description

    def test_long_web_links_are_kept_complete_or_omitted(self):
        first_url = "https://example.com/" + "a" * 3500
        second_url = "https://example.org/" + "b" * 1000
        embeds = []
        append_sources_embed(
            embeds,
            [
                {"title": "First", "url": first_url},
                {"title": "Second", "url": second_url},
            ],
        )

        assert f"[First]({first_url})" in embeds[0].description
        assert second_url not in embeds[0].description
        assert len(embeds[0].description) <= 4000


class TestAppendResearchSourcesEmbed:
    def test_web_citations_grouped_and_numbered(self):
        embeds = []
        citations = [{"title": "Example", "url": "https://example.com"}]
        append_research_sources_embed(embeds, citations)
        assert len(embeds) == 1
        assert embeds[0].title == "Sources"
        assert "**Web sources**" in embeds[0].description
        assert "1. [Example](https://example.com)" in embeds[0].description

    def test_file_citations_use_documents_heading(self):
        embeds = []
        file_citations = [{"filename": "report.pdf", "file_id": "file-abc"}]
        append_research_sources_embed(embeds, [], file_citations)
        assert len(embeds) == 1
        assert "**Documents**" in embeds[0].description
        assert "1. report.pdf" in embeds[0].description

    def test_web_and_file_citations_combined(self):
        embeds = []
        citations = [{"title": "Web Source", "url": "https://example.com"}]
        file_citations = [{"filename": "data.csv", "file_id": "file-123"}]
        append_research_sources_embed(embeds, citations, file_citations)
        assert len(embeds) == 1
        assert "**Web sources**" in embeds[0].description
        assert "**Documents**" in embeds[0].description

    def test_caps_at_eight_with_overflow_indicator(self):
        embeds = []
        citations = [{"title": f"T{i}", "url": f"https://e/{i}"} for i in range(10)]
        append_research_sources_embed(embeds, citations)
        assert "8. [T7](https://e/7)" in embeds[0].description
        assert "9. " not in embeds[0].description
        assert "_…and 2 more_" in embeds[0].description

    def test_no_citations(self):
        embeds = []
        append_research_sources_embed(embeds, [], [])
        assert len(embeds) == 0

    def test_long_research_links_are_kept_complete_or_omitted(self):
        first_url = "https://example.com/" + "a" * 3500
        second_url = "https://example.org/" + "b" * 1000
        embeds = []
        append_research_sources_embed(
            embeds,
            [
                {"title": "First", "url": first_url},
                {"title": "Second", "url": second_url},
            ],
        )

        assert f"[First]({first_url})" in embeds[0].description
        assert second_url not in embeds[0].description
        assert len(embeds[0].description) <= 4000


class TestAppendPricingEmbed:
    def test_appends_embed(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1000, 500, 0.05)
        assert len(embeds) == 1
        assert embeds[0].color == Colour.blue()

    def test_description_is_one_cost_line(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1_234, 567, 0.42)
        assert embeds[0].description == "$0.0088 · 1.2k in / 567 out · $0.42 today"

    def test_output_count_includes_thinking_tokens(self):
        """The Responses API counts reasoning inside output_tokens; the line does not subtract it."""
        embeds = []
        append_pricing_embed(
            embeds, "gpt-5.6-sol", 2_000, 900, 0.12, cached_tokens=1_500, reasoning_tokens=700
        )
        assert embeds[0].description == (
            "$0.0206 · 2k in (1.5k cached) / 900 out (700 thinking) · $0.12 today"
        )

    def test_cache_writes_are_billed_but_not_listed(self):
        embeds = []
        append_pricing_embed(
            embeds, "gpt-5.6-sol", 1_000, 500, 0.05, cached_tokens=100, cache_write_tokens=900
        )
        expected = calculate_cost("gpt-5.6-sol", 1_000, 500, 100, 900)
        assert f"${expected:.4f}" == "$0.0145"
        assert embeds[0].description == "$0.0145 · 1k in (100 cached) / 500 out · $0.05 today"

    def test_tools_show_as_counts_inside_the_cost(self):
        embeds = []
        append_pricing_embed(
            embeds,
            "gpt-4o",
            3_000,
            400,
            1.5,
            tool_call_counts={
                "shell": 1,
                "get_weather": 3,
                "mcp": 1,
                "code_interpreter": 1,
                "web_search": 2,
            },
            service_tier="priority",
        )
        # $0.01955 of fast-mode tokens + $0.08 of tool calls.
        assert embeds[0].description == (
            "$0.0995 · 3k in / 400 out · 2 searches · 1 code run · 1 MCP call"
            " · 3 get weather calls · 1 shell call · fast mode · $1.50 today"
        )

    def test_nonzero_cost_below_the_smallest_unit(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-6-luna", 24, 21, 0.003)
        assert embeds[0].description == "<$0.0001 · 24 in / 21 out · <$0.01 today"

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
        assert embeds[0].description == "$0.0340 · $1.23 today"

    def test_description_contains_details(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.133, 0.50, ["1 image", "high", "1024x1024"])
        assert embeds[0].description == "$0.1330 · 1 image · high · 1024x1024 · $0.50 today"

    def test_token_counts_show_when_passed(self):
        embeds = []
        append_flat_pricing_embed(
            embeds,
            0.0512,
            0.50,
            ["1 image", "medium", "1024x1024"],
            input_tokens=48,
            output_tokens=1_056,
        )
        assert embeds[0].description == (
            "$0.0512 · 48 in / 1.1k out · 1 image · medium · 1024x1024 · $0.50 today"
        )

    def test_no_details(self):
        embeds = []
        append_flat_pricing_embed(embeds, 0.01, 0.01)
        assert embeds[0].description == "$0.0100 · $0.01 today"

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Image", description="A cat")]
        append_flat_pricing_embed(embeds, 0.034, 0.05, ["auto", "auto"])
        assert len(embeds) == 2
        assert embeds[0].title == "Image"
        assert embeds[1].color == Colour.blue()


class TestAppendThinkingEmbeds:
    def test_short_thinking_text(self):
        embeds = []
        append_thinking_embeds(embeds, "Quick thought")
        assert len(embeds) == 1
        assert embeds[0].title == "Thinking"
        assert "Quick thought" in embeds[0].description
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
        inner = desc[2:-2]
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
        embed = error_embed("Something went wrong")
        assert embed.title == "Error"
        assert embed.description == "Something went wrong"
        assert embed.color == Colour.red()

    def test_empty_description(self):
        embed = error_embed("")
        assert embed.description == ""
