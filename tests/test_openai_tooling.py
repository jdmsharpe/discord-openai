from unittest.mock import MagicMock, patch

from discord_openai.cogs.openai.tool_registry import TOOL_REGISTRY, get_tool_select_options
from discord_openai.cogs.openai.tooling import extract_tool_info, resolve_selected_tools
from discord_openai.config.mcp import OpenAIMcpPreset


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

    def test_extract_tool_info_mcp_outputs(self):
        response = MagicMock()
        response.output = [
            {
                "type": "mcp_list_tools",
                "server_label": "GitHub",
                "tools": [{"name": "search_issues"}],
            },
            {
                "type": "mcp_call",
                "server_label": "GitHub",
                "name": "search_issues",
                "output": '{"items": []}',
            },
            {
                "type": "mcp_approval_request",
                "id": "mcpr_123",
                "server_label": "GitHub",
                "name": "create_issue",
                "arguments": '{"title":"Bug"}',
            },
        ]

        result = extract_tool_info(response)

        assert "mcp" in result["tool_types"]
        assert result["mcp_list_tools"][0]["server_label"] == "GitHub"
        assert result["mcp_calls"][0]["name"] == "search_issues"
        assert result["pending_mcp_approval"] == {
            "approval_request_id": "mcpr_123",
            "server_label": "GitHub",
            "tool_name": "create_issue",
            "arguments": '{"title":"Bug"}',
        }


class TestResolveSelectedTools:
    def test_resolve_selected_tools_includes_mcp_presets(self):
        preset = OpenAIMcpPreset(
            name="github",
            kind="remote_mcp",
            server_label="GitHub",
            server_url="https://example.com/mcp",
        )

        with (
            patch(
                "discord_openai.cogs.openai.tooling.resolve_mcp_presets",
                return_value=([preset], None),
            ),
            patch(
                "discord_openai.cogs.openai.tooling.build_mcp_tool",
                return_value={"type": "mcp", "server_label": "GitHub"},
            ),
        ):
            tools, error = resolve_selected_tools(["web_search"], "gpt-5.4", ["github"])

        assert error is None
        assert tools == [
            {"type": "web_search"},
            {"type": "mcp", "server_label": "GitHub"},
        ]


class TestToolRegistrySync:
    def test_tool_select_options_match_registry_keys(self):
        option_values = [option["value"] for option in get_tool_select_options()]
        assert option_values == list(TOOL_REGISTRY.keys())

    def test_resolve_selected_tools_uses_registry_entries(self):
        with patch(
            "discord_openai.cogs.openai.tool_registry.OPENAI_VECTOR_STORE_IDS",
            ["vs_123"],
        ):
            tools, error = resolve_selected_tools(list(TOOL_REGISTRY.keys()), "gpt-5.4")

        assert error is None
        assert [tool["type"] for tool in tools] == list(TOOL_REGISTRY.keys())
