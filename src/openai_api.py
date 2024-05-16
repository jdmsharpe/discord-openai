import aiohttp
import asyncio
import logging
import io
import openai
from discord import (
    ApplicationContext,
    Attachment,
    ButtonStyle,
    Colour,
    Embed,
    File,
    Interaction,
)
from discord.ext import commands
from discord.commands import slash_command, option, OptionChoice
from discord.ui import button, Button, View
from pathlib import Path
from typing import Optional
from util import (
    ChatCompletionParameters,
    ImageGenerationParameters,
    TextToSpeechParameters,
)

from config.auth import GUILD_IDS, OPENAI_API_KEY


class ButtonView(View):
    def __init__(self, cog, conversation_id):
        super().__init__()
        self.cog = cog
        self.conversation_id = conversation_id

    @button(label="Finish", style=ButtonStyle.danger)
    async def finish_button(self, button: Button, interaction: Interaction):
        # End the conversation
        if self.conversation_id in self.cog.conversation_histories:
            del self.cog.conversation_histories[self.conversation_id]
        await interaction.response.send_message(
            "Conversation finished.", ephemeral=True
        )
        # Disable the button
        button.disabled = True
        await interaction.message.edit(view=self)


class OpenAIAPI(commands.Cog):
    def __init__(self, bot):
        """
        Initialize the OpenAIAPI class.

        Args:
            bot: The bot instance.
        """
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.bot = bot
        openai.api_key = OPENAI_API_KEY

        # Dictionary to store conversation histories for each converse interaction
        self.conversation_histories = {}

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener that runs when the bot is ready.
        Logs bot details and attempts to synchronize commands.
        """
        logging.info(f"Logged in as {self.bot.user} (ID: {self.bot.owner_id})")
        logging.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            logging.info("Commands synchronized successfully.")
        except Exception as e:
            logging.error(f"Error during command synchronization: {e}", exc_info=True)

    async def keep_typing(self, channel):
        """
        Coroutine to keep the typing indicator alive in a channel.
        """
        while True:
            await channel.typing()
            await asyncio.sleep(5)  # Resend typing indicator every 5 seconds

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Event listener that runs when a message is sent.
        Generates a response using chat completion API when a new message from the conversation author is detected.
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        for conversation in self.conversation_histories.values():
            # Ignore messages not from the conversation starter or from another user
            if (
                message.author != conversation.conversation_starter
                and message.author != self.bot.user
            ):
                return

            # Should not happen, but just in case
            if (
                conversation.conversation_id not in self.conversation_histories.keys()
                or conversation.conversation_id is None
            ):
                self.conversation_histories[message.id] = ChatCompletionParameters(
                    model="gpt-4o",
                    conversation_starter=message.author,
                    conversation_id=message.id,
                )
                logging.info(
                    f"on_message: Conversation history and parameters initialized for interaction ID {message.id}."
                )

            # Determine the role based on the sender
            role = (
                "user"
                if message.author == conversation.conversation_starter
                else "assistant"
            )
            # Only attempt to generate a response if the message is from a user
            if role == "user":
                # Default response will be overwritten
                title = "ChatGPT Text Generation - Thread Conversation"
                description = ""
                color = Colour.blue()

                # Start typing and keep it alive until the response is ready
                typing_task = asyncio.create_task(self.keep_typing(message.channel))

                try:
                    content = {
                        "role": "user",
                        "content": {"type": "text", "text": message.content},
                    }

                    if message is not None and message.attachments[0] is not None:
                        # If the message contains attachments, append the attachment URLs to the prompt
                        for attachment in message.attachments:
                            content["content"].append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": {attachment.url}},
                                }
                            )

                    # Append the user's message to the conversation history
                    conversation.messages.append({"role": "user", "content": content})
                    response = openai.chat.completions.create(
                        messages=conversation.messages,
                        model=conversation.model,
                    )
                    response_text = (
                        response.choices[0].message.content
                        if response.choices
                        else "No response."
                    )

                    # Now that response is generated, add that to description and conversation history
                    description = f"**Response:**\n{response_text}"
                    conversation.messages.append(
                        {
                            "role": "assistant",
                            "content": {"type": "text", "text": response_text},
                        }
                    )

                except Exception as e:
                    title = "Error"
                    description = str(e)
                    if (
                        hasattr(e, "error")
                        and isinstance(e.error, dict)
                        and "message" in e.error
                    ):
                        description = e.error["message"]
                    color = Colour.red()

                finally:
                    # Assemble and send the response
                    embed = Embed(title=title, description=description, color=color)
                    view = ButtonView(self, message.id)
                    await message.reply(embed=embed, view=view)

                    # Stop typing
                    typing_task.cancel()

    @slash_command(
        name="converse",
        description="Starts a conversation with a model.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True)
    @option(
        "persona",
        description="What role you want the model to emulate. (default: You are a helpful assistant.)",
        required=False,
    )
    @option(
        "model",
        description="Choose from the following GPT models (default: gpt-4o)",
        required=False,
        choices=[
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo-0125"),
            OptionChoice(name="GPT-3.5 Turbo 16k", value="gpt-3.5-turbo-16k"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
            OptionChoice(name="GPT-4 Omni", value="gpt-4o"),
        ],
    )
    @option(
        "attachment",
        description="Attachment to append to the prompt. (default: none)",
        required=False,
        type=Attachment,
    )
    @option(
        "frequency_penalty",
        description="(Advanced) Controls how much the model should repeat itself. (default: 0.0)",
        required=False,
        type=float,
    )
    @option(
        "presence_penalty",
        description="(Advanced) Controls how much the model should talk about the prompt. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "seed",
        description="(Advanced) Seed for deterministic outputs. (default: not set)",
        required=False,
        type=int,
    )
    @option(
        "temperature",
        description="(Advanced) Controls the randomness of the model. Set this or top_p, but not both. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "top_p",
        description="(Advanced) Nucleus sampling. Set this or temperature, but not both. (default: not set)",
        required=False,
        type=float,
    )
    async def converse(
        self,
        ctx: ApplicationContext,
        prompt: str,
        persona: str = "You are a helpful assistant.",
        model: str = "gpt-4o",
        attachment: Optional[Attachment] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ):
        """
        Creates a model response for the given chat conversation.

        Args:
          prompt: The prompt to generate a response for.

          persona: The persona you want the model to emulate as a description. For example,
              "You are a helpful assistant." The maximum length is 1000 characters.

          model: ID of the model to use. See the
              [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
              table for details on which models work with the Chat API.

          (Advanced) frequency_penalty: Controls how much the model should repeat itself.

          (Advanced) presence_penalty: Controls how much the model should talk about the prompt.

          (Advanced) seed: Seed for deterministic outputs.

          (Advanced) temperature: Controls the randomness of the model.

          (Advanced) top_p: Nucleus sampling.

          Please see https://platform.openai.com/docs/guides/text-generation for more information on advanced parameters.
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        # Initialize parameters for the chat completions API
        params = ChatCompletionParameters(
            messages=[
                {"role": "system", "content": {"type": "text", "text": persona}},
                {"role": "user", "content": {"type": "text", "text": prompt}},
            ],
            model=model,
            persona=persona,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            seed=seed,
            temperature=temperature,
            top_p=top_p,
            conversation_starter=ctx.author,
            conversation_id=ctx.interaction.id,
        )

        typing_task = None

        try:
            # Update initial response description based on input parameters
            description = ""
            description += f"**Model:** {params.model}\n"
            description += f"**Persona:** {params.persona}\n"
            description += (
                f"**Frequency Penalty:** {params.frequency_penalty}\n"
                if params.frequency_penalty
                else ""
            )
            description += (
                f"**Presence Penalty:** {params.presence_penalty}\n"
                if params.presence_penalty
                else ""
            )
            description += f"**Seed:** {params.seed}\n" if params.seed else ""
            description += (
                f"**Temperature:** {params.temperature}\n" if params.temperature else ""
            )
            description += (
                f"**Nucleus Sampling:** {params.top_p}\n" if params.top_p else ""
            )

            # Send conversation acknowledgement
            await ctx.send(
                embed=Embed(
                    title="ChatGPT Conversation Started",
                    description=description,
                    color=Colour.green(),
                )
            )

            content = {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }

            if attachment is not None:
                content["content"].append(
                    {"type": "image_url", "image_url": {"url": attachment.url}}
                )

            # Append the user's message to the conversation history
            params.messages.append(content)
            logging.info(
                f"converse: Conversation history and parameters initialized for interaction ID {ctx.interaction.id}."
            )

            # API call
            response = openai.chat.completions.create(**params.to_dict())
            response_text = (
                response.choices[0].message.content
                if response.choices
                else "No response."
            )

            # Start typing and keep it alive until the response is ready
            typing_task = asyncio.create_task(self.keep_typing(ctx.message.channel))

            view = ButtonView(self, ctx.interaction.id)

            # Send response
            await ctx.send_followup(
                embed=Embed(
                    title="ChatGPT Text Generation",
                    description=f"**Prompt:**\n{prompt}\n\n**Response:**\n{response_text}",
                    color=Colour.blue(),
                ),
                view=view,
            )
            params.messages.append(
                {
                    "role": "assistant",
                    "content": {"type": "text", "text": response_text},
                }
            )
            self.conversation_histories[ctx.interaction.id] = params

        except Exception as e:
            error_message = str(e)
            if (
                hasattr(e, "error")
                and isinstance(e.error, dict)
                and "message" in e.error
            ):
                error_message = e.error["message"]

            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )

        finally:
            # Stop typing
            if typing_task is not None:
                typing_task.cancel()

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
            OptionChoice(name="1024x1792 (portrait)", value="1024x1792"),
            OptionChoice(name="1792x1024 (landscape)", value="1792x1024"),
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
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        # Guard clauses for model-specific constraints
        if (model == "dall-e-2" and n > 10) or (model == "dall-e-3" and n > 1):
            error_message = (
                "The maximum number of images for DALL-E 2 is 10 and for DALL-E 3 is 1."
            )
            await ctx.send_followup(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-2" and (size == "1024x1792" or size == "1792x1024"):
            error_message = "The DALL-E 2 model only supports `256x256`, `512x512`, or `1024x1024` image size."
            await ctx.send_followup(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-3" and (size == "256x256" or size == "512x512"):
            error_message = "The DALL-E 3 model only supports `1024x1024`, `1792x1024`, or `1024x1792` image size."
            await ctx.send_followup(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        if model == "dall-e-2" and quality == "hd":
            error_message = "The `hd` quality option is only supported for DALL-E 3."
            await ctx.send_followup(
                embed=Embed(
                    title="Error", description=error_message, color=Colour.red()
                )
            )
            return

        # Strip style parameter if model is DALL-E 2
        if model == "dall-e-2" and style is not None:
            style = None

        # Initialize parameters for the image generation API
        image_params = ImageGenerationParameters(prompt, model, n, quality, size, style)

        try:
            response = openai.images.generate(**image_params.to_dict())
            image_urls = [data.url for data in response.data]
            if image_urls:
                image_files = []
                for idx, url in enumerate(image_urls):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                await ctx.send_followup("Could not download file...")
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
                await ctx.send_followup(embed=embed, files=image_files)

        except Exception as e:
            error_message = str(e)
            if (
                hasattr(e, "error")
                and isinstance(e.error, dict)
                and "message" in e.error
            ):
                error_message = e.error["message"]

            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
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
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        # Initialize parameters for the text-to-speech API
        text_to_speech_params = TextToSpeechParameters(
            input, model, voice, response_format, speed
        )

        try:
            response = openai.audio.speech.create(**text_to_speech_params.to_dict())

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
                color=Colour.blue(),
            )
            await ctx.send_followup(embed=embed, file=File(speech_file_path))

        except Exception as e:
            error_message = str(e)
            if (
                hasattr(e, "error")
                and isinstance(e.error, dict)
                and "message" in e.error
            ):
                error_message = e.error["message"]

            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )

        finally:
            # Delete the audio file after sending
            speech_file_path.unlink(missing_ok=True)
