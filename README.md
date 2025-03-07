# Discord OpenAI Bot

<div align="center">

[![HitCount](https://hits.dwyl.com/jdmsharpe/discord-openai-bot.svg?style=flat-square&show=unique)](http://hits.dwyl.com/jdmsharpe/discord-openai-bot)
<a href="https://hub.docker.com/r/jsgreen152/discord-openai-bot" target="_blank" rel="noopener noreferrer">![Workflow](https://github.com/jdmsharpe/discord-openai-bot/actions/workflows/main.yml/badge.svg)</a>
  
</div>

## Overview
This is a Discord bot built on [Pycord 2.0](https://github.com/Pycord-Development/pycord) that integrates the OpenAI API. It brings together conversational AI, image generation, text-to-speech, and speech-to-text capabilities all accessible via modern slash commands. Whether you’re looking to chat with a state-of-the-art model, generate creative visuals, or convert text and speech, this bot offers an interactive interface that enhances your Discord server experience.

## Features
- **Conversational AI:** Engage in interactive, ongoing conversations with various OpenAI models using `/converse`. The bot maintains conversation history as you write further messages in the same channel, and even accepts image attachments.
- **Image Generation:** Create images from text prompts with `/generate_image` using either DALL-E 2 or DALL-E 3, including options for image quality, size, and style.
- **Text-to-Speech:** Convert text into lifelike audio using `/text_to_speech`, with customizable voice, audio format, and speed.
- **Speech-to-Text:** Transform audio attachments into text with `/speech_to_text` – choose between simple transcription or translation into English.
- **Interactive UI:** Incorporates button-based controls and real-time feedback.

## Commands

### `/converse`
- **Usage:** `/converse <prompt>`
- **Description:** Start a conversation with a model. The bot tracks conversation history and context, allowing for follow-up messages in the same channel.
- **Advanced Options:**
  - **Persona:** Define the model’s role (default: “You are a helpful assistant.”)
  - **Model Selection:** Choose from multiple GPT models (e.g., GPT-3.5 Turbo, GPT-4, etc.)
  - **Customization:** Adjust parameters like frequency penalty, presence penalty, temperature, top_p, and more.
- **Notes:** You can include image attachments to enrich the conversation (note: this may be model-specific, as not all support image uploads).

### `/generate_image`
- **Usage:** `/generate_image <prompt>`
- **Description:** Generate image(s) from a text prompt using OpenAI’s DALL-E models.
- **Options:**
  - **Model:** Select between DALL-E 2 and DALL-E 3.
  - **Count:** Specify the number of images (with model-specific limits).
  - **Quality, Size, and Style:** Customize image output details (note: some options are model-specific).

### `/text_to_speech`
- **Usage:** `/text_to_speech <input>`
- **Description:** Convert text into natural-sounding audio.
- **Options:**
  - **Model & Voice:** Select from available TTS models and voices.
  - **Response Format & Speed:** Choose the audio file format and adjust playback speed.

### `/speech_to_text`
- **Usage:** `/speech_to_text <attachment>`
- **Description:** Convert an audio file into text.
- **Options:**
  - **Model:** Currently supports `whisper-1`.
  - **Action:** Choose between transcription or translation (into English).
- **Notes:** Supports various audio file types (e.g., mp3, mp4, wav, etc.) up to 25 MB.

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
+ Build the image with `docker build -t python-bot .` in the root directory
+ Run the bot with `docker run -e BOT_TOKEN=<YOUR BOT TOKEN> -e GUILD_IDS=<YOUR GUILD IDS IN LIST FORMAT> -e OPENAI_API_KEY=<YOUR OPENAI API KEY> python-bot` in the root directory

### Running from source
+ (Recommended) Create a virtual environment
+ Install the dependencies from `requirements.txt` with `pip install -r requirements.txt` in the root directory
+ Set an environment variable for BOT_TOKEN with your bot's token
+ Set an environment variable for GUILD_IDS with the Discord guild ids (servers) you wish to deploy the bot on
+ Set an environment variable for OPENAI_API_KEY with the OpenAI API key (available at <a href="https://platform.openai.com/api-keys">OpenAI API Platform</a>)
+ Run the bot with `python src/bot.py` in the root directory
