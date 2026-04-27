from discord import Colour, Embed

from discord_openai.cogs.openai.embeds import (
    append_flat_pricing_embed,
    append_pricing_embed,
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
    error_embed,
)


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
        assert desc == "$0.0100 · daily $0.01"

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Image", description="A cat")]
        append_flat_pricing_embed(embeds, 0.034, 0.05, "auto · auto")
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
