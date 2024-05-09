import aiohttp
import logging
import io
import openai
from discord.ext import commands
from discord.commands import slash_command, option, OptionChoice
from discord import ApplicationContext, Colour, Embed, File
import json
from pathlib import Path
from typing import Dict, List, Optional

from config.auth import GUILD_IDS, OPENAI_API_KEY


class ChatGPT(commands.Cog):
    def __init__(self, bot):
        """
        Initialize the ChatGPT class.

        Args:
            bot: The bot instance.
        """
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.bot = bot
        openai.api_key = OPENAI_API_KEY

        # Dictionary to store conversation history for each thread
        self.conversation_histories = {}

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener that runs when the bot is ready.
        Logs bot details and attempts to synchronize commands.
        """
        logging.info(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        logging.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            logging.info("Commands synchronized successfully.")
        except Exception as e:
            logging.error(f"Error during command synchronization: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        logging.info(f"Message received: {message.content}")

        # Ignore messages sent by the bot itself or not within a thread
        if message.author == self.bot.user or message.thread is None:
            return

        # Retrieve the thread ID
        thread_id = message.thread.id

        # Initialize conversation history for the thread if not already present
        if thread_id not in self.conversation_histories:
            self.conversation_histories[thread_id] = []
            logging.info(f"Conversation history initialized for thread {thread_id}")

        # Log message details, assuming it's from the user
        logging.info(
            f"Message received in thread {thread_id} from {message.author}: {message.content}"
        )

        # Append the message to the conversation history
        self.conversation_histories[thread_id].append(
            {"role": "user", "content": message.content}
        )

        try:
            # Generate and send response if the message is from a user
            response = await self.chat(self.conversation_histories[thread_id])
            await message.thread.send(response)
        except Exception as e:
            logging.error(f"Error during chat attempt: {e}", exc_info=True)

    @slash_command(
        name="chat",
        description="Creates a model response for the given chat conversation.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True)
    @option(
        "personality",
        description="What role you want the model to emulate. (default: You are a helpful assistant.)",
        required=False,
    )
    @option(
        "model",
        description="Choose from the following GPT models (default: gpt-4-turbo)",
        required=False,
        choices=[
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo-0125"),
            OptionChoice(name="GPT-3.5 Turbo 16k", value="gpt-3.5-turbo-16k"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
        ],
    )
    @option(
        "message_history",
        description="A list of messages comprising the conversation so far. JSON format as string required.",
        required=False,
        type=str,
    )
    async def chat(
        self,
        ctx: ApplicationContext,
        prompt: str,
        personality: str = "You are a helpful assistant.",
        model: str = "gpt-4-turbo",
        message_history: str = None,
    ):
        """
        Creates a model response for the given chat conversation.

        Args:
          messages: A list of messages comprising the conversation so far.
              [Example Python code](https://cookbook.openai.com/examples/how_to_format_inputs_to_chatgpt_models).

          model: ID of the model to use. See the
              [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
              table for details on which models work with the Chat API.
        """
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        try:
            # Parse the messages string into a list of dictionaries
            message_list = json.loads(message_history) if message_history else []

            # Create the final input from the prompt, personality, and message list
            messages = [
                {"role": "system", "content": personality},
                {"role": "user", "content": prompt},
            ] + message_list

            response = openai.chat.completions.create(
                messages=messages,
                model=model,
            )
            response_text = (
                response.choices[0].message.content
                if response.choices
                else "No response."
            )
            await ctx.followup.send(
                embed=Embed(
                    title="ChatGPT Text Generation",
                    description=f"**Prompt:**\n{prompt}\n\n**Response:**\n{response_text}",
                    color=Colour.blue(),
                )
            )
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )

    @slash_command(
        name="generate_image",
        description="Generate image from prompt. Image URLs expire after 1 hour.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True)
    @option(
        "model",
        description="Choose from the following DALL-E models (default: dall-e-3)",
        required=False,
        choices=[
            OptionChoice(name="DALL-E 2", value="dall-e-2"),
            OptionChoice(name="DALL-E 3", value="dall-e-3"),
        ],
    )
    @option(
        "n",
        description="Number of images to generate (default: 1)",
        required=False,
        type=int,
    )
    @option(
        "quality",
        description="Quality of the image (default: standard)",
        required=False,
        choices=[
            OptionChoice(name="Standard", value="standard"),
            OptionChoice(name="HD", value="hd"),
        ],
    )
    @option(
        "size",
        description="Size of the image (default: 1024x1024)",
        required=False,
        choices=[
            OptionChoice(name="256x256", value="256x256"),
            OptionChoice(name="512x512", value="512x512"),
            OptionChoice(name="1024x1024", value="1024x1024"),
            OptionChoice(name="1024x1792 (landscape)", value="1024x1792"),
            OptionChoice(name="1792x1024 (portrait)", value="1792x1024"),
        ],
    )
    @option(
        "style",
        description="Style of the image. Only supported for DALL-E 3. (default: natural)",
        required=False,
        choices=[
            OptionChoice(name="Vivid", value="vivid"),
            OptionChoice(name="Natural", value="natural"),
        ],
    )
    async def generate_image(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "dall-e-3",
        n: int = 1,
        quality: str = "standard",
        size: str = "1024x1024",
        style: str = "natural",
    ):
        """
        Creates an image given a prompt.

        Args:
          prompt: A text description of the desired image(s). The maximum length is 1000
              characters for `dall-e-2` and 4000 characters for `dall-e-3`.

          model: The model to use for image generation.

          n: The number of images to generate. Must be between 1 and 10. For `dall-e-3`, only
              `n=1` is supported.

          quality: The quality of the image that will be generated. `hd` creates images with finer
              details and greater consistency across the image. This param is only supported
              for `dall-e-3`.

          size: The size of the generated images. Must be one of `256x256`, `512x512`, or
              `1024x1024` for `dall-e-2`. Must be one of `1024x1024`, `1792x1024`, or
              `1024x1792` for `dall-e-3` models.

          style: The style of the generated images. Must be one of `vivid` or `natural`. Vivid
              causes the model to lean towards generating hyper-real and dramatic images.
              Natural causes the model to produce more natural, less hyper-real looking
              images. This param is only supported for `dall-e-3`.
        """
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time

        # Guard clauses for model-specific constraints
        if (model == "dall-e-2" and n > 10) or (model == "dall-e-3" and n > 1):
            error_message = (
                "The maximum number of images for DALL-E 2 is 10 and for DALL-E 3 is 1."
            )
            await ctx.followup.send(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-2" and (size == "1024x1792" or size == "1792x1024"):
            error_message = "The DALL-E 2 model only supports `256x256`, `512x512`, or `1024x1024` image size."
            await ctx.followup.send(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-3" and (size == "256x256" or size == "512x512"):
            error_message = "The DALL-E 3 model only supports `1024x1024`, `1792x1024`, or `1024x1792` image size."
            await ctx.followup.send(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-2" and quality == "hd":
            error_message = "The `hd` quality is only supported for DALL-E 3."
            await ctx.followup.send(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        # Initialize parameters for the image generation API
        image_params = {
            "prompt": prompt,
            "model": model,
            "n": n,
            "quality": quality,
            "size": size,
        }

        # style parameter is not supported for DALL-E 2
        if model != "dall-e-2" or style is not None:
            image_params["style"] = style

        try:
            response = openai.images.generate(**image_params)
            image_urls = [data.url for data in response.data]
            if image_urls:
                image_files = []
                for idx, url in enumerate(image_urls):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                await ctx.followup.send("Could not download file...")
                                continue  # Skip this iteration and proceed with the next image
                            data = io.BytesIO(await resp.read())
                            image_files.append(File(data, f"image{idx}.png"))

                if len(image_files) <= 0:
                    raise Exception("No images were generated.")

                embed = Embed(
                    title="DALL-E Image Generation",
                    description=f"**Prompt:**\n{prompt}",
                    color=Colour.blue(),
                )
                await ctx.followup.send(embed=embed, files=image_files)
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )

    @slash_command(
        name="text_to_speech",
        description="Generates audio from the input text.",
        guild_ids=GUILD_IDS,
    )
    @option(
        "input",
        description="Text to convert to speech (max length 4096 characters)",
        required=True,
    )
    @option(
        "model",
        description="Choose from the following TTS models (default: tts-1)",
        required=False,
        choices=[
            OptionChoice(name="tts-1", value="tts-1"),
            OptionChoice(name="tts-1-hd", value="tts-1-hd"),
        ],
    )
    @option(
        "voice",
        description="Choose a voice for the speech (default: alloy)",
        required=False,
        choices=[
            OptionChoice(name="alloy", value="alloy"),
            OptionChoice(name="echo", value="echo"),
            OptionChoice(name="fable", value="fable"),
            OptionChoice(name="onyx", value="onyx"),
            OptionChoice(name="nova", value="nova"),
            OptionChoice(name="shimmer", value="shimmer"),
        ],
    )
    @option(
        "response_format",
        description="Choose the format of the audio (default: mp3)",
        required=False,
        choices=[
            OptionChoice(name="MP3", value="mp3"),
            OptionChoice(name="WAV", value="wav"),
            OptionChoice(name="Opus", value="opus"),
            OptionChoice(name="AAC", value="aac"),
            OptionChoice(name="FLAC", value="flac"),
            OptionChoice(name="PCM", value="pcm"),
        ],
    )
    @option(
        "speed",
        description="Speed of the generated audio (default: 1.0)",
        required=False,
        type=float,
    )
    async def text_to_speech(
        self,
        ctx: ApplicationContext,
        input: str,
        model: str = "tts-1",
        voice: str = "alloy",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        """
        Generates audio from the input text.

        Args:
          input: The text to generate audio for. The maximum length is 4096 characters.

          model:
              One of the available [TTS models](https://platform.openai.com/docs/models/tts):
              `tts-1` or `tts-1-hd`

          voice: The voice to use when generating the audio. Supported voices are `alloy`,
              `echo`, `fable`, `onyx`, `nova`, and `shimmer`. Previews of the voices are
              available in the
              [Text to speech guide](https://platform.openai.com/docs/guides/text-to-speech/voice-options).

          response_format: The format to audio in. Supported formats are `mp3`, `opus`, `aac`, `flac`,
              `wav`, and `pcm`.

          speed: The speed of the generated audio. Select a value from `0.25` to `4.0`. `1.0` is
              the default.
        """
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        try:
            # Generate spoken audio from input text
            response = openai.audio.speech.create(
                input=input,
                model=model,
                voice=voice,
                response_format=response_format,
                speed=speed,
            )

            # Path where the audio file will be saved
            speech_file_path = (
                Path(__file__).parent / f"{voice}_speech.{response_format}"
            )

            # Stream audio to file
            response.write_to_file(speech_file_path)

            # Inform the user that the audio has been created
            embed = Embed(
                title="Text to Speech Conversion",
                description=f"**Text:** {input}\n**Voice:** {voice}",
                color=Colour.green(),
            )
            await ctx.followup.send(embed=embed, file=File(speech_file_path))
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )
        finally:
            # Delete the audio file after sending
            speech_file_path.unlink(missing_ok=True)
