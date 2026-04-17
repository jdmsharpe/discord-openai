# Discord OpenAI Bot - Developer Reference

## Quick Start

```bash
cp .env.example .env          # fill in BOT_TOKEN and OPENAI_API_KEY at minimum
pip install -r requirements.txt
python src/bot.py              # or: docker compose up
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Discord bot token |
| `GUILD_IDS` | No | Comma-separated Discord server IDs; omit for global slash-command registration (~1h propagation) or set for instant per-guild registration |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_VECTOR_STORE_IDS` | No | Comma-separated vector store IDs for `/openai chat file_search` |
| `OPENAI_MCP_PRESETS_JSON` | No | Inline JSON of named MCP presets |
| `OPENAI_MCP_PRESETS_PATH` | No | Path to JSON file of named MCP presets |
| `SHOW_COST_EMBEDS` | No | Show cost embeds (`true`/`1`/`yes`, default: `true`) |
| `OPENAI_PRICING_PATH` | No | Override the bundled `src/discord_openai/config/pricing.yaml` |
| `LOG_FORMAT` | No | `text` (default) or `json` for structured JSON-lines output |

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
    ├── logging_setup.py             # Structured logging + request-id ContextVar
    ├── util.py
    ├── config/
    │   ├── __init__.py
    │   ├── auth.py
    │   ├── mcp.py
    │   ├── pricing.py                # YAML loader exposing MODEL_PRICING, IMAGE_PRICING, etc.
    │   └── pricing.yaml              # Canonical pricing data (override via OPENAI_PRICING_PATH)
    └── cogs/openai/
        ├── __init__.py
        ├── attachments.py
        ├── chat.py
        ├── client.py
        ├── cog.py
        ├── embeds.py
        ├── image.py
        ├── models.py           # Re-export shim for util.py parameter types
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
- `tests/test_util.py` covers `ResponseParameters`, cost helpers, and error formatting.
- `tests/test_button_view.py` covers the button-based Discord UI components.
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

- The repo pre-commit hook (`.githooks/pre-commit`) runs `ruff format` (auto-applied + re-staged), then `ruff check` (blocking), then `pyright` and `pytest --collect-only` as warning-only smoke tests. Resolves tools from `.venv/bin` or `.venv/Scripts` first, then `PATH`.

## Provider Notes

- `resolve_selected_tools()` in `discord_openai.cogs.openai.tooling` remains the canonical tool-resolution path for chat and research.
- `file_search` requires `OPENAI_VECTOR_STORE_IDS`.
- `gpt-5`, `gpt-5-mini`, and `gpt-5-nano` (`GPT5_NO_TEMP_MODELS`) never accept `temperature` or `top_p`; `ResponseParameters.__init__` silently drops them.
- `shell` remains limited to GPT-5 series models.
- `ResponseParameters.to_dict()` in `discord_openai.util` remains the canonical request-construction path.
- Named MCP presets are loaded from `OPENAI_MCP_PRESETS_JSON` and `OPENAI_MCP_PRESETS_PATH`; when both are set they merge additively, and duplicate preset names are rejected.
- Presets support both remote MCP servers (`kind="remote_mcp"`) and OpenAI connectors (`kind="connector"`).
- `authorization_env_var` names are user-defined token env vars that must be present at runtime for those presets to be available.
- MCP state is persisted separately from built-in tool selections via `tool_names`, `mcp_preset_names`, and `pending_mcp_approval`.
- While an approval is pending, the bot swaps to `McpApprovalView`, blocks typed follow-ups, and resumes the same response chain with `mcp_approval_response` when the owner approves or denies.

## Runtime Conventions (Cross-Project)

- **Pricing** is loaded from `src/discord_openai/config/pricing.yaml` by `config/pricing.py` at import time. Override via `OPENAI_PRICING_PATH` to push a vendor price change without a code release. Cross-referenced against [genai-prices/openai.yml](https://github.com/pydantic/genai-prices/blob/main/prices/providers/openai.yml).
- **Retry**: the `AsyncOpenAI` client is built with `max_retries=4, timeout=300` (total 5 attempts) in `client.py`; transient 429/5xx/connection errors recover transparently via the OpenAI SDK's built-in exponential backoff.
- **Conversation TTL**: `prune_runtime_state` in `cogs/openai/state.py` evicts conversations older than `CONVERSATION_TTL` (12h) every 15 minutes via `@tasks.loop`. Caps at `MAX_ACTIVE_CONVERSATIONS` / `MAX_VIEW_STATES`. Daily costs retained for `DAILY_COST_RETENTION_DAYS` (30).
- **Request IDs**: `cog_before_invoke` (and `on_message`) bind a fresh 8-char hex id via `discord_openai.logging_setup.bind_request_id`. All downstream `logger.info`/`warning`/`error` calls automatically include the id. Set `LOG_FORMAT=json` for JSON-lines output.
