from unittest.mock import MagicMock, patch
import unittest
from typing import Any, cast
from openai_api import OpenAIAPI, append_pricing_embed, append_response_embeds, append_sources_embed, extract_tool_info
from discord import Bot, Colour, Embed, Intents


class TestOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
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
        self.assertEqual(tools, [])
        self.assertIn("OPENAI_VECTOR_STORE_IDS", error)

    async def test_resolve_selected_tools_file_search_success(self):
        cog = cast(OpenAIAPI, self.bot.cogs["OpenAIAPI"])
        with patch("openai_api.OPENAI_VECTOR_STORE_IDS", ["vs_123"]):
            tools, error = cog.resolve_selected_tools(["file_search"], "gpt-5.2")
        self.assertIsNone(error)
        self.assertEqual(tools[0]["type"], "file_search")
        self.assertEqual(tools[0]["vector_store_ids"], ["vs_123"])
        self.assertEqual(tools[0]["max_num_results"], 5)

    async def test_resolve_selected_tools_shell_model_guard(self):
        cog = cast(OpenAIAPI, self.bot.cogs["OpenAIAPI"])
        tools, error = cog.resolve_selected_tools(["shell"], "gpt-4.1")
        self.assertEqual(tools, [])
        self.assertIn("GPT-5", error)

        tools, error = cog.resolve_selected_tools(["shell"], "gpt-5.2")
        self.assertIsNone(error)
        self.assertEqual(tools[0]["type"], "shell")


class TestAppendResponseEmbeds(unittest.TestCase):
    def test_append_short_response(self):
        """Short responses should be added as a single embed."""
        embeds = []
        append_response_embeds(embeds, "Hello, world!")
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Response")
        self.assertEqual(embeds[0].description, "Hello, world!")

    def test_append_to_existing_embeds(self):
        """Response should be appended to existing embeds list."""
        embeds = [Embed(title="Prompt", description="Test prompt", color=Colour.green())]
        append_response_embeds(embeds, "Response text")
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[1].title, "Response")

    def test_chunk_long_response(self):
        """Responses over 3500 chars should be chunked into multiple embeds."""
        embeds = []
        long_response = "x" * 4000  # Over 3500 char chunk size
        append_response_embeds(embeds, long_response)
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[0].title, "Response")
        self.assertEqual(embeds[1].title, "Response (Part 2)")

    def test_respects_total_limit(self):
        """Response should be truncated to respect 6000 char total limit."""
        # Create existing embed that uses some of the 6000 char budget
        existing_embed = Embed(title="Prompt", description="x" * 3000)
        embeds = [existing_embed]
        # Try to add a response that would exceed 6000 total
        long_response = "y" * 5000
        append_response_embeds(embeds, long_response)
        # Calculate total chars across all embeds
        total_chars = sum(
            len(embed.description or "") + len(embed.title or "")
            for embed in embeds
        )
        # Should be under 6000 (with some buffer)
        self.assertLess(total_chars, 6100)

    def test_truncation_message(self):
        """Truncated responses should include truncation notice."""
        existing_embed = Embed(title="Prompt", description="x" * 4000)
        embeds = [existing_embed]
        long_response = "y" * 5000
        append_response_embeds(embeds, long_response)
        # Check if any embed contains the truncation message
        all_descriptions = " ".join(embed.description or "" for embed in embeds)
        self.assertIn("truncated", all_descriptions.lower())

    def test_empty_response(self):
        """Empty response should not create an embed."""
        embeds = []
        append_response_embeds(embeds, "")
        # chunk_text("") returns [], so no embed is created
        self.assertEqual(len(embeds), 0)

    def test_multiple_chunks_numbered(self):
        """Multiple chunks should be numbered correctly."""
        embeds = []
        # Create response that needs 3 chunks (3500 * 3 = 10500 chars)
        # But limited by 6000 total, so will be truncated first
        long_response = "z" * 7000
        append_response_embeds(embeds, long_response)
        # First embed should be "Response", subsequent should be "Response (Part N)"
        self.assertEqual(embeds[0].title, "Response")
        if len(embeds) > 1:
            self.assertIn("Part", embeds[1].title)


class TestExtractToolInfo(unittest.TestCase):
    def test_extract_tool_info_empty_output(self):
        response = MagicMock()
        response.output = []

        result = extract_tool_info(response)

        self.assertEqual(result["tool_types"], [])
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["file_citations"], [])

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

        self.assertIn("web_search", result["tool_types"])
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["title"], "Example Source")
        self.assertEqual(result["citations"][0]["url"], "https://example.com")

    def test_extract_tool_info_code_interpreter(self):
        response = MagicMock()
        response.output = [{"type": "code_interpreter_call"}]

        result = extract_tool_info(response)

        self.assertIn("code_interpreter", result["tool_types"])
        self.assertEqual(result["citations"], [])

    def test_extract_tool_info_file_search(self):
        response = MagicMock()
        response.output = [{"type": "file_search_call"}]

        result = extract_tool_info(response)

        self.assertIn("file_search", result["tool_types"])
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["file_citations"], [])

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

        self.assertIn("file_search", result["tool_types"])
        self.assertEqual(len(result["file_citations"]), 2)
        self.assertEqual(result["file_citations"][0]["filename"], "report.pdf")
        self.assertEqual(result["file_citations"][0]["file_id"], "file-abc123")
        self.assertEqual(result["file_citations"][1]["filename"], "notes.txt")

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

        self.assertEqual(len(result["file_citations"]), 1)

    def test_extract_tool_info_shell(self):
        response = MagicMock()
        response.output = [{"type": "shell_call"}]

        result = extract_tool_info(response)

        self.assertIn("shell", result["tool_types"])
        self.assertEqual(result["citations"], [])


class TestAppendSourcesEmbed(unittest.TestCase):
    def test_web_citations_only(self):
        embeds = []
        citations = [{"title": "Example", "url": "https://example.com"}]
        append_sources_embed(embeds, citations)
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Sources")
        self.assertIn("Example", embeds[0].description)
        self.assertIn("https://example.com", embeds[0].description)

    def test_file_citations_only(self):
        embeds = []
        file_citations = [
            {"filename": "report.pdf", "file_id": "file-abc"},
            {"filename": "notes.txt", "file_id": "file-def"},
        ]
        append_sources_embed(embeds, [], file_citations)
        self.assertEqual(len(embeds), 1)
        self.assertIn("Files referenced", embeds[0].description)
        self.assertIn("report.pdf", embeds[0].description)
        self.assertIn("notes.txt", embeds[0].description)

    def test_web_and_file_citations_combined(self):
        embeds = []
        citations = [{"title": "Web Source", "url": "https://example.com"}]
        file_citations = [{"filename": "data.csv", "file_id": "file-123"}]
        append_sources_embed(embeds, citations, file_citations)
        self.assertEqual(len(embeds), 1)
        self.assertIn("Web Source", embeds[0].description)
        self.assertIn("data.csv", embeds[0].description)

    def test_no_citations(self):
        embeds = []
        append_sources_embed(embeds, [], [])
        self.assertEqual(len(embeds), 0)

    def test_no_embed_when_no_space(self):
        embeds = [Embed(title="Big", description="x" * 5950)]
        file_citations = [{"filename": "report.pdf", "file_id": "file-abc"}]
        append_sources_embed(embeds, [], file_citations)
        # Should not add since no remaining space
        self.assertEqual(len(embeds), 1)


class TestAppendPricingEmbed(unittest.TestCase):
    def test_appends_embed(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1000, 500, 0.05)
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].color, Colour.blue())

    def test_description_contains_model(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4.1", 2000, 1000, 0.10)
        self.assertIn("gpt-4.1", embeds[0].description)

    def test_description_contains_tokens(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 1_234, 567, 0.42)
        desc = embeds[0].description
        self.assertIn("1,234 in", desc)
        self.assertIn("567 out", desc)

    def test_description_contains_daily_cost(self):
        embeds = []
        append_pricing_embed(embeds, "gpt-4o", 100, 50, 1.23)
        self.assertIn("daily $1.23", embeds[0].description)

    def test_appends_to_existing_embeds(self):
        embeds = [Embed(title="Response", description="Hello")]
        append_pricing_embed(embeds, "gpt-4o", 100, 50, 0.01)
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[1].color, Colour.blue())


if __name__ == "__main__":
    unittest.main()
