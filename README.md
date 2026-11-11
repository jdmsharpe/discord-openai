<h1 align="center">Discord OpenAI Bot</h1>

<div align="center">

![Hits](https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2Fjdmsharpe%2Fdiscord-openai%2F&label=discord-openai&icon=github&color=%23198754&message=&style=flat&tz=UTC)
[![Version](https://img.shields.io/github/v/tag/jdmsharpe/discord-openai?sort=semver&label=version)](https://github.com/jdmsharpe/discord-openai/tags)
[![License](https://img.shields.io/github/license/jdmsharpe/discord-openai?label=license)](./LICENSE)
[![CI](https://github.com/jdmsharpe/discord-openai/actions/workflows/main.yml/badge.svg)](https://github.com/jdmsharpe/discord-openai/actions/workflows/main.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/jsgreen152/discord-openai-bot?logo=docker&logoColor=white)](https://hub.docker.com/r/jsgreen152/discord-openai-bot)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Codecov](https://codecov.io/gh/jdmsharpe/discord-openai/branch/main/graph/badge.svg)](https://app.codecov.io/gh/jdmsharpe/discord-openai)

</div>

## Overview

A Discord bot for the OpenAI API, built on Pycord 2.0. It provides chat, image generation, text-to-speech, speech-to-text and deep research through slash commands.

## Features

- **Chat:** Multi-turn conversations with GPT-6, GPT-5.x, GPT-4.1, o3 and GPT-4o Mini models. Messages you send in the channel continue the conversation.
- **Attachments:** Images, PDFs, documents, spreadsheets and code files.
- **Reasoning:** Reasoning models show a summary of their thinking in a spoiler.
- **Built-in tools:** `web_search`, `code_interpreter`, `file_search` and `shell`.
- **Remote MCP and connectors:** Trusted servers enabled through named presets, with optional tool allow-lists and approval policies. Tool calls that need approval show Approve / Deny buttons.
- **Citations:** Web and file search citations appear in a Sources embed.
- **Media generation:**
  - **Images:** GPT Image models with quality, size and background options.
  - **Text-to-speech:** `gpt-4o-mini-tts`, `tts-1` and `tts-1-hd`, with 13 voices.
  - **Speech-to-text:** Transcription or English translation of audio files, with optional speaker labels.
- **Deep research:** Research runs that search the web and return a report with citations.
- **Cost line:** Each reply ends with a line such as `$0.0120 · 3.4k in (2.1k cached) / 812 out (640 thinking) · 1 search · fast mode · $0.34 today`: request cost, input tokens (cached in parentheses), output tokens (thinking in parentheses), tool calls and your total for the day. Set `SHOW_COST_EMBEDS=false` to hide it.

## Commands

### `/openai chat`

Start a conversation with an OpenAI model.

- **`prompt` (required):** Your first message.
- **`persona`:** System prompt (default: "You are a helpful assistant.").
- **`model`:** GPT-6 Astra (default), GPT-6.1 Sol / Terra, GPT-6 Sol / Luna, GPT-5.6 Sol / Terra / Luna, GPT-5.5 through GPT-5 (including the Pro, Mini and Nano tiers), GPT-4.1 / 4.1 Mini, o3 / o3 Pro, GPT-4o Mini.
- **`attachment`:** An image, PDF, document, spreadsheet or code file.
- **`temperature` / `top_p`:** Sent only when the model and reasoning effort accept them; otherwise dropped.
- **`reasoning_effort`:** `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max`. Each model supports a subset, and an unsupported level is refused before the request is sent.
- **`reasoning_mode`:** `pro` on GPT-6 Astra / Sol / Luna, GPT-6.1 Sol and GPT-5.6. Same token rates, but roughly 4–6x the tokens per turn.
- **`service_tier`:** `fast` for faster processing at OpenAI's Fast-mode rates (2x on GPT-6, GPT-6.1 and GPT-5.6). Not available on the Pro tiers or GPT-5.4 Nano.
- **`verbosity`:** `low`, `medium` (default) or `high`.
- **`web_search` / `code_interpreter` / `file_search` / `shell`:** Enable built-in tools (default: off). `file_search` needs `OPENAI_VECTOR_STORE_IDS`; `shell` works on GPT-5 and GPT-6 models.
- **`mcp`:** Comma-separated MCP preset names (see [MCP Setup](#mcp-setup)).

### `/openai-media image`

Generate an image from a prompt, or edit an attached image.

- **`model`:** `gpt-image-2.6-sunburst` (default), `gpt-image-2.6-flare`, `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`, `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1-mini`.
- **`quality`:** `auto` (default), `low`, `medium` or `high`; `xhigh` and `max` on GPT Image 2.5 and 2.6 only.
- **`size`:** `auto` (default), `1024x1024`, `1024x1536` (portrait) or `1536x1024` (landscape).
- **`background`:** `auto` (default), `opaque` or `transparent` (alpha PNG).
- **`attachment`:** An image to edit (PNG, JPEG, GIF, WebP).
- Cost is billed from the token usage each response reports.

### `/openai-tools research`

Run a deep research task that searches the web and returns a report with citations.

- **`model`:** `gpt-6-astra` (default), `gpt-6.1-sol`, `gpt-6-sol`, `gpt-5.6-sol`, `gpt-5.5` or `gpt-5.5-pro`.
- **`file_search` / `code_interpreter`:** Also search your vector stores, or let the model run code (default: off).

### `/openai-tools tts`

Convert text to speech (up to 4096 characters).

- **`model`:** `gpt-4o-mini-tts` (default), `tts-1` or `tts-1-hd`.
- **`voice`:** 13 voices (default: Marin); Marin, Cedar, Ballad and Verse need `gpt-4o-mini-tts`.
- **`instructions`:** Delivery instructions.
- **`response_format` / `speed`:** MP3 (default), WAV, Opus, AAC, FLAC or PCM, and playback speed (default 1.0).

### `/openai-tools stt`

Transcribe or translate an audio file (up to 25 MB).

- **`model`:** `gpt-transcribe` (default), `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `whisper-1`, or a diarization model for speaker-labeled transcripts.
- **`action`:** Transcription (default) or translation to English.

### `/openai check_permissions`

Check if the bot has the necessary permissions in the current channel.

## Setup & Installation

### Prerequisites

- Python 3.11+
- Discord Bot Token
- OpenAI API Key

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/jdmsharpe/discord-openai.git
   cd discord-openai
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the package and its runtime dependencies:

   ```bash
   python -m pip install .
   ```

4. Copy the environment example file:

   ```bash
   cp .env.example .env
   ```

### Contributor Setup

Install development tooling for tests, linting, and type checking:

```bash
python -m pip install -e ".[dev]"
```

### Configuration (`.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | **Yes** | Your Discord bot token |
| `GUILD_IDS` | **Yes** | Comma-separated Discord server IDs |
| `OPENAI_API_KEY` | **Yes** | Your OpenAI API key |
| `OPENAI_VECTOR_STORE_IDS` | No | Comma-separated vector store IDs for `/openai chat` file search |
| `SHOW_COST_EMBEDS` | No | Show cost/token usage embeds (Default: `true`) |
| `OPENAI_MCP_PRESETS_JSON` | No | Inline JSON object of named MCP presets |
| `OPENAI_MCP_PRESETS_PATH` | No | Path to a JSON file containing named MCP presets |
| `OPENAI_PRICING_PATH` | No | Path to a pricing YAML that overrides the bundled `src/discord_openai/config/pricing.yaml` |
| `LOG_FORMAT` | No | `text` (default) for human-readable logs, or `json` for structured JSON-lines output with per-request IDs |
| `SAFETY_IDENTIFIER_SECRET` | No | Key for the per-user identifier sent to OpenAI for abuse monitoring (Default: derived from `BOT_TOKEN`) |

#### User Identifier

Chat, research and image requests carry a per-user identifier (`safety_identifier` on the Responses API, `user` on the Images API) so OpenAI can attribute a policy violation to one Discord user instead of the whole bot.

- The identifier is an HMAC-SHA256 of the Discord user ID, keyed with `SAFETY_IDENTIFIER_SECRET` or, when that is unset, a key derived from `BOT_TOKEN`. OpenAI never receives the user ID or the key, and the bot refuses to start when `SAFETY_IDENTIFIER_SECRET` equals `OPENAI_API_KEY`.
- Changing the key (or the bot token, when no secret is set) gives every user a new identifier. To keep identifiers stable across token changes, set the secret to a long random string, for example `python -c "import secrets; print(secrets.token_hex(32))"`.
- discord-claude, discord-grok, discord-openai and discord-openrouter compute it the same way, so a user gets the same identifier from each bot that shares the key.
- Text-to-speech and speech-to-text requests carry none, because those endpoints don't accept one.

#### MCP Setup

Configure named presets in `OPENAI_MCP_PRESETS_JSON` or `OPENAI_MCP_PRESETS_PATH`. Example:

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

Connector presets (`kind: "connector"`) don't work on GPT-6 Astra / Sol / Luna or GPT-6.1 Sol, and the bot refuses them there before sending the request. Use a `remote_mcp` preset or a GPT-5.6 or earlier model instead.

Define presets only for servers you trust: the model can send conversation content to any server it calls.

### Running the Bot

**Locally:**

```bash
python src/bot.py
```

*(Note: `src/bot.py` is a thin launcher that delegates to `discord_openai.bot.main`)*

**With Docker:**

```bash
docker compose up -d --build
```

**Using as a Cog:**
To compose this repo into a larger bot, import the namespaced package:

```python
from discord_openai import OpenAICog

bot.add_cog(OpenAICog(bot=bot))
```

## Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application and add a bot in the "Bot" section.
3. Enable **Server Members Intent** and **Message Content Intent** under Privileged Gateway Intents.
4. Copy the bot token and add it to your `.env` file.
5. Go to OAuth2 > URL Generator.
6. Select scopes: `bot`, `applications.commands`.
7. Select permissions: `Send Messages`, `Read Message History`, `Use Slash Commands`, `Embed Links`, `Attach Files`.
8. Use the generated URL to invite the bot to your server.

## Usage

1. Run `/openai chat` to start a conversation.
2. Send messages in the same channel to continue it.
3. Use the controls under each reply:
   - 🔄 Regenerate the last response
   - ⏯️ Pause or resume the conversation
   - ⏹️ End the conversation
   - **Tools** menu: turn tools on or off mid-conversation

### Demo

<div align="center">

![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/588d33fa-084d-46ae-bc19-96a299813c4c)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/99e81595-b30f-40b5-b8ac-2a9c8cc49948)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/e69242d0-acdc-42af-be66-794c95d81af7)
<br/>
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/47a96010-02d8-4dfc-b317-4009b926da1e)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/3907ac6b-4bb6-4bfa-9b97-68912ceed517)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/d5e0758e-f9d5-4ca6-bdb4-bea33c5065a3)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/c5992fac-3372-4c99-81f1-93c7fbda1d0e)

</div>

## Development

### Testing

Tests use `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`). All tests are mocked (no real API calls).

```bash
# Install developer tooling if you have not already
python -m pip install -e ".[dev]"

# Run tests locally
python -m pytest -q

# Run tests in Docker
docker build --build-arg PYTHON_VERSION=3.11 -f Dockerfile.test -t discord-openai-test:3.11 .
docker run --rm discord-openai-test:3.11 python -m pytest -q

# Run linting and type checks in Docker
docker run --rm discord-openai-test:3.11 sh -lc 'ruff check src tests && ruff format --check src tests && pyright'
```

### Linting & Type Checking

```bash
ruff check src tests
ruff format --check src tests
pyright
```

*Run `git config core.hooksPath .githooks` after cloning to enable the pre-commit hook.*

## License

MIT License - see [LICENSE](LICENSE) for details.
