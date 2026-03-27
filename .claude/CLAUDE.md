# Discord OpenAI Bot - Claude Code Context

## Repository Overview

Discord bot on Pycord 2.0 integrating OpenAI APIs: chat, image generation, TTS, STT, video, and deep research via `/openai` slash commands.

## Project Structure

```text
src/
├── bot.py              # Main bot entry point, logging configuration
├── openai_api.py       # OpenAI API cog with all slash commands
├── button_view.py      # Discord UI handlers (callback-based, decoupled from cog)
├── util.py             # Parameter classes, pricing, helpers (extract_usage, build_input_content, download_attachment)
└── config/auth.py      # Auth config (BOT_TOKEN, GUILD_IDS, OPENAI_API_KEY)
tests/
├── test_openai_api.py
├── test_util.py
└── test_button_view.py
```

## Commands

All grouped under `/openai` using Pycord's `SlashCommandGroup`.

- **`/openai chat`** (14 params): `prompt`, `persona`, `model`, `attachment`, `frequency_penalty`, `presence_penalty`, `temperature`, `top_p`, `reasoning_effort`, `verbosity`, `web_search`, `code_interpreter`, `file_search`, `shell`
- **`/openai research`** (4 params): `prompt`, `model`, `file_search`, `code_interpreter`
- **`/openai image`**: Image generation and editing (attach an image to edit)
- **`/openai tts`**: Text-to-speech
- **`/openai stt`**: Speech-to-text / transcription
- **`/openai video`**: Sora video generation

## Key Behavioral Rules

### Temperature / Reasoning Restrictions

- `GPT5_NO_TEMP_MODELS` (`gpt-5`, `gpt-5-mini`, `gpt-5-nano`): **never** allow `temperature`/`top_p`
- GPT-5.4/5.2 with `reasoning.effort` ≠ `none`: strip `temperature`/`top_p`
- o-series models default `reasoning.effort` to `medium`; GPT-5.x only sends `reasoning` when explicitly set
- All reasoning dicts include `"summary": "auto"` for reasoning summary output

### Conversation Management

- Tracked per user per channel via `response_id_history` (Responses API `previous_response_id` chaining)
- Pause/resume via button controls; tool toggling via Select Menu
- `ButtonView` is decoupled from the cog via callbacks (`get_conversation`, `on_regenerate`, `on_stop`, `on_tools_changed`) — no direct cog reference
- `_cleanup_conversation(user)` strips button view and removes state on stop/error/end
- `file_search` requires `OPENAI_VECTOR_STORE_IDS`; uses `max_num_results: 5`, `ranking_options` (ranker: auto, score_threshold: 0.3)
- `shell` tool guarded to GPT-5 series models only
- `resolve_selected_tools()` is the single source of truth for tool resolution (used by both `chat` and `research`)

### API Configuration

- `ResponseParameters.to_dict()` is the single source of truth for API call construction (includes `context_management`, `prompt_cache_retention`, `prompt_cache_key`, `safety_identifier`)
- `context_management=[{"type": "compaction", "compact_threshold": 200000}]` on every Responses API call
- `prompt_cache_retention="24h"` on every Responses API call
- `safety_identifier` sent on every Responses API call (SHA-256 hash of Discord user ID, truncated to 16 chars) via `hash_user_id()` in `util.py`
- `prompt_cache_key` derived from SHA-256 hash of system instructions (16 chars)
- Deep research uses `background=True` with 15s polling, 20-min timeout

### Discord Embed Limits

| Field              | Limit           |
|--------------------|-----------------|
| Embed description  | 4096 chars      |
| Total embed        | 6000 chars      |
| User prompts       | 2000 chars      |
| Response chunks    | 3500 chars      |
| TTS input          | 1500 chars      |
| TTS instructions   | 500 chars       |
| Hard truncation    | 20000 chars     |

Research responses are sent as `.md` file attachments to avoid embed limits.

### Attachment Handling

- Images (PNG, JPEG, GIF, WebP) → `image_url` content blocks
- Files (PDF, DOCX, XLSX, CSV, TXT, code) → `input_file` content blocks via `file_url`
- Routing: `build_input_content()` builds text+attachment input; delegates to `build_attachment_content_block()` per attachment
- Downloads: `download_attachment()` in `util.py` handles temp file creation with filename sanitization

### Pricing

All commands show a blue pricing embed (toggle: `SHOW_COST_EMBEDS` env var, default `true`).

- **Token-based** (chat, research): `MODEL_PRICING` dict, cached tokens at 50% input price, `TOOL_CALL_PRICING` per tool call
- **Flat-rate**: `IMAGE_PRICING` by (model, quality, size), `TTS_PRICING_PER_CHAR`, `STT_PRICING_PER_MINUTE`, `VIDEO_PRICING_PER_SECOND`
- Daily costs tracked in-memory per user; structured `COST |` log lines emitted via `logger.info()`
- Token extraction: `extract_usage()` in `util.py` returns `UsageInfo` TypedDict from API responses
- `_track_and_append_cost()` combines usage extraction, daily cost tracking, and pricing embed in one call

## Code Quality

Pre-commit hook (`.githooks/pre-commit`) auto-formats and lints staged Python files in `src/` and `tests/` using ruff. Configuration in `pyproject.toml`:

- **Target:** Python 3.12, 100-column line length
- **Lint rules:** E, W, F, I, UP, B, SIM (E501 ignored — formatter handles it)
- **Behavior:** Format is auto-applied and re-staged; lint violations block the commit
- **Missing ruff:** Hook warns but does not block (soft-fail)

```bash
# One-time setup after cloning (points git to the checked-in hooks directory)
git config core.hooksPath .githooks

# Manual check
ruff check src/ tests/ --config pyproject.toml
ruff format --check src/ tests/ --config pyproject.toml
```

## Running Tests

```bash
# Windows (with venv)
PYTHONPATH=src .venv/Scripts/python.exe -m unittest discover -s tests -v

# Unix/macOS (with venv)
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Environment Variables

| Variable                  | Description                                          |
|---------------------------|------------------------------------------------------|
| `BOT_TOKEN`               | Discord bot token                                    |
| `GUILD_IDS`               | Comma-separated Discord server IDs                   |
| `OPENAI_API_KEY`          | OpenAI API key                                       |
| `OPENAI_VECTOR_STORE_IDS` | Vector store IDs for file_search (optional)          |
| `SHOW_COST_EMBEDS`        | Show cost/token embeds (`true`/`false`, default `true`) |
