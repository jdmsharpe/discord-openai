# Discord OpenAI Bot - Developer Reference

## Supported Entry Points

- Launcher: `python src/bot.py` remains supported and delegates to `discord_openai.bot.main`.
- Cog composition contract:

  ```python
  from discord_openai import OpenAICog
  from discord_openai.config.auth import validate_required_config

  validate_required_config()  # raises if BOT_TOKEN or OPENAI_API_KEY are missing or blank
  bot.add_cog(OpenAICog(bot=bot))
  ```

- `BOT_TOKEN` and `OPENAI_API_KEY` are read at module import time without raising. Call `validate_required_config()` before connecting so missing or blank vars produce a clear error rather than a silent downstream API failure.
- `discord_openai` and `discord_openai.cogs.openai` both use lazy `__getattr__` exports so helper imports do not eagerly pull in Discord-heavy modules. Type-only imports keep `pyright src/` aware of those public exports.

## Package Layout

```text
src/
├── bot.py                           # Thin repo-local launcher
└── discord_openai/
    ├── __init__.py                  # Lazily re-exports OpenAICog
    ├── bot.py                       # Namespaced launcher
    ├── util.py
    ├── config/
    │   ├── __init__.py
    │   ├── auth.py
    │   └── mcp.py
    └── cogs/openai/
        ├── __init__.py
        ├── attachments.py
        ├── chat.py
        ├── client.py
        ├── cog.py
        ├── embeds.py
        ├── image.py
        ├── models.py
        ├── research.py
        ├── responses.py
        ├── speech.py
        ├── state.py
        ├── tool_registry.py
        ├── tooling.py
        ├── video.py
        └── views.py
```

Only `src/bot.py` remains at the repo root; code imports should target `discord_openai...`.

## Testing And Patch Targets

- `pytest` runs with `pythonpath = ["src"]`.
- `tests/conftest.py` provides an autouse fixture that sets dummy `BOT_TOKEN` and `OPENAI_API_KEY` env vars so the package can be imported without real credentials in CI.
- The test suite is organized into module-aligned files such as `tests/test_openai_cog.py`, `tests/test_openai_embeds.py`, `tests/test_openai_responses.py`, `tests/test_openai_tooling.py`, `tests/test_config_auth.py`, and `tests/test_lazy_imports.py`.
- MCP coverage lives primarily in `tests/test_openai_mcp_config.py` and `tests/test_openai_chat.py`.
- Runtime state pruning is covered in `tests/test_openai_state.py`.
- `tests/test_package_import.py` is the package import smoke test.
- New tests and patches should target real owners under `discord_openai...`.
- Examples:
  - `discord_openai.cogs.openai.tool_registry.TOOL_REGISTRY`
  - `discord_openai.cogs.openai.tool_registry.get_tool_select_options`
  - `discord_openai.cogs.openai.embeds.append_pricing_embed`
  - `discord_openai.cogs.openai.tooling.extract_tool_info`
  - `discord_openai.config.mcp.OPENAI_MCP_PRESETS`
  - `discord_openai.cogs.openai.chat.handle_mcp_approval_action`
  - `discord_openai.cogs.openai.views.McpApprovalView`
- Import `OpenAICog` from `discord_openai`; do not reintroduce legacy `openai_api` shim paths.

## Validation Commands

```bash
ruff check src/ tests/
ruff format src/ tests/
pyright src/
pytest -q
```

- The repo pre-commit hook prefers a repo-local `.venv` Ruff binary when available and falls back to `PATH`.

## Provider Notes

- `resolve_selected_tools()` in `discord_openai.cogs.openai.tooling` remains the canonical tool-resolution path for chat and research.
- `file_search` requires `OPENAI_VECTOR_STORE_IDS`.
- `shell` remains limited to GPT-5 series models.
- `ResponseParameters.to_dict()` in `discord_openai.util` remains the canonical request-construction path.
- Named MCP presets are loaded from `OPENAI_MCP_PRESETS_JSON` and `OPENAI_MCP_PRESETS_PATH`; when both are set they merge additively, and duplicate preset names are rejected.
- Presets support both remote MCP servers (`kind="remote_mcp"`) and OpenAI connectors (`kind="connector"`).
- `authorization_env_var` names are user-defined token env vars that must be present at runtime for those presets to be available.
- MCP state is persisted separately from built-in tool selections via `tool_names`, `mcp_preset_names`, and `pending_mcp_approval`.
- While an approval is pending, the bot swaps to `McpApprovalView`, blocks typed follow-ups, and resumes the same response chain with `mcp_approval_response` when the owner approves or denies.
