# Discord OpenAI Bot

![Badge](https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2Fjdmsharpe%2Fdiscord-openai%2F&label=discord-openai&icon=github&color=%23198754&message=&style=flat&tz=UTC)
[![Workflow](https://github.com/jdmsharpe/discord-openai-bot/actions/workflows/main.yml/badge.svg)](https://hub.docker.com/r/jsgreen152/discord-openai-bot)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)

## Overview

This is a Discord bot built on [Pycord 2.0](https://github.com/Pycord-Development/pycord) that integrates the OpenAI API. It brings together conversational AI, image generation, text-to-speech, and speech-to-text capabilities all accessible via modern slash commands. Whether you’re looking to chat with a state-of-the-art model, generate creative visuals, or convert text and speech, this bot offers an interactive interface that enhances your Discord server experience.

## Features

- **Conversational AI:** Engage in interactive, ongoing conversations with various OpenAI models using `/openai chat`. The bot maintains conversation history as you write further messages in the same channel, and accepts image, PDF, document, spreadsheet, and code file attachments.
- **Remote MCP and connectors:** `/openai chat` can enable trusted remote MCP servers and OpenAI connectors through named MCP presets loaded from config, with optional tool allow-lists and approval policies.
- **Image Generation:** Create images from text prompts with `/openai image` using GPT Image models, with controls for quality and aspect ratio.
- **Text-to-Speech:** Convert text into lifelike audio using `/openai tts`, with customizable voice, audio format, and speed.
- **Speech-to-Text:** Transform audio attachments into text with `/openai stt` and pick Whisper or GPT-4o transcription models, plus transcription or translation into English.
- **Deep Research:** Run autonomous research tasks with `/openai research` using deep research models that search, read, and synthesize detailed reports with inline citations.
- **Video Generation:** Create videos from text prompts with `/openai video` using OpenAI's Sora models, with controls for resolution and duration.
- **Interactive UI:** Incorporates button-based controls and real-time feedback.

## Commands

All commands are grouped under the `/openai` slash command group.

### `/openai chat`

- **Usage:** `/openai chat prompt:<text>`
- **What it does:** Opens a thread with the selected GPT model and keeps the whole conversation in context for follow-up replies in the same channel.
- **Defaults:** Persona is `You are a helpful assistant.` and the default model is `gpt-5.4`.
- **Model choices:**
  - GPT-5.4 (standard/pro)
  - GPT-5.3
  - GPT-5.2 (standard/pro)
  - GPT-5.1
  - GPT-5 (standard/pro/mini/nano)
  - GPT-4.1 (standard/mini/nano)
  - `o4-mini`, `o3-pro`, `o3`, `o3-mini`, `o1-pro`, `o1`
  - GPT-4o (standard/mini)
  - GPT-4 / GPT-4 Turbo
  - GPT-3.5 Turbo
- **Attachments:** Attach an image, PDF, document, spreadsheet, or code file. Images are sent as visual input; all other files are sent via the Responses API `input_file` type.
- **Reasoning summary:** When using reasoning models (o-series, GPT-5.x with reasoning effort), the model's thinking process is displayed in a spoilered "Thinking" embed before the response.
- **Advanced tuning:** Frequency penalty, presence penalty, temperature (or nucleus sampling via `top_p`), and `seed` are all optional. Reasoning models ignore custom temperature/`top_p` and fall back to their defaults automatically.
- **Built-in tools:** Optional tool calling supports `web_search`, `code_interpreter`, `file_search` (requires `OPENAI_VECTOR_STORE_IDS`; surfaces file citations in a Sources embed), and `shell` (GPT-5 series models only).
- **MCP presets:** The optional `mcp` parameter accepts a comma-separated list of preset names. Presets can target either a remote MCP server (`kind: "remote_mcp"`) or an OpenAI connector (`kind: "connector"`). MCP selections persist for the life of the conversation and are kept separate from the built-in tool dropdown.
- **Approval loop:** OpenAI MCP and connector tool calls default to requiring approval. When the model requests access, the bot swaps the normal controls for `Approve MCP`, `Deny MCP`, and `Stop`, blocks typed follow-ups until a decision is made, and then edits the same Discord message in place with the final response.

### MCP Setup For `/openai chat`

Configure trusted MCP presets in `OPENAI_MCP_PRESETS_JSON`, `OPENAI_MCP_PRESETS_PATH`, or both.

- `OPENAI_MCP_PRESETS_JSON` should contain a single JSON object inline in `.env`.
- `OPENAI_MCP_PRESETS_PATH` should point to a JSON file with the same top-level object shape.
- When both are set, the sources are merged additively and duplicate preset names across the two sources are rejected.

Each preset is keyed by name and supports this schema:

```json
{
  "github": {
    "kind": "remote_mcp",
    "server_label": "GitHub",
    "server_url": "https://api.githubcopilot.com/mcp/",
    "authorization_env_var": "GITHUB_MCP_TOKEN",
    "allowed_tools": ["search_issues"],
    "approval": "selective",
    "never_tool_names": ["search_issues"]
  },
  "gmail": {
    "kind": "connector",
    "server_label": "Gmail",
    "connector_id": "connector_gmail",
    "authorization_env_var": "GMAIL_OAUTH_TOKEN",
    "approval": "always"
  }
}
```

- `kind: "remote_mcp"` requires `server_url`, and the URL must be HTTPS.
- `kind: "connector"` requires `connector_id`.
- `approval` supports `always` (default), `never`, or `selective`.
- `never_tool_names` is only valid when `approval` is `selective`.
- `authorization_env_var` is optional and names another env var you define separately, such as `GITHUB_MCP_TOKEN`. When set, it must resolve at runtime or the preset is marked unavailable.
- Presets are re-resolved on every Responses call so connector/OAuth tokens are always re-injected and never stored in conversation state.
- Use trusted servers only, prefer least-privilege `allowed_tools`, and keep approval enabled for anything that can read sensitive data or take action.

### `/openai image`

- **Usage:** `/openai image prompt:<text>`
- **What it does:** Creates images using GPT Image models (`gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`).
- **Defaults:** Uses `gpt-image-1.5` with `auto` quality and `auto` size (model picks the best options based on your prompt).
- **Options:** Quality presets (low, medium, high, auto) and sizes (auto, 1024x1024, 1024x1536 portrait, 1536x1024 landscape).

### `/openai tts`

- **Usage:** `/openai tts input:<text>`
- **What it does:** Generates audio with OpenAI's TTS stack and returns the file as an attachment.
- **Models & voices:** Pick between `gpt-4o-mini-tts`, `tts-1`, and `tts-1-hd`. 13 voices are available: alloy, ash, ballad, cedar, coral, echo, fable, marin, nova, onyx, sage, shimmer, verse. Voices `ballad`, `verse`, `marin`, and `cedar` are exclusive to GPT-4o Mini TTS; the remaining 9 work across all models. Default voice is `marin`. Instructions are only honoured by GPT-4o based TTS models.
- **Format & speed:** Select MP3/WAV/Opus/AAC/FLAC/PCM output and tweak playback speed (default `1.0`).

### `/openai stt`

- **Usage:** `/openai stt attachment:<audio>`
- **What it does:** Transcribes or translates uploaded audio that is <=25 MB (mp3, mp4, mpeg, mpga, m4a, wav, webm).
- **Model choices:** `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe-diarize`, or `whisper-1`.
- **Actions:** Switch between verbatim `transcription` (default) or English `translation` (uses `whisper-1` regardless of model selection, as translation is only supported by Whisper).
- **Diarization:** The `gpt-4o-transcribe-diarize` model produces speaker-labeled transcripts with speaker names and segment boundaries.
- **Output:** Results are displayed in an embed, and long responses are automatically truncated to fit Discord limits.

### `/openai research`

- **Usage:** `/openai research prompt:<text>`
- **What it does:** Runs a deep research task that autonomously searches the web, reads pages, and synthesizes a detailed report with inline citations. Research can take several minutes.
- **Defaults:** Uses `o3-deep-research` model with web search enabled.
- **Model choices:**
  - `o3-deep-research` — Full deep research model
  - `o4-mini-deep-research` — Faster, lower-cost deep research
- **Tools:** Web search is always enabled. Optionally enable `file_search` (requires `OPENAI_VECTOR_STORE_IDS`) to search your vector stores, or `code_interpreter` to allow the model to write and run code for analysis.
- **Output:** A detailed report with numbered source citations, displayed across chunked embeds. Includes cost/token tracking.

### `/openai video`

- **Usage:** `/openai video prompt:<text>`
- **What it does:** Generates videos from text prompts using OpenAI's Sora models. Video generation is asynchronous and can take several minutes.
- **Defaults:** Uses `sora-2` model, 1280x720 resolution, and 8 seconds duration.
- **Model choices:**
  - `sora-2` (Fast) - Ideal for quick iteration and experimentation
  - `sora-2-pro` (High Quality) - Best for production-quality output
- **Size options:** Landscape (1280x720), Portrait (720x1280), Wide Landscape (1792x1024), Tall Portrait (1024x1792), 1080p Landscape (1920x1080, Pro only), or 1080p Portrait (1080x1920, Pro only).
- **Duration:** 4, 8, 12, 16, or 20 seconds.
- **Prompting tips:** For best results, describe shot type, subject, action, setting, and lighting (e.g., "Wide shot of a child flying a red kite in a grassy park, golden hour sunlight, camera slowly pans upward").
- **Restrictions:** Content must be suitable for all audiences. Copyrighted characters, copyrighted music, and real people (including public figures) cannot be generated.

## UI

<div align="center">

![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/588d33fa-084d-46ae-bc19-96a299813c4c)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/99e81595-b30f-40b5-b8ac-2a9c8cc49948)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/e69242d0-acdc-42af-be66-794c95d81af7)

</div>

## Demo

<div align="center">

![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/47a96010-02d8-4dfc-b317-4009b926da1e)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/3907ac6b-4bb6-4bfa-9b97-68912ceed517)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/d5e0758e-f9d5-4ca6-bdb4-bea33c5065a3)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/c5992fac-3372-4c99-81f1-93c7fbda1d0e)

</div>

## Setup & Installation

### Prerequisites

- A Discord account and a server where you can add the bot.
- An OpenAI API key (get one at [OpenAI API Keys](https://platform.openai.com/api-keys)).

### Creating and Inviting Your Bot

1. Follow the [Discord Bot Creation Guide](https://docs.pycord.dev/en/master/discord.html#:~:text=Make%20sure%20you're%20logged%20on%20to%20the%20Discord%20website.&text=Click%20on%20the%20%E2%80%9CNew%20Application,and%20clicking%20%E2%80%9CAdd%20Bot%E2%80%9D) to create your application and bot.
2. Invite the bot to your server using the correct permissions.

#### Required Permissions

- **Bot Permissions Integer:** `397821737984`
- **Intents:** Ensure the bot has access to read messages and message history.

<div align="center">

![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/87e33ec0-e496-4835-9526-4eaa1e980f7f)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/b0e2d96a-769b-471c-91ad-ef2f2dc54f13)

</div>

### Build and Run with Docker (Recommended)

#### Build and run the image locally

- Build the image with `docker build -t python-bot .` in the root directory
- Run the bot with `docker run -e BOT_TOKEN=<YOUR BOT TOKEN> -e GUILD_IDS=<YOUR GUILD IDS IN LIST FORMAT> -e OPENAI_API_KEY=<YOUR OPENAI API KEY> -e OPENAI_VECTOR_STORE_IDS=<COMMA_SEPARATED_VECTOR_STORE_IDS> -e SHOW_COST_EMBEDS=true python-bot` in the root directory

### Running from source

- (Recommended) Create a virtual environment
- Install the dependencies with `pip install -r requirements.txt`
- Copy `.env.example` to `.env` and fill in your values. Optional settings are included as commented examples in the template:
  - `BOT_TOKEN`: Your Discord bot token
  - `GUILD_IDS`: Comma-separated list of Discord server IDs to deploy the bot on
  - `OPENAI_API_KEY`: Your OpenAI API key (available at [OpenAI API Platform](https://platform.openai.com/api-keys))
  - `OPENAI_VECTOR_STORE_IDS`: Comma-separated vector store IDs used by `/openai chat` file search tool (Optional)
  - `OPENAI_MCP_PRESETS_JSON`: Inline JSON object of named MCP presets for `/openai chat mcp` (Optional)
  - `OPENAI_MCP_PRESETS_PATH`: Path to a JSON file containing named MCP presets for `/openai chat mcp`; additive with `OPENAI_MCP_PRESETS_JSON`, and preset names must be unique across both sources (Optional)
  - `SHOW_COST_EMBEDS`: Show cost/token usage embeds on chat responses — `true` by default; `true`, `1`, or `yes` enable it (Optional)
- `BOT_TOKEN` and `OPENAI_API_KEY` are required; the bot exits at startup with a clear error if either is missing or blank.
- Run the bot with `python src/bot.py`
  - `src/bot.py` remains a thin repo-local launcher that delegates to `discord_openai.bot.main`

### Using as a Cog

To compose this repo into a larger bot, import the namespaced package:

```python
from discord_openai import OpenAICog

bot.add_cog(OpenAICog(bot=bot))
```

Only `src/bot.py` remains at the repository root as a thin launcher; package code should be imported from `discord_openai`.

## Development

### Testing

Tests use pytest with pytest-asyncio (`asyncio_mode = "auto"`). All tests are mocked — no real API calls. CI runs the suite on Python 3.10, 3.11, 3.12, and 3.13.
The suite is organized around the refactored package layout, with focused files such as `tests/test_openai_cog.py`, `tests/test_openai_embeds.py`, `tests/test_openai_responses.py`, `tests/test_openai_tooling.py`, `tests/test_openai_mcp_config.py`, `tests/test_openai_chat.py`, `tests/test_openai_state.py`, `tests/test_config_auth.py`, and `tests/test_lazy_imports.py`.
`tests/test_package_import.py` is the package import smoke test, and `tests/test_lazy_imports.py` covers the lazy package exports used by `discord_openai` and `discord_openai.cogs.openai`.
The lazy package exports are paired with type-only imports so `pyright src/` can validate public namespaced imports without eagerly importing the full cog modules at runtime.
Import from `discord_openai` directly; legacy top-level shim modules are no longer part of the supported workflow.

```bash
# Run tests
.venv/Scripts/python.exe -m pytest -q    # Windows
.venv/bin/python -m pytest -q            # Unix

# Run tests in Docker
docker build --build-arg PYTHON_VERSION=3.13 -f Dockerfile.test -t discord-openai-test . && docker run --rm discord-openai-test

# Smoke-test another supported version
docker build --build-arg PYTHON_VERSION=3.10 -f Dockerfile.test -t discord-openai-test:3.10 . && docker run --rm discord-openai-test:3.10
```

### Linting & Type Checking

```bash
ruff check src/ tests/
ruff format src/ tests/
pyright src/
```

After cloning, run `git config core.hooksPath .githooks` to enable the pre-commit hook.
The pre-commit hook prefers a repo-local `.venv` Ruff binary when available and falls back to `PATH`.
