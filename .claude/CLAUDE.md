# Discord OpenAI Bot - Claude Code Context

## Repository Overview

This is a Discord bot built on Pycord 2.0 that integrates multiple OpenAI APIs to provide conversational AI, image generation, text-to-speech, speech-to-text, and video generation capabilities via Discord slash commands.

## Project Structure

```text
discord-chatgpt/
├── src/
│   ├── bot.py              # Main bot entry point
│   ├── openai_api.py       # OpenAI API cog with all slash commands
│   ├── button_view.py      # Discord UI button handlers (regenerate, pause, stop)
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

- **ResponseParameters**: Parameters for the Responses API (used by `/openai converse`)
  - Supports `previous_response_id` for conversation chaining
  - Handles reasoning models (o-series) with `reasoning` parameter
  - Discord-specific fields for conversation management

- **ImageGenerationParameters**: Parameters for image generation
  - Supports GPT-4 Image, DALL-E 3, DALL-E 2
  - Handles model-specific quality defaults

- **VideoGenerationParameters**: Parameters for Sora video generation
  - Supports `sora-2` and `sora-2-pro` models
  - Size options and duration (4/8/12 seconds)

- **TextToSpeechParameters**: Parameters for TTS
  - Voice selection with model-specific validation
  - Rich voice instructions for GPT-4o models

- **ChatCompletionParameters**: Legacy parameters (kept for reference)

### Commands (`src/openai_api.py`)

All commands are grouped under the `/openai` slash command group using Pycord's `SlashCommandGroup`.

| Command | Description | API |
|---------|-------------|-----|
| `/openai converse` | Multi-turn conversations | Responses API |
| `/openai image` | Image generation | Images API |
| `/openai video` | Video generation | Videos API (Sora) |
| `/openai tts` | Text to audio | Audio Speech API |
| `/openai stt` | Audio to text | Audio Transcriptions API |
| `/openai check_permissions` | Check bot permissions | N/A |

### Conversation Management

- Conversations are tracked per user per channel
- `response_id_history` enables regeneration by reverting to previous response IDs
- Pause/resume functionality via button controls
- Automatic conversation state cleanup on stop

## Recent Changes (November 2025)

### Video Generation (`/openai video`)

Added support for OpenAI's Sora video generation:

- Models: `sora-2` (fast) and `sora-2-pro` (high quality)
- Sizes: 1280x720, 720x1280, 1792x1024, 1024x1792
- Durations: 4, 8, or 12 seconds
- Async polling with 10-minute timeout

### Chat Completions → Responses API Migration

Migrated `/openai converse` from Chat Completions API to the new Responses API:

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
cd discord-chatgpt
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Discord bot token |
| `GUILD_IDS` | Comma-separated Discord server IDs |
| `OPENAI_API_KEY` | OpenAI API key |

## Models Supported

### Conversational Models (via `/openai converse`)

- GPT-5.1, GPT-5.1 Mini
- GPT-5, GPT-5 Mini, GPT-5 Nano
- GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano
- o4-mini, o3, o3-mini, o1, o1-mini (reasoning models)
- GPT-4o, GPT-4o Mini
- GPT-4, GPT-4 Turbo
- GPT-3.5 Turbo

### Image Generation Models

- `gpt-image-1` (GPT-4 Image)
- `gpt-image-1-mini`
- `dall-e-3`
- `dall-e-2`

### Video Generation Models

- `sora-2` (fast)
- `sora-2-pro` (high quality)

### TTS Models

- `gpt-4o-mini-tts` (supports rich voices)
- `tts-1`
- `tts-1-hd`

### STT Models

- `gpt-4o-transcribe`
- `gpt-4o-mini-transcribe`
- `gpt-4o-transcribe-diarize`
- `whisper-1`
