import json
from unittest.mock import patch

import pytest

from discord_openai.config.mcp import (
    APPROVAL_SELECTIVE,
    CONNECTOR_UNSUPPORTED_MODELS,
    OpenAIMcpPreset,
    build_mcp_tool,
    load_openai_mcp_presets,
    mcp_connector_error,
    parse_mcp_preset_names,
)

CONNECTOR_PRESET = OpenAIMcpPreset(
    name="dropbox",
    kind="connector",
    server_label="Dropbox",
    connector_id="connector_dropbox",
)
REMOTE_PRESET = OpenAIMcpPreset(
    name="github",
    kind="remote_mcp",
    server_label="GitHub",
    server_url="https://api.githubcopilot.com/mcp/",
)


class TestOpenAIMcpConfig:
    def test_load_openai_mcp_presets_from_inline_json(self):
        raw_config = json.dumps(
            {
                "github": {
                    "kind": "remote_mcp",
                    "server_url": "https://api.githubcopilot.com/mcp/",
                    "server_label": "GitHub",
                    "allowed_tools": ["search_issues", "search_issues"],
                },
                "gmail": {
                    "kind": "connector",
                    "connector_id": "connector_gmail",
                    "server_label": "Gmail",
                },
            }
        )

        with patch.dict("os.environ", {"OPENAI_MCP_PRESETS_JSON": raw_config}, clear=False):
            presets = load_openai_mcp_presets()

        assert presets["github"].server_url == "https://api.githubcopilot.com/mcp/"
        assert presets["github"].allowed_tools == ["search_issues"]
        assert presets["gmail"].connector_id == "connector_gmail"

    def test_missing_auth_env_marks_preset_unavailable(self):
        raw_config = json.dumps(
            {
                "google_calendar": {
                    "kind": "connector",
                    "connector_id": "connector_googlecalendar",
                    "authorization_env_var": "GOOGLE_CALENDAR_TOKEN",
                }
            }
        )

        with patch.dict(
            "os.environ",
            {"OPENAI_MCP_PRESETS_JSON": raw_config},
            clear=True,
        ):
            presets = load_openai_mcp_presets()

        assert presets["google_calendar"].available is False
        assert "GOOGLE_CALENDAR_TOKEN" in (presets["google_calendar"].unavailable_reason or "")

    def test_build_mcp_tool_supports_selective_approval(self):
        preset = OpenAIMcpPreset(
            name="github",
            kind="remote_mcp",
            server_label="GitHub",
            server_url="https://api.githubcopilot.com/mcp/",
            authorization_env_var="GITHUB_MCP_TOKEN",
            approval=APPROVAL_SELECTIVE,
            never_tool_names=["search_issues"],
        )

        with patch.dict("os.environ", {"GITHUB_MCP_TOKEN": "secret-token"}, clear=False):
            tool = build_mcp_tool(preset)

        assert tool["type"] == "mcp"
        assert tool["server_url"] == "https://api.githubcopilot.com/mcp/"
        assert tool["authorization"] == "secret-token"
        assert tool["require_approval"] == {
            "never": {
                "tool_names": ["search_issues"],
            }
        }

    def test_parse_mcp_preset_names_deduplicates_and_trims(self):
        assert parse_mcp_preset_names(" github, gmail ,github ,, ") == ["github", "gmail"]


class TestMcpConnectorError:
    """The GPT-6 models 400 on an `mcp` tool carrying `connector_id`."""

    def test_unsupported_model_set_is_pinned(self):
        assert set(CONNECTOR_UNSUPPORTED_MODELS) == {"gpt-6-astra", "gpt-6-sol", "gpt-6-luna"}

    @pytest.mark.parametrize("model", sorted(CONNECTOR_UNSUPPORTED_MODELS))
    def test_connector_preset_is_refused_on_gpt_6(self, model):
        error = mcp_connector_error(model, [REMOTE_PRESET, CONNECTOR_PRESET])
        assert error is not None
        assert "`dropbox`" in error
        assert f"`{model}`" in error
        assert "`remote_mcp`" in error
        assert "GPT-5.6 or earlier" in error

    @pytest.mark.parametrize("model", sorted(CONNECTOR_UNSUPPORTED_MODELS))
    def test_remote_mcp_preset_passes_on_gpt_6(self, model):
        assert mcp_connector_error(model, [REMOTE_PRESET]) is None

    @pytest.mark.parametrize("model", ["gpt-5.6-sol", "gpt-5.4-nano"])
    def test_connector_preset_passes_on_earlier_models(self, model):
        assert mcp_connector_error(model, [CONNECTOR_PRESET]) is None

    def test_no_presets_pass(self):
        assert mcp_connector_error("gpt-6-astra", []) is None
