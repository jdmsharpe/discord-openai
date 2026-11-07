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
- **Slash-command options cap at 25 static `choices`.** Discord rejects any option with more than 25 entries (error `50035`), and py-cord's startup sync is one all-or-nothing bulk `PUT`, so a single over-limit list (most likely a model menu in `command_options.py`) aborts command registration for **every** cog inside `on_connect`, surfacing only as `Ignoring exception in on_connect`. `CHAT_MODEL_CHOICES` is at 25 of 25. Before adding another model, drop a deprecated one (the 2026-12-11 shutdown batch still in the menu: `gpt-5`, `gpt-5-mini`, `gpt-5-pro`, `o3`, `o3-pro`) or switch that option from `choices=` to an `autocomplete=` callback, which has no length limit. `tests/test_choice_caps.py` discovers every choice list. Discord also caps a command at 25 **options**: `/openai chat` carries 15 (pinned by `test_reasoning_mode_option_is_on_chat_and_pro_models_are_menu_selectable` in `tests/test_openai_cog.py`), and every subcommand's serialized payload must stay under 8000 bytes (`test_registered_command_groups_fit_discord_size_limit`).

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Discord bot token |
| `GUILD_IDS` | Yes | Comma-separated Discord server IDs; at least one is required — empty or unset registers the slash commands **nowhere** (not enforced by `validate_required_config()`) |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_VECTOR_STORE_IDS` | No | Comma-separated vector store IDs for `/openai chat file_search` |
| `OPENAI_MCP_PRESETS_JSON` | No | Inline JSON of named MCP presets |
| `OPENAI_MCP_PRESETS_PATH` | No | Path to JSON file of named MCP presets |
| `SHOW_COST_EMBEDS` | No | Show cost embeds (`true`/`1`/`yes`, default: `true`) |
| `OPENAI_PRICING_PATH` | No | Override the bundled `src/discord_openai/config/pricing.yaml` |
| `LOG_FORMAT` | No | `text` (default) or `json` for structured JSON-lines output |
| `SAFETY_IDENTIFIER_SECRET` | No | HMAC key for the per-user safety identifier (default: derived from `BOT_TOKEN`) |

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
    ├── cost_line.py                 # One-line cost formatter, byte-identical across the discord-* AI bots (change all five together)
    ├── logging_setup.py             # Structured logging + request-id ContextVar
    ├── stickers.py                  # Sticker-to-text labels for follow-ups, byte-identical across the discord-* AI bots (change all five together)
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
        ├── embed_delivery.py   # Discord embed batching (6000-char/10-embed message caps) + plain-text fallback; byte-identical across the five AI bots
        ├── embeds.py
        ├── image.py
        ├── models.py           # Re-export shim for util.py parameter types
        ├── research.py
        ├── responses.py
        ├── speech.py
        ├── state.py
        ├── tool_registry.py
        ├── tooling.py
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
- `tests/test_safety_identifier.py` covers the safety identifier in the chat, chat follow-up, MCP-approval, research, image generate and image edit request bodies, and its absence from the chat, research and image generate bodies when no key is set.
- `tests/test_button_view.py` covers the button-based Discord UI components.
- `tests/test_config_pricing.py` covers YAML pricing load and `OPENAI_PRICING_PATH` override.
- `tests/test_logging_setup.py` covers structured logging and request-id binding.
- `tests/test_embed_delivery.py` covers Discord embed batching and char/count limits.
- `tests/test_attachment_bytes.py` covers in-memory attachment downloads and TTS output (concurrent same-name voice messages, nothing written to disk).
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
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pyright src/
uv run pytest -q
```

- The repo pre-commit hook (`.githooks/pre-commit`) runs `ruff format` (auto-applied + re-staged), then `ruff check` (blocking), then `pyright` and `pytest --collect-only` as warning-only smoke tests. Resolves tools from `.venv/bin` or `.venv/Scripts` first, then `PATH`.

## Provider Notes

Probe results, dates, token counts and the history behind each bold-titled bullet are in [provider-history.md](provider-history.md) under the same title, together with the log of past SDK sweeps. Read the matching entry before changing that area; add new evidence there and keep each bullet here to the rule, the constants to keep aligned and the guarding tests.

- `resolve_selected_tools()` in `discord_openai.cogs.openai.tooling` remains the canonical tool-resolution path for chat and research.
- `file_search` requires `OPENAI_VECTOR_STORE_IDS`.
- `gpt-6-astra`, `gpt-6.1-sol`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano` and the Pro tiers `gpt-5.5-pro` / `gpt-5.4-pro` / `gpt-5.2-pro` / `gpt-5-pro` (`NO_SAMPLING_MODELS`) never accept `temperature` or `top_p` (400 `Unsupported parameter: 'temperature'`, and none of them has a `none` effort to lift the restriction; Astra probed 2026-09-15, the Pro tiers 2026-09-22, GPT-6.1 Sol 2026-10-08 with no effort and at `low`); `ResponseParameters.__init__` silently drops them (`TestGpt6AstraRequestShape` in `tests/test_util.py`, parametrized over Astra and 6.1 Sol).
- **Sampling parameters on reason-by-default models:** `REASONING_BY_DEFAULT_MODELS` (`discord_openai.util`: `gpt-6-sol`, `gpt-6-luna`, `gpt-6.1-terra`, `gpt-5.6-sol` / `-terra` / `-luna`, `gpt-5.5`) reason at medium when the request omits `reasoning.effort` and then return 400 on `temperature` / `top_p`; they accept them only at an explicit effort `none`. `ResponseParameters.__init__` drops both for these models when the effort is omitted, in addition to the existing rules for effort ≠ `none` and for pro mode without an effort. `gpt-5.4` / `5.4-mini` / `5.4-nano` / `5.2` / `5.1`, `gpt-4.1` / `4.1-mini` and `gpt-4o-mini` accept `temperature` with no effort and are in neither set. Guard: `TestSamplingParametersWithoutEffort` (`tests/test_util.py`).
- **Reasoning effort gate:** `SUPPORTED_REASONING_EFFORTS` (`discord_openai.util`) maps every reasoning model in `CHAT_MODEL_CHOICES` (plus the research ids) to its probed effort set: GPT-6 Astra and GPT-6.1 Sol `low`..`max`; GPT-6 Sol / Luna, GPT-6.1 Terra and GPT-5.6 Sol / Terra / Luna `none`..`max`; GPT-5.5 / 5.4 / 5.4 Mini / 5.4 Nano / 5.2 `none`..`xhigh`; GPT-5.1 `none`..`high`; GPT-5 / 5 Mini / 5 Nano `minimal`..`high`; GPT-5.5 Pro / 5.4 Pro / 5.2 Pro `medium` / `high` / `xhigh`; GPT-5 Pro `high` only; o3 / o3 Pro `low` / `medium` / `high`. `reasoning_effort_error()` turns an unsupported combination into an error embed in `run_chat_command` before the request; unmapped ids (GPT-4.1, GPT-4o Mini) pass through unvalidated. Adding a reasoning model to the menu requires probing each effort and adding its row. Guards: `TestSupportedReasoningEfforts` (`tests/test_util.py`) and `test_every_menu_reasoning_model_has_an_effort_entry` (`tests/test_openai_cog.py`).
- **Pro reasoning mode:** the opt-in `/openai chat` `reasoning_mode` option. `PRO_MODE_MODELS` (`discord_openai.util`: GPT-6 Astra / Sol / Luna, GPT-6.1 Sol, GPT-5.6 Sol / Terra / Luna) accept `reasoning.mode = "pro"` with any effort or none; `gpt-5.5` returns 400; `gpt-5.5-pro` accepts it as a no-op and is excluded on purpose; GPT-6.1 Terra is not in the set. `reasoning_mode_error()` runs before `reasoning_effort_error()` in `run_chat_command` and refuses `pro` on every other model; an unset mode and `standard` always pass. `build_reasoning_config(model, reasoning_effort, reasoning_mode)` (`responses.py`) emits `{"summary": "auto", "mode": "pro"}` plus `effort` only when one was chosen and never emits `mode: "standard"`, so models that reject the key never see it. Pro with no explicit effort reasons at medium and returns 400 on `temperature` / `top_p`, so `ResponseParameters.__init__` drops both; pro with effort `none` keeps them. Pro mode costs only inflated standard usage (about 1.5k extra input tokens per call, roughly 4–6x per turn), which `extract_usage` already captures, so `pricing.yaml` and `calculate_cost` are unchanged. The intro embed appends `**Reasoning Mode:** pro`. Probe `mode: pro` on a model before adding it. Guards: `TestReasoningModeError`, `test_pro_mode_without_effort_strips_temperature` / `test_pro_mode_with_effort_none_keeps_temperature` (`tests/test_util.py`), `TestBuildReasoningConfig` (`tests/test_openai_responses.py`), `test_chat_command_rejects_pro_mode_on_unsupported_model_before_request` / `test_chat_command_sends_pro_mode_and_renders_it` (`tests/test_openai_chat.py`), `test_reasoning_mode_choice_set` (`tests/test_openai_cog.py`).
- **Deep research:** defaults to `gpt-6-astra`. `DEEP_RESEARCH_MODELS` is `gpt-6-astra` / `gpt-6.1-sol` / `gpt-6-sol` / `gpt-5.6-sol` / `gpt-5.5` / `gpt-5.5-pro` (in `RESEARCH_MODEL_CHOICES` order), and `ResearchParameters.__init__`, the `/openai-tools research` `model` default and its `(default: GPT-6 Astra)` description must agree. A model joins the research menu only after the bot's exact request (`{model, input, tools: [{"type": "web_search"}], background: True}`, then `responses.retrieve` polling) completes with `web_search_call` items and a `url_citation`; GPT-6 Luna, GPT-6.1 Terra and GPT-5.6 Terra / Luna are not offered. Research sends no reasoning summary. Guards: `TestResearchParameters` (`tests/test_util.py`), `test_command_defaults_are_unchanged` / `test_critical_choice_values_present` (`tests/test_openai_cog.py`), the option-description guard.
- **An `incomplete` response can report all-zero usage.** Probed 2026-08-28: a `max_output_tokens` cut-off on `gpt-5.6-luna` came back `status="incomplete"` with `usage.total_tokens == 0` although tokens were consumed, which `track_and_append_cost` bills as $0.00. It now logs a `BILLING | ... status=incomplete with zero usage` warning when `status == "incomplete"` and input + output tokens are 0 — no behaviour change otherwise. Guards: `test_track_and_append_cost_warns_on_incomplete_response_with_zero_usage` and `test_track_and_append_cost_does_not_warn_when_usage_is_reported` in `tests/test_openai_state.py`.
- **Cached-input rates:** the published cached-input discount differs by generation (90% off for the gpt-5 and gpt-6 families, 95% off for gpt-6.1-sol, 75% off for gpt-4.1 / o3 / o4-mini, 50% off for gpt-4o / o1 / o3-mini), so the 50% fallback in `calculate_cost` is wrong for most of the catalog. Every model with a published rate declares `cached_input_per_million` in `pricing.yaml`; only the Pro tiers and legacy models that publish none may reach the fallback. A deprecated id still has a cached rate on its own model page even when the aggregate table omits it. Cache writes (`usage.input_tokens_details.cache_write_tokens`) are billed at `cache_write_per_million` (1.25x input) on the GPT-6, GPT-6.1 and GPT-5.6 rows only; other rows bill cache-write tokens as ordinary input, and ordinary input = input − cached − cache_write, never negative. `extract_usage` reads the field defensively, and the value is stored as `cache_write_tokens` in `UsageInfo` / `PendingMcpApproval` and passed to `track_daily_cost` and the pricing embed. Guards: `test_declared_cached_rates_match_published`, `test_every_model_declares_or_is_exempt`, `test_gpt_5_6_cache_write_rates_are_125_percent_of_input`, the `test_calculate_cost_cache_write_*` cases (`tests/test_util.py`), `test_older_usage_shape_without_cache_write_field`.
- **Long-context tier:** GPT-5.4 / 5.4 Pro / 5.5 / 5.5 Pro, the GPT-5.6 trio and the GPT-6 / GPT-6.1 models bill the whole request at 2x input / cached / cache-write and 1.5x output once the prompt exceeds 272K input tokens. Declared as a `long_context` block per row in `pricing.yaml` (`threshold_tokens: 272001`), loaded into `LONG_CONTEXT_PRICING` and applied in `calculate_cost` when `input_tokens >= threshold_tokens`; a tier without a cached or cache-write rate falls back to 50% of the tier input or the tier input. Caveat: the MCP-approval continuation sums two responses' usage before costing, so a summed prompt can cross a threshold neither request did. Guards: `test_long_context_tiers_are_pinned` (`tests/test_config_pricing.py`) and the `test_long_context_tier_*` cases in `tests/test_util.py`.
- **Fast mode:** `/openai chat service_tier:fast` sends `service_tier: "fast"` (the API also takes `"priority"`) and bills at the pricing page's Fast-mode rates: 2x standard for the GPT-6 / GPT-6.1 models and the GPT-5.6 trio, other multiples elsewhere. Responses report `"priority"` on GPT-5.6 and earlier and `"fast"` on the GPT-6 models; `FAST_SERVICE_TIERS` is `{"fast", "priority"}`. Each row with fast pricing declares a `fast` block (`FAST_TIER_PRICING` / `FastTier`); GPT-6 Astra / Sol / Luna, GPT-6.1 Sol / Terra and the GPT-5.6 trio also declare `fast.long_context` (2x the standard long-context rates), which `calculate_cost(..., service_tier=...)` applies before the flat fast rate; the fast tier overrides the standard long-context tier. `extract_usage` reads `response.service_tier` into `UsageInfo["service_tier"]`, and every `track_daily_cost` / `append_pricing_embed` / `_append_public_pricing_embed` call passes it through (the embed appends "fast mode"). In `SERVICE_TIER_CHOICES`, `standard` is never sent and `fast` is stored on `ResponseParameters.service_tier` and sent on every turn; `service_tier_error()` rejects `fast` on any model without a fast row before the request. `ultrafast` (6x standard, offered by OpenAI on `gpt-6-astra` and `gpt-6.1-sol` only) is not offered and has no pricing block, so a response reporting `"ultrafast"` (for example from a project default) bills at standard rates; offering it needs an `ultrafast` pricing block, a gate like `service_tier_error` and a choice entry. Guards: `TestFastTiers` (`tests/test_config_pricing.py`), the `test_fast_tier_*` / `TestServiceTierError` / `test_service_tier_*` cases (`tests/test_util.py`), the `test_chat_command_*fast*` / `*standard_tier` cases (`tests/test_openai_chat.py`); the chat option count pin is 15.
- **Transparent image backgrounds:** `IMAGE_BACKGROUND_CHOICES` (`auto` default / `opaque` / `transparent`) is stored on `ImageGenerationParameters.background`; `transparent` sets `output_format: "png"` on both `images.generate` and `images.edit`, because JPEG has no alpha channel. Guards: `test_background_defaults_to_auto_and_transparent_forces_png` (`tests/test_util.py`) and `test_image_background_choice_set` (`tests/test_openai_cog.py`).
- **GPT-5.6 Sol is on a promotional rate** — $4.00 in / $0.40 cached / $5.00 cache-write / $20.00 out per 1M, running until 2026-11-30 per OpenAI (it said at least through 2026-11-21 until 2026-11-06). `test_gpt_5_6_family_rates_are_pinned` and `test_gpt_5_6_cache_write_rates_are_pinned` in `tests/test_config_pricing.py` pin the family's absolute rates; re-verify the pricing page after 2026-11-30 and bump the yaml row and the pins together.
- **openai SDK pin:** `openai~=3.46` (last checked 3.46.0 on 2026-11-06: no removed or retyped parameter on any method the bot calls; the new image parameters `complexity` / `frame_count` / `frame_duration_ms` / `svg` / `markup` and gif / svg output formats, `responses.create`'s `image.context_compression` and `access_programs`, prompt-cache diagnostics and `prompt_cache_options.prewarm` are not wired). `prompt_cache_retention` is still a typed `responses.create` parameter, marked deprecated in favour of `prompt_cache_options.ttl` (GPT-5.6 and newer; `30m` or `12h`, default `30m`), but the API still accepts `24h` on GPT-5.6 and the GPT-6 / GPT-6.1 models and it remains the right setting for older models, so `PROMPT_CACHE_RETENTION` is unchanged; migrate when the SDK or API rejects it. The bot sends no `prompt_cache_options.ttl`, so the 30-minute default and its write rate apply. SDK 3.16.0 deprecates the MCP tool's `connector_id` for models released after 2026-09-01 (see Connector presets on GPT-6 models). Recheck on the next minor bump.
- **GPT-6 Astra (v1.13.0, GA 2026-09-03) is the chat and research default and first in the menu**: $10 in / $1 cached / $12.50 cache-write / $50 out per 1M, long context above 272K input tokens at $20 / $2 / $25 / $75, fast $20 / $2 / $25 / $100 (fast long context $40 / $4 / $50 / $150); 1,050,000-token context, 128K output; efforts `low`..`max`, pro mode accepted, `service_tier: fast` reported back as `fast`. No Pro id and no dated snapshot exist (`gpt-6`, `gpt-6-pro`, `gpt-6-astra-pro` 404 on `models.retrieve`). It is 2.5x Sol's promotional rate per token. Pinned by `test_gpt_6_astra_rates_are_pinned` (`tests/test_config_pricing.py`).
- **GPT-6 Sol and GPT-6 Luna:** in the chat menu after GPT-6 Astra. Per 1M (input / cached / cache-write / output): Sol $2 / $0.20 / $2.50 / $10, long context $4 / $0.40 / $5 / $15, fast $4 / $0.40 / $5 / $20, fast long context $8 / $0.80 / $10 / $30; Luna $0.10 / $0.01 / $0.125 / $0.50, long context $0.20 / $0.02 / $0.25 / $0.75, fast $0.20 / $0.02 / $0.25 / $1, fast long context $0.40 / $0.04 / $0.50 / $1.50. Both: 1,050,000-token context, 128K output; efforts `none`..`max` (unset reasons at medium); `temperature` / `top_p` only at effort `none`; pro mode accepted; `service_tier: priority` reported as `fast`; `prompt_cache_retention: 24h` and the hosted shell tool accepted; connector presets refused. Guards: `test_gpt_6_sol_and_luna_rates_are_pinned`, `test_long_context_tiers_are_pinned`, `TestFastTiers` (`tests/test_config_pricing.py`).
- **GPT-6.1 Sol:** `gpt-6.1-sol`, in the chat menu right after GPT-6 Astra and in the research menu. Per 1M (input / cached / cache-write / output): $2 / $0.10 / $2.50 / $10, long context $4 / $0.20 / $5 / $15, fast $4 / $0.20 / $5 / $20, fast long context $8 / $0.40 / $10 / $30. Cached input is 5% of the input rate, not the 10% of the rest of GPT-5/6 (`CACHED_DISCOUNT_BY_MODEL` in `tests/test_util.py` carries 0.05). 1,050,000-token context, 128K output. Efforts `low`..`max` (unset reasons at medium); `temperature` / `top_p` always return 400 (`NO_SAMPLING_MODELS`); pro mode accepted; `fast` and `priority` reported as `fast`; connector presets refused; the hosted shell tool and `prompt_cache_retention: 24h` accepted. Guards: `test_gpt_6_1_sol_rates_are_pinned`, `test_long_context_tiers_are_pinned`, `TestFastTiers` (`tests/test_config_pricing.py`).
- **GPT-6.1 Terra:** `gpt-6.1-terra`, in the chat menu (it took `gpt-5-nano`'s slot). Per 1M (input / cached / cache-write / output): $1 / $0.05 / $1.25 / $5; prompts over 272K input tokens $2 / $0.10 / $2.50 / $7.50; fast mode doubles both tiers. The cache-write rate is for the default 30-minute retention, not the opt-in 12-hour one. Efforts `none`..`max`, unset starts at medium, so it is in `REASONING_BY_DEFAULT_MODELS` (`temperature` accepted only at effort `none`). Not in `PRO_MODE_MODELS`, the research menu or `CONNECTOR_UNSUPPORTED_MODELS` (not probed with a connector preset).
- **Chat model shutdowns:** `gpt-5`, `gpt-5-mini`, `gpt-5-pro`, `o3` and `o3-pro` shut down on 2026-12-11 (replacements GPT-5.6 Sol / Terra / Luna, and GPT-5.6 Sol with `reasoning.mode: pro` for the Pro tiers); `gpt-5-nano` (same date) has already left the menu. `gpt-5.1` (replacement `gpt-6-sol`) and `gpt-5.4-nano` (replacement `gpt-6-luna`) shut down on 2027-04-01. The bare aliases and dated snapshots behind the menu ids `gpt-4.1`, `gpt-4.1-mini` and `gpt-4o-mini` and the pricing-only `gpt-4o` row shut down on 2027-01-14 (replacement `gpt-6-luna`). Each stays in `CHAT_MODEL_CHOICES`, `SUPPORTED_REASONING_EFFORTS` and `pricing.yaml` until its date; on removal keep the pricing row for historical costing.
- **Image cost:** OpenAI bills GPT Image models per token and the Images API reports the usage on every response (`usage.input_tokens_details.text_tokens` / `image_tokens`, `usage.output_tokens_details.image_tokens`); `calculate_image_cost_from_usage(model, response.usage)` prices it with `IMAGE_TOKEN_PRICING` (the `per_million_tokens` block of each `image_generation` row: $5 text in / $8 image in / $30 image out on GPT Image 2, 2.5 and 2.6, $32 out on 1.5, $2 / $2.50 / $8 on 1-mini). The per-image table (`calculate_image_cost`, keyed by the quality and size the response echoes) is only the fallback, because an `auto` request resolves server-side to a quality and size it cannot predict; for 2.6 its low and medium cells are measured and the high / xhigh / max cells reuse the 2.5 values. GPT Image 2.6 Sunburst is the `/openai-media image` default, followed by 2.6 Flare and the 2.5 pair (7 of 25 choices); a default request costs about $0.020. `xhigh` / `max` qualities are allowed only on `EXTENDED_IMAGE_QUALITY_MODELS` (the 2.5 and 2.6 pairs; gpt-image-2 returns 400) by `image_quality_error`. The `complexity` parameter does not change the token count and is not sent. Batch is not supported on 2.5. GPT Image 2.6 is the named replacement for `gpt-image-1.5` and `gpt-image-1-mini`, which shut down on 2026-12-01 and stay in the menu until then. Guards: `TestImageCostFromUsage` / `TestImageQualityGate` (`tests/test_util.py`), `test_image_token_rates_are_pinned` / `test_gpt_image_2_5_per_image_rows` / `test_gpt_image_2_6_per_image_rows` (`tests/test_config_pricing.py`).
- TTS: `gpt-4o-mini-tts` is the only rich-voice model (`RICH_TTS_MODELS`). The never-shipped full-size `gpt-4o` TTS id was removed from `RICH_TTS_MODELS`, `MODEL_SUPPORTED_TTS_VOICES`, and pricing.yaml in v1.9.0 — it was never menu-selectable, so it is not a retired-id pricing row. `test_tts_model_maps_only_cover_menu_models` in `tests/test_openai_cog.py` keeps those maps aligned with `TTS_MODEL_CHOICES`.
- **TTS deprecation (announced 2026-10-01):** `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts-2025-03-20` and `gpt-4o-mini-tts-2025-12-15` shut down on **2027-01-06**. The bare `gpt-4o-mini-tts` alias is also scheduled to shut down on that date (confirmed in SDK 3.41 documentation on 2026-10-28), so every model in `TTS_MODEL_CHOICES` is affected. The named replacement, `gpt-realtime-2.1-mini`, lists `v1/audio/speech` as not supported, so `/openai-tools tts` has no successor model on the Speech endpoint. All three stay as choices until then; before 2027-01-06, remove the command or move it to a model OpenAI ships for the Speech endpoint.
- STT default is **`gpt-transcribe`** ($0.0045/min, 25% cheaper than the previous `gpt-4o-transcribe` default) and it is the only transcription model returning the `languages` response field. Its `keywords`/`languages` **request** params are model-gated — `gpt-4o-transcribe` returns a 400 on `keywords` (live-probed 2026-08-12) — so exposing them needs a per-model rejection branch plus a guard test; deliberately not wired yet.
- **STT deprecation:** `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe` and `gpt-4o-transcribe-diarize` shut down on 2027-02-26 (replacements `gpt-transcribe` / `gpt-live-transcribe`); all four stay in `STT_MODEL_CHOICES` and `pricing.yaml` until then. The `translation` action in `speech.py` hard-codes `whisper-1` for `/audio/translations`; no other model supports that endpoint, and the endpoint itself shuts down the same day (replacement `v1/realtime/translations`, a WebSocket API), so the action must be removed or reworked before 2027-02-26.
- **The Videos API surface was removed on 2026-09-22** (`/openai-media video`, `video.py`, `VIDEO_*_CHOICES`, `VideoGenerationParameters`, `calculate_video_cost`, `VIDEO_SIZE_RESOLUTIONS`, the `video_generation` pricing block and the `unknown_video_model` fallback), ahead of OpenAI's shutdown of the whole Videos API (`sora-2`, `sora-2-pro`, no successor) on 2026-09-24. `append_flat_pricing_embed` stays (image and speech use it). The option-description guard (`EXPECTED_ASSERTABLE_OPTIONS` in `tests/test_option_defaults.py`) dropped from 14 to 11 with the video command's `model` / `size` / `seconds` options, and `/openai-media` now carries only `image`.
- The Responses API has no `frequency_penalty`/`presence_penalty` parameters (SDK raises `TypeError` client-side); those slash options were removed in v1.6.0 after being dead-broken since the Responses migration.
- `shell` is offered on GPT-5 and GPT-6 series models (`_shell_availability` in `tool_registry.py`). Until 2026-09-22 the check was `model.startswith("gpt-5")`, so `/openai chat shell:true` was refused on the default GPT-6 Astra although the API accepts the hosted shell tool (`{"type": "shell", "environment": {"type": "container_auto"}}`) on gpt-6-astra, gpt-6-sol and gpt-6-luna (probed 2026-09-22) and on gpt-6.1-sol (2026-10-08; the `gpt-6` prefix already allows it). Guard: `test_resolve_selected_tools_allows_shell_on_gpt_6_models` in `tests/test_openai_cog.py`.
- `ResponseParameters.to_dict()` in `discord_openai.util` remains the canonical request-construction path.
- **Per-user safety identifier:** `build_safety_identifier(user_id)` (`discord_openai.util`) returns `HMAC-SHA256(key, str(user_id)).hexdigest()` (64 lowercase hex characters, untruncated; the Responses API limit is 128). The key is `SAFETY_IDENTIFIER_SECRET` when set, otherwise `HMAC-SHA256(BOT_TOKEN, b"safety-identifier-v1")` (`derive_safety_identifier_key`, computed once at import into `SAFETY_IDENTIFIER_KEY`); with neither it returns `None` and no identifier is sent. Never use the OpenAI API key as key material; `validate_required_config` refuses a `SAFETY_IDENTIFIER_SECRET` equal to `OPENAI_API_KEY`. It is sent as `safety_identifier` on `responses.create` for chat (`ResponseParameters`, so every follow-up and MCP-approval turn too) and research (`ResearchParameters`), and on `images.generate` / `images.edit` (`ImageGenerationParameters.safety_identifier`). `audio.speech`, `audio.transcriptions` and `audio.translations` accept no identifier, so TTS and STT send nothing. The construction, env var and label are shared with discord-claude, discord-grok and discord-openrouter; change all four together. Changing the secret, or `BOT_TOKEN` when no secret is set, changes every user's identifier. Guards: `TestSafetyIdentifier` / `TestDeriveSafetyIdentifierKey` (`tests/test_util.py`), the `SAFETY_IDENTIFIER_SECRET` cases in `tests/test_config_auth.py` (including `test_validate_required_config_rejects_the_api_key_as_safety_secret`), `tests/test_safety_identifier.py`.
- Named MCP presets are loaded from `OPENAI_MCP_PRESETS_JSON` and `OPENAI_MCP_PRESETS_PATH`; when both are set they merge additively, and duplicate preset names are rejected.
- Presets support both remote MCP servers (`kind="remote_mcp"`) and OpenAI connectors (`kind="connector"`).
- **Connector presets on GPT-6 models:** an `mcp` tool carrying `connector_id` returns 400 on `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna` and `gpt-6.1-sol`; GPT-5.6 and earlier accept it. `mcp_connector_error(model, presets)` (`config/mcp.py`) refuses any `kind="connector"` preset on `CONNECTOR_UNSUPPORTED_MODELS` (those four ids) and names the alternatives (a `remote_mcp` preset, or GPT-5.6 or earlier); `resolve_selected_tools()` calls it after `resolve_mcp_presets()`, which covers the chat start, the tool selector and follow-up turns. Remote MCP presets are unaffected. Guards: `TestMcpConnectorError` (`tests/test_openai_mcp_config.py`), `test_resolve_selected_tools_refuses_connector_preset_on_gpt_6` (`tests/test_openai_tooling.py`), `test_chat_command_rejects_connector_preset_on_default_model_before_request` (`tests/test_openai_chat.py`).
- `authorization_env_var` names are user-defined token env vars that must be present at runtime for those presets to be available.
- MCP state is persisted separately from built-in tool selections via `tool_names`, `mcp_preset_names`, and `pending_mcp_approval`.
- While an approval is pending, the bot swaps to `McpApprovalView`, blocks typed follow-ups, and resumes the same response chain with `mcp_approval_response` when the owner approves or denies.
- **Stickers are sent as text:** `handle_new_message_in_conversation` (`chat.py`) sends each sticker in `message.stickers` as a `[Sticker: <name>]` line after the message text, built by `text_with_stickers` in `stickers.py` (byte-identical in the five AI bots; change all five together). The sticker image is not sent. A follow-up with nothing to send is ignored and the conversation stays open. Guards: `tests/test_stickers.py` and the sticker follow-up tests in `tests/test_openai_chat.py`.

## Runtime Conventions (Cross-Project)

- **Pricing** is loaded from `src/discord_openai/config/pricing.yaml` by `config/pricing.py` at import time. Override via `OPENAI_PRICING_PATH` to push a vendor price change without a code release. Cross-referenced against [genai-prices/openai.yml](https://github.com/pydantic/genai-prices/blob/main/prices/providers/openai.yml).
- **Retry**: the `AsyncOpenAI` client is built with `max_retries=4, timeout=300` (total 5 attempts) in `client.py`; transient 429/5xx/connection errors recover transparently via the OpenAI SDK's built-in exponential backoff.
- **Conversation TTL**: `prune_runtime_state` in `cogs/openai/state.py` evicts conversations older than `CONVERSATION_TTL` (12h) every 15 minutes via `@tasks.loop`. Caps at `MAX_ACTIVE_CONVERSATIONS` / `MAX_VIEW_STATES`. Daily costs retained for `DAILY_COST_RETENTION_DAYS` (30).
- **Request IDs**: `cog_before_invoke` (and `on_message`) bind a fresh 8-char hex id via `discord_openai.logging_setup.bind_request_id`. All downstream `logger.info`/`warning`/`error` calls automatically include the id. Set `LOG_FORMAT=json` for JSON-lines output.
- **Async file I/O**: blocking `open()` and `pathlib` methods (`read_bytes`, `write_bytes`, `unlink`, etc.) inside `async def` freeze the Discord event loop and stall every concurrent slash command. Wrap them with `asyncio.to_thread(...)` so the I/O runs on a worker thread. Enforced by `ruff` (`ASYNC230`/`ASYNC240`).
- **Attachments and generated audio stay in memory:** `fetch_attachment_bytes(url)` (`discord_openai.util`) returns an attachment's bytes; STT, translation and image edit send them as `(filename, bytes)` tuples, and the STT and TTS replies attach a `BytesIO` (TTS uses `response.content`). Nothing is written to disk. Do not reintroduce temp files: Discord voice messages are always named `voice-message.ogg`, so a fixed temp path is shared between concurrent users. Guard: `tests/test_attachment_bytes.py` (`TestSpeechToText`, `TestTextToSpeech`, `TestImageEdit`; the temp and working directories are read-only there, so any file write fails the test).
