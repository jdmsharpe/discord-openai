# Discord ChatGPT Bot

<div align="center">

[![HitCount](https://hits.dwyl.com/jdmsharpe/discord-chatgpt.svg?style=flat-square&show=unique)](http://hits.dwyl.com/jdmsharpe/discord-chatgpt)
<a href="https://hub.docker.com/r/jsgreen152/discord-chatgpt" target="_blank" rel="noopener noreferrer">![Workflow](https://github.com/jdmsharpe/discord-chatgpt/actions/workflows/main.yml/badge.svg)</a>
  
</div>

## What is it?
This is a Discord bot built on [Pycord 2.0](https://github.com/Pycord-Development/pycord). It draws heavily from [Nick McGee's awesome discord-bot](https://github.com/Nick-McGee/discord-bot). The bot allows users in the server to interact with ChatGPT. It is controlled with slash commands and the message-based user interface.

Please also check out the official OpenAI Discord bot [here](https://github.com/openai/gpt-discord-bot/tree/main).

### Commands
+ `/chat <prompt>` - Creates a model response for the given prompt.
+ `/generate_image <prompt>` - Creates image(s) given a prompt.
+ `/text_to_speech <prompt>` - Generates lifelike spoken audio from the prompt.

### Thread Functionality
Starting a thread with `/thread name:<name> message:<message>` with a value for `name` that includes the string `ChatGPT` (case-sensitive) will start a conversation with a model. The model will keep track of the conversation history and remember past inputs.
+ You can add additional parameters (developer API options) to the name field in order, separated by forward slashes (`/`) as delimiters.
+ Accepted arguments after the initial `ChatGPT` string are `model`, `frequency_penalty`, `presence_penalty`, `temperature`, and `top_p` (AKA "Nucleus Sampling").
+ An example value for the thread name (also the default) is `ChatGPT/gpt-4-turbo/0.0/0.0/0.0/0.0`.
+ The model will take the `message` value for the initial prompt.
+ Any further response from the thread creator within the thread will be interpreted as a reply to the model's last output.

For more information on these thread parameters, please see [this OpenAI API doc on them](https://platform.openai.com/docs/guides/text-generation/parameter-details). Please also see the [helpful OpenAI API guide doc splash page](https://platform.openai.com/docs/overview) for further reference and information.

### UI

<div align="center">

![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/20d6af48-699c-40e7-be62-d62f1256744e)
![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/99e81595-b30f-40b5-b8ac-2a9c8cc49948)
![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/e69242d0-acdc-42af-be66-794c95d81af7)

</div>

### Demo

<div align="center">

![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/563968fe-caeb-4a0f-bd27-625839c251c7)
![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/d5e0758e-f9d5-4ca6-bdb4-bea33c5065a3)
![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/c5992fac-3372-4c99-81f1-93c7fbda1d0e)

</div>

## How to use it?
+ <a href="https://docs.pycord.dev/en/master/discord.html#:~:text=Make%20sure%20you're%20logged%20on%20to%20the%20Discord%20website.&text=Click%20on%20the%20%E2%80%9CNew%20Application,and%20clicking%20%E2%80%9CAdd%20Bot%E2%80%9D.">**Create a Discord Bot** and invite it to your Discord server</a>
+ Note that this bot needs the following Discord bot permissions to function correctly: ![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/92645355-827e-46a1-9140-cd56898e09c2)
+ Alongside the following intents: ![image](https://github.com/jdmsharpe/discord-chatgpt/assets/55511821/533b7a14-8174-43fa-999d-4bd6533cbc02)


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
