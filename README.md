# Discord OpenAI Bot

![Hits](https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2Fjdmsharpe%2Fdiscord-openai%2F&label=discord-openai&icon=github&color=%23198754&message=&style=flat&tz=UTC)
[![Workflow](https://github.com/jdmsharpe/discord-openai-bot/actions/workflows/main.yml/badge.svg)](https://hub.docker.com/r/jsgreen152/discord-openai-bot)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)

## Overview
This is a Discord bot built on Pycord 2.0 that integrates the OpenAI API. It brings together conversational AI, image generation, text-to-speech, speech-to-text capabilities, autonomous research, and video generation—all accessible via modern slash commands grouped neatly under the `/openai` namespace.

## Features
- **Conversational AI:** Engage in interactive, multi-turn conversations with a wide variety of OpenAI models (GPT-5 series, o-series, GPT-4o, etc.). Maintains full context for follow-up replies in the same channel.
- **Multimodal Input:** Attach images, PDFs, documents, spreadsheets, and code files. 
- **Reasoning Display:** Model thinking processes (for o-series and reasoning-effort models) are displayed in spoilered "Thinking" embeds.
- **Built-in Tools:** Supports `web_search`, `code_interpreter`, `file_search` (with citation embeds), and `shell` (GPT-5 series only).
- **Remote MCP & Connectors:** Enable trusted remote MCP servers and OpenAI connectors via named presets with optional tool allow-lists and approval policies. Features a seamless Discord UI approval loop for actions.
- **Media Generation:**
  - **Images:** Create images using GPT Image models with quality and aspect ratio controls.
  - **Video:** Generate videos using Sora models with customizable duration and resolution.
  - **Text-to-Speech:** Convert text into lifelike audio using `gpt-4o-mini-tts` or `tts-1` models with 13 distinct voices.
  - **Speech-to-Text:** Transform audio attachments into verbatim transcriptions or English translations, complete with optional speaker diarization.
- **Deep Research:** Run autonomous agents that search the web, read pages, and synthesize detailed reports with inline citations.
- **Interactive UI:** Incorporates button-based controls, real-time feedback, and dynamic context menus.

## Commands

### `/openai chat`
Start an interactive thread with an OpenAI model.
* **Models:** GPT-5 series, GPT-4 series, o-series (o1, o3, o4-mini, etc.), GPT-3.5 Turbo.
* **Tuning Options:** Adjust frequency penalty, presence penalty, temperature, `top_p`, and `seed`.
* **Tools:** `web_search`, `code_interpreter`, `file_search` (requires `OPENAI_VECTOR_STORE_IDS`), `shell`.
* **MCP Integration:** Provide a comma-separated list of preset names via the `mcp` parameter to enable remote servers or connectors.

### `/openai image`
Create images using GPT Image models (`gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`).
* Features quality presets (low, medium, high, auto) and multiple sizes (portrait, landscape, square).

### `/openai video`
Generate videos from text prompts using OpenAI's Sora models (`sora-2`, `sora-2-pro`).
* Features customizable size options (up to 1080p for Pro) and duration (4–20 seconds).

### `/openai research`
Run a deep research task using `o3-deep-research` or `o4-mini-deep-research`.
* Autonomously searches the web and synthesizes cited reports. Optionally enable `file_search` or `code_interpreter` to enhance analysis.

### `/openai tts`
Generate lifelike audio from text using OpenAI's TTS stack.
* Select from 13 voices, multiple output formats (MP3, WAV, Opus, AAC, FLAC, PCM), and adjust playback speed.

### `/openai stt`
Transcribe or translate uploaded audio (up to 25 MB).
* Supports `gpt-4o-transcribe`, `whisper-1`, and diarization models for speaker-labeled transcripts.

### `/openai check_permissions`
Check if the bot has the necessary permissions in the current channel.

## Setup & Installation

### Prerequisites
- Python 3.10+
- Discord Bot Token
- OpenAI API Key

### Installation
1. Clone the repository and navigate to the project directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment example file:
   ```bash
   cp .env.example .env
   ```

### Configuration (`.env`)
| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | **Yes** | Your Discord bot token |
| `GUILD_IDS` | **Yes** | Comma-separated Discord server IDs |
| `OPENAI_API_KEY` | **Yes** | Your OpenAI API key |
| `OPENAI_VECTOR_STORE_IDS`| No | Comma-separated vector store IDs for `/openai chat` file search |
| `SHOW_COST_EMBEDS` | No | Show cost/token usage embeds (Default: `true`) |
| `OPENAI_MCP_PRESETS_JSON`| No | Inline JSON object of named MCP presets |
| `OPENAI_MCP_PRESETS_PATH`| No | Path to a JSON file containing named MCP presets |

#### MCP Setup
Configure trusted MCP presets via JSON. Example schema:
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

### Running the Bot
**Locally:**
```bash
python src/bot.py
```
*(Note: `src/bot.py` is a thin launcher that delegates to `discord_openai.bot.main`)*

**With Docker:**
```bash
docker build -t discord-openai-bot .
docker run -e BOT_TOKEN=<YOUR_TOKEN> -e GUILD_IDS=<YOUR_IDS> -e OPENAI_API_KEY=<YOUR_KEY> discord-openai-bot
```

**Using as a Cog:**
To compose this repo into a larger bot:
```python
from discord_openai import OpenAICog

bot.add_cog(OpenAICog(bot=bot))
```

## Discord Bot Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application and add a bot.
3. Enable **Server Members Intent** and **Message Content Intent** under Privileged Gateway Intents.
4. Set the **Bot Permissions Integer** to `397821737984`.

<div align="center">

![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/87e33ec0-e496-4835-9526-4eaa1e980f7f)
![image](https://github.com/jdmsharpe/discord-openai-bot/assets/55511821/b0e2d96a-769b-471c-91ad-ef2f2dc54f13)

</div>

5. Generate your OAuth2 URL using the scopes `bot` and `applications.commands`.
6. Use the generated URL to invite the bot to your server.

## Usage & Demo
Start a chat via `/openai chat`, write follow-up messages directly in the channel, and utilize interactive UI elements for approvals, regeneration, and tools.

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
# Run tests locally
.venv/Scripts/python.exe -m pytest -q    # Windows
.venv/bin/python -m pytest -q            # Unix

# Run tests in Docker
docker build --build-arg PYTHON_VERSION=3.13 -f Dockerfile.test -t discord-openai-test . 
docker run --rm discord-openai-test
```

### Linting & Type Checking
```bash
ruff check src/ tests/
ruff format src/ tests/
pyright src/
```
*Run `git config core.hooksPath .githooks` after cloning to enable the pre-commit hook.*
