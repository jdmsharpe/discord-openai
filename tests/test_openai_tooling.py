from unittest.mock import MagicMock

from discord_openai.cogs.openai.tooling import extract_tool_info


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
