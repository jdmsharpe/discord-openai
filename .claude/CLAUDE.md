# Discord OpenAI Bot - Developer Reference

## Quick Start

```bash
cp .env.example .env          # fill in BOT_TOKEN and OPENAI_API_KEY at minimum
uv sync --extra dev           # creates .venv from uv.lock (no pip inside — use `uv pip` if needed)
git config core.hooksPath .githooks   # enable repo pre-commit hook
uv run python src/bot.py       # or: docker compose up
```

## Gotchas

- Uses **`py-cord`** (not `discord.py`). The slash-command API differs; don't mix docs between the two.
- `GUILD_IDS` must list at least one guild ID. Empty or unset → `_parse_guild_ids("")` returns `[]`, and py-cord only treats `guild_ids is None` as global, so the commands register **nowhere** — not globally, not per-guild.
- **Slash-command options cap at 25 static `choices`.** Discord rejects any option with >25 entries (error `50035`), and py-cord's startup sync is one all-or-nothing bulk `PUT` — so a single over-limit list (most likely a model menu in `command_options.py`) aborts command registration for **every** cog inside `on_connect`, surfacing only as `Ignoring exception in on_connect`. `CHAT_MODEL_CHOICES` currently sits at 21 of 25 (GPT-5.6 Sol/Terra/Luna added in v1.6.0 into room pre-cleared by the v1.5.0 prune), so there is limited headroom; when it next approaches 25, drop a deprecated model or — to escape the cap permanently — switch that option from `choices=` to an `autocomplete=` callback (no length limit). `REASONING_MODE_CHOICES` (2 entries, v1.10.0) is picked up by the same `tests/test_choice_caps.py` discovery. Separately, Discord caps a command at 25 **options**: `/openai chat` carries 14 since `reasoning_mode` landed in v1.10.0 (pinned by `test_reasoning_mode_option_is_on_chat_and_pro_models_are_menu_selectable` in `tests/test_openai_cog.py`), and every subcommand's serialized payload must stay under 8000 bytes (`test_registered_command_groups_fit_discord_size_limit`).

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Discord bot token |
| `GUILD_IDS` | No | Comma-separated Discord server IDs; not enforced by `validate_required_config()`, but leaving it empty registers the slash commands **nowhere** — set at least one guild ID |
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
        ├── command_options.py  # OptionChoice lists for slash-command model/voice/etc. menus
        ├── embed_delivery.py   # Discord embed batching (6000-char/10-embed message caps)
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
- `tests/test_config_pricing.py` covers YAML pricing load and `OPENAI_PRICING_PATH` override.
- `tests/test_logging_setup.py` covers structured logging and request-id binding.
- `tests/test_embed_delivery.py` covers Discord embed batching and char/count limits.
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
- **Reasoning effort is gated per model before the request.** `SUPPORTED_REASONING_EFFORTS` in `discord_openai.util` maps every reasoning model in `CHAT_MODEL_CHOICES` (plus the research ids) to its live-probed effort set — probed 2026-07-13 (5.6 `minimal`) and 2026-08-28 (the rest) with the bot's own payload and `max_output_tokens=16`: GPT-5.6 Sol/Terra/Luna take `none`/`low`/`medium`/`high`/`xhigh`/`max` (reject `minimal`); GPT-5.5/5.4/5.4 Mini/5.4 Nano/5.2 take `none`..`xhigh`; GPT-5.1 `none`..`high`; GPT-5/5 Mini/5 Nano `minimal`..`high` (reject `none`); GPT-5.5 Pro/5.4 Pro/5.2 Pro `medium`/`high`/`xhigh`; GPT-5 Pro `high` only; o3/o3 Pro `low`/`medium`/`high`. `reasoning_effort_error()` turns an unsupported menu combination into a friendly error embed in `run_chat_command` instead of a raw 400; unmapped ids (GPT-4.1, GPT-4o Mini, un-probed o-series) pass through unvalidated. Guards: `TestSupportedReasoningEfforts` in `tests/test_util.py` (exact map pin + accept/reject cases) and `test_every_menu_reasoning_model_has_an_effort_entry` in `tests/test_openai_cog.py` — adding a reasoning model to the menu requires probing each effort and adding its row.
- **Pro reasoning mode is an opt-in `/openai chat` option (`reasoning_mode`), gated per model before the request.** `PRO_MODE_MODELS` in `discord_openai.util` is the live-probed set (2026-08-28, bot payload): GPT-5.6 Sol/Terra/Luna accept `reasoning.mode = "pro"` with any effort (`none`..`max`) or none at all; `gpt-5.5` returns a 400 `unsupported_value` on `reasoning.mode`; `gpt-5.5-pro` accepts it as a no-op and is excluded on purpose. `reasoning_mode_error()` runs before `reasoning_effort_error()` in `run_chat_command` and refuses `pro` on every other model via the error embed (it lists the three ids); an unset mode and `standard` always pass. `build_reasoning_config(model, reasoning_effort, reasoning_mode)` in `responses.py` emits `{"summary": "auto", "mode": "pro"}` plus `effort` only when one was chosen, and **never emits `mode: "standard"`** — the key is omitted so models that reject it never see it. Temperature rule: pro with no explicit effort reasons at the API default (medium) and 400s on `temperature`/`top_p` (`Unsupported parameter: 'temperature'`), so `ResponseParameters.__init__` drops both; pro with effort `none` keeps them. Mode and effort are independent, and the cost is plain inflated standard usage (~1.5k fixed input tokens per call, roughly 4-6x per turn, tool schemas and history multiplied) that `extract_usage` already captures, so pricing.yaml and `calculate_cost` are untouched. The intro embed appends `**Reasoning Mode:** pro`. Guards: `TestReasoningModeError` (exact set pin, accept/reject cases) and `test_pro_mode_without_effort_strips_temperature` / `test_pro_mode_with_effort_none_keeps_temperature` in `tests/test_util.py`; `TestBuildReasoningConfig` in `tests/test_openai_responses.py`; `test_chat_command_rejects_pro_mode_on_unsupported_model_before_request` and `test_chat_command_sends_pro_mode_and_renders_it` in `tests/test_openai_chat.py`; `test_reasoning_mode_choice_set` in `tests/test_openai_cog.py`. Adding a model to `PRO_MODE_MODELS` requires probing `mode: pro` on it first and updating the pin.
- **Deep research defaults to `gpt-5.6-sol`** (v1.10.0). `DEEP_RESEARCH_MODELS` is `gpt-5.6-sol` / `gpt-5.5` / `gpt-5.5-pro`, and `ResearchParameters.__init__`, the `/openai-tools research` `model` option default, and its `(default: GPT-5.6 Sol)` description all agree — pinned by `TestResearchParameters` in `tests/test_util.py`, `test_command_defaults_are_unchanged` / `test_critical_choice_values_present` in `tests/test_openai_cog.py`, and the option-description guard. Promoted after an end-to-end probe on 2026-08-28: `background=True` + `web_search` completes with output text and `url_citation` in the bot's exact unguarded payload, `medium`/`xhigh`/`max` efforts are accepted, and Sol is ~17% cheaper than 5.5. Terra/Luna are deliberately not research choices (unprobed), and research sends no reasoning summary (opt-in, not requested).
- **An `incomplete` response can report all-zero usage.** Probed 2026-08-28: a `max_output_tokens` cut-off on `gpt-5.6-luna` came back `status="incomplete"` with `usage.total_tokens == 0` although tokens were consumed, which `track_and_append_cost` bills as $0.00. It now logs a `BILLING | ... status=incomplete with zero usage` warning when `status == "incomplete"` and input + output tokens are 0 — no behaviour change otherwise. Guards: `test_track_and_append_cost_warns_on_incomplete_response_with_zero_usage` and `test_track_and_append_cost_does_not_warn_when_usage_is_reported` in `tests/test_openai_state.py`.
- **Cached-input rates must be declared per model, never inferred.** The published discount varies by generation — 90% off for the gpt-5 family, 75% off for gpt-4.1/o3/o4-mini, 50% off for gpt-4o/o1/o3-mini — so the 50% fallback in `calculate_cost` is wrong for most of the catalog and has silently misbilled twice (5× on gpt-5, 2× on gpt-4.1/o3). Every model with a published rate carries `cached_input_per_million` in pricing.yaml; the only ids allowed to reach the fallback are the Pro tiers and legacy models that genuinely publish none. Two guards pin this: `test_declared_cached_rates_match_published` (rate == input × expected discount) and `test_every_model_declares_or_is_exempt` (no model may silently rely on the fallback). When adding a model, look up its cached rate — a deprecated id still has one on its own model page even when the aggregate pricing table omits it. GPT-5.6 additionally bills **cache writes** (`usage.input_tokens_details.cache_write_tokens`, populated on first-turn requests) at 1.25× the uncached input rate: `cache_write_per_million` is declared on the three gpt-5.6 rows only (every other row prints `-` in the table's Cache-writes column, so `calculate_cost` bills their cache-write tokens as ordinary input), and ordinary input = input − cached − cache_write, never negative. Guards: `test_gpt_5_6_cache_write_rates_are_125_percent_of_input` (declared set == gpt-5.6 rows, rate == 1.25× input) plus the `test_calculate_cost_cache_write_*` cases in `tests/test_util.py`; `extract_usage` reads the field defensively (`test_older_usage_shape_without_cache_write_field`) and the value flows through `UsageInfo`/`PendingMcpApproval` into `track_daily_cost` and the pricing embed as `cache_write_tokens`.
- **GPT-5.6 Sol is on a promotional rate** — $4.00 in / $0.40 cached / $5.00 cache-write / $20.00 out per 1M, guaranteed at least through 2026-11-21 (changelog 2026-08-21). `test_gpt_5_6_family_rates_are_pinned` and `test_gpt_5_6_cache_write_rates_are_pinned` in `tests/test_config_pricing.py` pin the family's absolute rates; re-verify the pricing page after that date and bump the yaml row and the pins together.
- openai SDK pin `~=3.6` (last checked 3.6.0 on 2026-08-28). `prompt_cache_retention` is deprecated in the SDK in favour of `prompt_cache_options.ttl` (GPT-5.6+ only; `30m` is the only ttl), but the API still accepts `24h` on gpt-5.6 (probed 2026-08-28) and it stays the right knob for older models, so `PROMPT_CACHE_RETENTION` is unchanged — migrate when the SDK or API rejects it.
- TTS: `gpt-4o-mini-tts` is the only rich-voice model (`RICH_TTS_MODELS`). The never-shipped full-size `gpt-4o` TTS id was removed from `RICH_TTS_MODELS`, `MODEL_SUPPORTED_TTS_VOICES`, and pricing.yaml in v1.9.0 — it was never menu-selectable, so it is not a retired-id pricing row. `test_tts_model_maps_only_cover_menu_models` in `tests/test_openai_cog.py` keeps those maps aligned with `TTS_MODEL_CHOICES`.
- STT default is **`gpt-transcribe`** ($0.0045/min, 25% cheaper than the previous `gpt-4o-transcribe` default) and it is the only transcription model returning the `languages` response field. Its `keywords`/`languages` **request** params are model-gated — `gpt-4o-transcribe` returns a 400 on `keywords` (live-probed 2026-08-12) — so exposing them needs a per-model rejection branch plus a guard test; deliberately not wired yet.
- The Responses API has no `frequency_penalty`/`presence_penalty` parameters (SDK raises `TypeError` client-side); those slash options were removed in v1.6.0 after being dead-broken since the Responses migration.
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
- **Async file I/O**: blocking `open()` and `pathlib` methods (`read_bytes`, `write_bytes`, `unlink`, etc.) inside `async def` freeze the Discord event loop and stall every concurrent slash command. Wrap them with `asyncio.to_thread(...)` so the I/O runs on a worker thread. Enforced by `ruff` (`ASYNC230`/`ASYNC240`).
