# Discord OpenAI Bot - Claude Code Context

## Repository Overview

This is a Discord bot built on Pycord 2.0 that integrates multiple OpenAI APIs to provide conversational AI, image generation, text-to-speech, speech-to-text, and video generation capabilities via Discord slash commands.

## Project Structure

```text
discord-chatgpt/
├── src/
│   ├── bot.py              # Main bot entry point
│   ├── openai_api.py       # OpenAI API cog with all slash commands
│   ├── button_view.py      # Discord UI handlers (regenerate, pause, stop, tool select)
│   ├── util.py             # Parameter classes and utility functions
│   └── config/
│       └── auth.py         # Authentication configuration (BOT_TOKEN, GUILD_IDS, OPENAI_API_KEY)
├── tests/
│   ├── test_openai_api.py  # Tests for OpenAI API commands
│   ├── test_util.py        # Tests for parameter classes and utilities
│   └── test_button_view.py # Tests for button interactions
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker build configuration
└── docker-compose.yaml     # Docker compose configuration
```

## Key Components

### Parameter Classes (`src/util.py`)

- **ResponseParameters**: Parameters for the Responses API (used by `/openai chat`)
  - Supports `previous_response_id` for conversation chaining
  - Handles reasoning models (o-series) with `reasoning` parameter; supports `none/low/medium/high/xhigh` effort levels
  - `GPT5_NO_TEMP_MODELS` (`gpt-5`, `gpt-5-mini`, `gpt-5-nano`) never allow `temperature`/`top_p`
  - For GPT-5.4/5.2, `temperature`/`top_p` are stripped when `reasoning.effort` is not `none`
  - Supports `verbosity` (`low`/`medium`/`high`) via `text: {verbosity: ...}` in the API payload
  - Supports `tools` for built-in tool calling (`web_search`, `code_interpreter`, `file_search`, `shell`)
  - Discord-specific fields for conversation management

- **ImageGenerationParameters**: Parameters for image generation
  - Supports GPT Image 1.5, GPT Image 1, GPT Image 1 Mini (DALL-E models removed)
  - Defaults: quality `auto`, size `auto`

- **ResearchParameters**: Parameters for deep research
  - Supports `o3-deep-research` and `o4-mini-deep-research` models
  - Optional `file_search` and `code_interpreter` toggles
  - Always includes `web_search` tool; uses `background=True` mode

- **VideoGenerationParameters**: Parameters for Sora video generation
  - Supports `sora-2` and `sora-2-pro` models
  - Size options including 1080p (sora-2-pro only) and duration (4/8/12/16/20 seconds)

- **TextToSpeechParameters**: Parameters for TTS
  - 13 voices with model-specific validation (default: `marin`, fallback: `coral` for non-rich models)
  - Rich voice instructions for GPT-4o models

- **ChatCompletionParameters**: Legacy parameters (kept for reference)

### Commands (`src/openai_api.py`)

All commands are grouped under the `/openai` slash command group using Pycord's `SlashCommandGroup`.

| Command  | Field            | Limit              | Reason                           |
|----------|------------------|--------------------|----------------------------------|
| chat     | user prompt      | 2000 chars         | Leave room for metadata          |
| chat     | model response   | 3500 char chunks   | Via `append_response_embeds()`   |
| image    | user prompt      | 2000 chars         | Leave room for metadata          |
| tts      | input text       | 1500 chars         | Leave room for instructions      |
| tts      | instructions     | 500 chars          | Secondary field                  |
| research | user prompt      | 2000 chars         | Leave room for metadata          |
| research | model response   | sent as .md file   | Avoids embed size limits         |
| video    | user prompt      | 2000 chars         | Leave room for metadata          |
| stt      | transcription    | 3500 chars         | Primary output field             |

`/openai chat` parameters (14 total): `prompt`, `persona`, `model`, `attachment`, `frequency_penalty`, `presence_penalty`, `temperature`, `top_p`, `web_search`, `code_interpreter`, `file_search`, `shell`, `reasoning_effort`, `verbosity`.

`/openai research` parameters (4 total): `prompt`, `model`, `file_search`, `code_interpreter`.

### Conversation Management

- Conversations are tracked per user per channel
- `response_id_history` enables regeneration by reverting to previous response IDs
- Pause/resume functionality via button controls
- Tool enable/disable toggling via Select Menu on conversation views
- `file_search` requires `OPENAI_VECTOR_STORE_IDS` in environment config; uses `max_num_results: 5` to limit retrieval; file citations are surfaced in a Sources embed
- `shell` is guarded to GPT-5 series models in this bot configuration
- Automatic conversation state cleanup on stop

### Discord Embed Limits

Discord enforces strict limits on embed content. The bot handles these automatically:

| Limit                  | Value       |
|------------------------|-------------|
| Embed description      | 4096 chars  |
| Total embed content    | 6000 chars  |

**Truncation strategy by command:**

| Command  | Field            | Limit              | Reason                           |
|----------|------------------|--------------------|----------------------------------|
| chat     | user prompt      | 2000 chars         | Leave room for metadata          |
| chat     | model response   | 3500 char chunks   | Via `append_response_embeds()`   |
| image    | user prompt      | 2000 chars         | Leave room for metadata          |
| tts      | input text       | 1500 chars         | Leave room for instructions      |
| tts      | instructions     | 500 chars          | Secondary field                  |
| video    | user prompt      | 2000 chars         | Leave room for metadata          |
| stt      | transcription    | 3500 chars         | Primary output field             |

**Key functions:**

- `append_response_embeds()` in `openai_api.py` - Chunks model responses into 3500 char segments with 20000 char hard truncation
- `append_sources_embed()` in `openai_api.py` - Renders web citations (numbered links) and file citations (filename list) in a Sources embed
- `append_pricing_embed()` in `openai_api.py` - Appends a blue embed showing request cost, token counts (with cached/thinking annotations), tool call costs, and daily cumulative cost (controlled by `SHOW_COST_EMBEDS` env var)
- `append_flat_pricing_embed()` in `openai_api.py` - Appends a compact blue pricing embed for non-token commands (image, TTS, STT, video) showing cost, details, and daily total
- `extract_tool_info()` in `openai_api.py` - Extracts tool usage, call counts per tool, `url_citation` annotations (web), and `file_citation` annotations (file search) from Responses API output
- `build_attachment_content_block()` in `util.py` - Routes Discord attachments to `image_url` (images) or `input_file` (PDFs, docs, spreadsheets, code files) content blocks
- `calculate_cost()` in `util.py` - Calculates dollar cost from model name and token counts using `MODEL_PRICING`; cached tokens billed at 50% input price
- `calculate_tool_cost()` in `util.py` - Calculates dollar cost for tool calls using `TOOL_CALL_PRICING`
- `calculate_image_cost()` in `util.py` - Calculates image generation cost from `IMAGE_PRICING` table keyed by (model, quality, size); falls back to `IMAGE_PRICING_DEFAULTS` for "auto" values
- `calculate_tts_cost()` in `util.py` - Estimates TTS cost from character count using `TTS_PRICING_PER_CHAR`
- `calculate_stt_cost()` in `util.py` - Estimates STT cost from audio duration using `STT_PRICING_PER_MINUTE`
- `estimate_audio_duration_seconds()` in `util.py` - Estimates audio duration from file size and format (WAV vs compressed)
- `calculate_video_cost()` in `util.py` - Calculates video generation cost from `VIDEO_PRICING_PER_SECOND`
- `truncate_text()` in `util.py` - Truncates text with suffix (e.g., `truncate_text(prompt, 2000)` → "text...")
- `chunk_text()` in `util.py` - Splits text into 3500 char segments (configurable via `CHUNK_TEXT_SIZE`)

### Attachment Handling

The `/openai chat` `attachment` parameter supports images and file inputs:

- **Images** (PNG, JPEG, GIF, WebP): sent as `image_url` content blocks
- **Files** (PDF, DOCX, XLSX, CSV, TXT, code files, etc.): sent as `input_file` content blocks using the `file_url` field

Routing is handled by `build_attachment_content_block()` in `util.py`, which checks the Discord attachment's `content_type`. This works both for the initial slash command and follow-up messages in a conversation.

## Recent Changes (March 2026)

### GPT-5.4 Parameter Compatibility (`/openai chat`)

- Added `reasoning_effort` slash command option: `none` (fastest), `low`, `medium`, `high`, `xhigh` (GPT-5.4 only)
  - For o-series models, defaults to `medium` when not set; for GPT-5.x, only sends `reasoning` when explicitly set
- Added `verbosity` slash command option: `low` (concise), `medium` (default), `high` (detailed)
  - Sent as `text: {verbosity: ...}` in the Responses API payload; carried through follow-up messages
- Fixed `temperature`/`top_p` restrictions per OpenAI API rules:
  - `GPT5_NO_TEMP_MODELS` (`gpt-5`, `gpt-5-mini`, `gpt-5-nano`): always stripped — these models never support them
  - GPT-5.4/5.2 with `reasoning.effort` ≠ `none`: stripped to avoid API errors
- Added `REASONING_EFFORT_NONE = "none"` and `REASONING_EFFORT_XHIGH = "xhigh"` constants to `util.py`
- Added `GPT5_NO_TEMP_MODELS` frozenset to `util.py`

### Deep Research (`/openai research`)

- New `/openai research` command using `o3-deep-research` (default) and `o4-mini-deep-research` models
- Uses Responses API with `background=True` for long-running research tasks
- Polls every 15 seconds with 20-minute timeout
- Always includes `web_search` tool; optionally adds `file_search` (requires `OPENAI_VECTOR_STORE_IDS`) and `code_interpreter`
- Single-shot command (no conversation mode) — sends a green "researching" embed, then edits it to blue on completion
- Report is sent as a downloadable `research_report.md` file attachment to avoid Discord embed size limits
- Reuses `extract_tool_info()` and `append_sources_embed()` for inline citations
- Includes pricing embed with cost tracking
- `ResearchParameters` class in `util.py` with `to_dict(tools)` method

### Pricing Embeds & Cost Logging

All commands include a blue pricing embed (toggleable via `SHOW_COST_EMBEDS` env var, defaults to `true`):

- **Chat/Research** (token-based): `append_pricing_embed()` — format: `$0.0042 · 1,234 in (456 cached) / 567 out (89 thinking) · tools: web search ×2 ($0.02) · daily $0.15`
- **Image/TTS/STT/Video** (flat-rate): `append_flat_pricing_embed()` — format: `$0.0340 · high · 1024x1024 · 1 image(s) · daily $0.18`

**Token-based pricing (chat, research):**
- `MODEL_PRICING` in `util.py` maps each chat model to `(input_cost_per_million, output_cost_per_million)` tuple
- `calculate_cost()` computes dollar cost; unknown models fall back to `(2.50, 10.00)`; cached input tokens billed at 50% of input price
- `TOOL_CALL_PRICING` maps tool names to per-call costs: web_search $0.01, file_search $0.0025, code_interpreter/shell $0.03/container
- Token usage extracted from `response.usage.input_tokens` / `output_tokens`; cached from `usage.input_tokens_details.cached_tokens`; reasoning from `usage.output_tokens_details.reasoning_tokens`

**Image pricing:** `IMAGE_PRICING` table keyed by `(model, quality, size)` for all 27 combos (3 models × 3 qualities × 3 sizes); `IMAGE_PRICING_DEFAULTS` used when quality or size is "auto"

**TTS pricing:** `TTS_PRICING_PER_CHAR` — per-character rates: tts-1 $15/1M, tts-1-hd $30/1M, gpt-4o-mini-tts ~$20/1M (estimated)

**STT pricing:** `STT_PRICING_PER_MINUTE` — per-minute rates: whisper-1/gpt-4o-transcribe $0.006, gpt-4o-mini-transcribe $0.003. Duration estimated from file size via `estimate_audio_duration_seconds()` (WAV ~88 KB/s, compressed ~16 KB/s)

**Video pricing:** `VIDEO_PRICING_PER_SECOND` — sora-2 $0.10/s, sora-2-pro $0.20/s

**Persistent cost logging:**
- `_track_daily_cost()` — logs structured `COST |` lines for chat/research: `COST | command=chat | user=12345 | model=gpt-5.4 | input_tokens=... | output_tokens=... | cached_tokens=... | cost=$0.0042 | daily=$0.15`
- `_track_daily_cost_direct()` — logs structured `COST |` lines for image/TTS/STT/video: `COST | command=image | user=12345 | model=gpt-image-1.5 | cost=$0.0340 | daily=$0.18 | quality=auto | size=auto | n=1`
- Both methods accumulate per-user per-day costs in `self.daily_costs` (in-memory) and emit `logger.info()` for persistent log output

### File Search Citations & `max_num_results`

- `extract_tool_info()` now parses `file_citation` annotations (filename, file_id) alongside existing `url_citation` support
- `append_sources_embed()` renders file citations under a "**Files referenced:**" heading in the Sources embed
- Sources embed now triggers for any citation type (web or file), not just web_search
- `TOOL_FILE_SEARCH` includes `max_num_results: 5` to reduce token usage

### Server-Side Compaction

- `context_management=[{"type": "compaction", "compact_threshold": 200000}]` is sent with every Responses API call
- Automatically compresses context when conversations exceed the token threshold, preventing context-window overflow
- Applied in both the initial `/openai chat` command (via `to_dict()`) and follow-up conversation messages
- `CONTEXT_MANAGEMENT` constant defined in `util.py`

### Extended Prompt Cache Retention

- `prompt_cache_retention="24h"` is sent with every Responses API call
- Extends cached prompt prefix retention from the default 5-10 minutes to 24 hours
- Improves cache hit rates across conversations that share the same persona/instructions/tools
- `PROMPT_CACHE_RETENTION` constant defined in `util.py`

### File Input Support (`input_file`)

- Attachments are now routed by content type: images → `image_url`, everything else → `input_file`
- Supports PDFs, Word docs, spreadsheets, code files, and more via the Responses API `input_file` content block
- Works in both the initial `/openai chat` command and follow-up conversation messages

## Previous Changes (November 2025)

### Video Generation (`/openai video`)

Added support for OpenAI's Sora video generation:

- Models: `sora-2` (fast) and `sora-2-pro` (high quality)
- Sizes: 1280x720, 720x1280, 1792x1024, 1024x1792, 1920x1080 (Pro only), 1080x1920 (Pro only)
- Durations: 4, 8, 12, 16, or 20 seconds
- Async polling with 10-minute timeout

### Chat Completions → Responses API Migration

Migrated `/openai chat` from Chat Completions API to the new Responses API:

**Before (Chat Completions):**

- Stored full message history in `messages` array
- Sent entire conversation with each API call
- Manual message management

**After (Responses API):**

- Uses `previous_response_id` for conversation chaining
- API manages context automatically
- Simpler state management - just store response IDs
- Native `reasoning` parameter for o-series models

**Key changes:**

- `ChatCompletionParameters` → `ResponseParameters`
- `chat.completions.create()` → `responses.create()`
- `response.choices[0].message.content` → `response.output_text`
- Messages array → `previous_response_id` chaining

## Running Tests

```bash
# Windows PowerShell (with venv)
PYTHONPATH=src .venv/Scripts/python.exe -m unittest discover -s tests -v

# Unix/macOS (with venv)
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Environment Variables

| Variable             | Description                                              |
|----------------------|----------------------------------------------------------|
| `BOT_TOKEN`          | Discord bot token                                        |
| `GUILD_IDS`          | Comma‑separated Discord server IDs                       |
| `OPENAI_API_KEY`     | OpenAI API key                                           |
| `SHOW_COST_EMBEDS`   | Show cost/token embeds (`true`/`false`, default `true`)  |

## Models Supported

### Conversational Models (via `/openai chat`)

- GPT-5.4 (default), GPT-5.4 Pro
- GPT-5.3
- GPT-5.2, GPT-5.2 Pro
- GPT-5.1
- GPT-5, GPT-5 Pro, GPT-5 Mini, GPT-5 Nano
- GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano
- o4-mini, o3-pro, o3, o3-mini, o1-pro, o1 (reasoning models)
- GPT-4o, GPT-4o Mini
- GPT-4, GPT-4 Turbo
- GPT-3.5 Turbo

### Deep Research Models (via `/openai research`)

- `o3-deep-research` (default) — full deep research model
- `o4-mini-deep-research` — faster, lower-cost deep research

### Image Generation Models

- `gpt-image-1.5` (default)
- `gpt-image-1`
- `gpt-image-1-mini`

DALL-E 2 and DALL-E 3 have been removed (deprecated May 2026).

### Video Generation Models

- `sora-2` (fast)
- `sora-2-pro` (high quality, supports 1080p)

### TTS Models

- `gpt-4o-mini-tts` (supports all 13 voices including rich voices `ballad`, `verse`, `marin`, `cedar`)
- `tts-1` (9 standard voices: alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer)
- `tts-1-hd` (same 9 standard voices)

Default voice is `marin` (falls back to `coral` for models that don't support it).

### STT Models

- `gpt-4o-transcribe`
- `gpt-4o-mini-transcribe`
- `gpt-4o-transcribe-diarize` (uses `diarized_json` response format with speaker-labeled segments)
- `whisper-1`

Translation (into English) is only supported by `whisper-1`; the bot forces this model when the translation action is selected.
