# Changelog

## v1.1.0

### feat
- Build `AsyncOpenAI` with `max_retries=4` and `timeout=300` (5 total attempts) so transient 429/5xx/connection errors recover transparently via the OpenAI SDK's built-in exponential backoff.
- Extract `MODEL_PRICING`, `TOOL_CALL_PRICING`, `IMAGE_PRICING`, `IMAGE_PRICING_DEFAULTS`, `TTS_PRICING_PER_CHAR`, `STT_PRICING_PER_MINUTE`, and `VIDEO_PRICING_PER_SECOND` from `util.py` into `src/discord_openai/config/pricing.yaml`, loaded by `src/discord_openai/config/pricing.py`; override at runtime via `OPENAI_PRICING_PATH` to push a vendor price change without a code release.
- Add `src/discord_openai/logging_setup.py` with `REQUEST_ID` (`ContextVar`), `bind_request_id()`, and `configure_logging()`; `cog_before_invoke` and `on_message` bind a fresh 8-char hex id so all downstream logs correlate, and `LOG_FORMAT=json` switches to JSON-lines output.

### fix
- Correct 11 stale OpenAI prices (discovered by cross-referencing [genai-prices/openai.yml](https://github.com/pydantic/genai-prices/blob/main/prices/providers/openai.yml)) so cost embeds are accurate for billing:
  - `gpt-5-pro`: 5/20 -> **15/120** (was 3-6x low)
  - `gpt-5.4-pro`: 3/12 -> **30/180** (10x low)
  - `gpt-5.2-pro`: 3/12 -> **21/168**
  - `o3`: 10/40 -> **2/8** (bot was overpaying by 5x)
  - `gpt-5`: 2/8 -> **1.25/10**
  - `gpt-5.1`: 2/8 -> **1.25/10**
  - `gpt-5.2`: 2/8 -> **1.75/14**
  - `gpt-5.4`: 2/8 -> **2.50/15**
  - `gpt-5-mini`: 0.40/1.60 -> **0.25/2**
  - `gpt-5-nano`: 0.10/0.40 -> **0.05/0.40**
  - `o4-mini-deep-research`: 1.10/4.40 -> **2/8**

### chore
- Bump project version to `1.1.0`.
- Add `PyYAML~=6.0` runtime dependency for the YAML pricing loader.
- Canonicalize `.githooks/pre-commit` across all 6 discord-* repos: `ruff format` (auto-applied + re-staged), `ruff check` (blocking), `pyright` (warning-only), `pytest --collect-only` (warning-only smoke).

### test
- Add 7 tests for the YAML pricing loader in `tests/test_config_pricing.py` (bundled defaults, `OPENAI_PRICING_PATH` override, malformed-file handling).
- Add 8 tests for structured logging in `tests/test_logging_setup.py` (`REQUEST_ID` ContextVar isolation, `bind_request_id()` behavior, text vs JSON formatter output).
- Total test count goes from 220 to 235.

### docs
- Refresh `README.md` with the new `OPENAI_PRICING_PATH` and `LOG_FORMAT` env vars.
- Update `.claude/CLAUDE.md` with pricing YAML, retry, and request-id runtime conventions.

### compare
- [`v1.0.2...v1.1.0`](https://github.com/jdmsharpe/discord-openai/compare/v1.0.2...v1.1.0)
