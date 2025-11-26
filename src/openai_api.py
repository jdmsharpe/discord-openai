import aiohttp
import asyncio
from button_view import ButtonView
import logging
import io
from openai import AsyncOpenAI
from discord import (
    ApplicationContext,
    Attachment,
    Colour,
    Embed,
    File,
)
from discord.ext import commands
from discord.commands import command, option, OptionChoice, slash_command
from pathlib import Path
from typing import Optional
from util import (
    ChatCompletionParameters,
    chunk_text,
    format_openai_error,
    ImageGenerationParameters,
    INPUT_IMAGE_TYPE,
    INPUT_TEXT_TYPE,
    REASONING_MODELS,
    ResponseParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
)
from config.auth import GUILD_IDS, OPENAI_API_KEY


def append_response_embeds(embeds, response_text):
    # Discord limits: 4096 chars per embed description, 6000 chars total for all embeds
    # Account for existing embeds' character count
    current_total = sum(
        len(embed.description or "") + len(embed.title or "") for embed in embeds
    )
    remaining_chars = (
        6000 - current_total - 100
    )  # Leave buffer for field names/formatting

    # Truncate response if it would exceed the total limit
    if len(response_text) > remaining_chars:
        response_text = (
            response_text[: remaining_chars - 50]
            + "\n\n... (Response truncated due to Discord's 6000 character limit)"
        )

    # Ensure each chunk is no larger than 4096 characters (max Discord embed description length)
    for index, chunk in enumerate(chunk_text(response_text), start=1):
        embeds.append(
            Embed(
                title="Response" + f" (Part {index})" if index > 1 else "Response",
                description=chunk,
                color=Colour.blue(),
            )
        )


class OpenAIAPI(commands.Cog):
    def __init__(self, bot):
        """
        Initialize the OpenAIAPI class.

        Args:
            bot: The bot instance.
        """
        logging.basicConfig(
            level=logging.DEBUG,  # Capture all levels of logs
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)
        self.bot = bot
        self.openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # Dictionary to store conversation histories for each converse interaction
        self.conversation_histories = {}
        # Dictionary to store UI views for each conversation
        self.views = {}

    async def handle_new_message_in_conversation(self, message, conversation):
        """
        Handles a new message in an ongoing conversation using the Responses API.

        Args:
            message: The incoming Discord Message object.
            conversation: The conversation object, which is of type ResponseParameters.
        """
        self.logger.info(
            f"Handling new message in conversation {conversation.conversation_id}"
        )
        typing_task = None
        embeds = []

        try:
            # Start typing indicator
            typing_task = asyncio.create_task(self.keep_typing(message.channel))

            # Build input for Responses API
            # For text-only, use a simple string. For multimodal, use content array.
            if message.attachments:
                input_content = [{"type": INPUT_TEXT_TYPE, "text": message.content}]
                for attachment in message.attachments:
                    input_content.append(
                        {
                            "type": INPUT_IMAGE_TYPE,
                            "image_url": attachment.url,
                        }
                    )
            else:
                input_content = message.content  # Simple string for text-only
            self.logger.debug(f"Built input content: {input_content}")

            # Build API call parameters
            api_params = {
                "model": conversation.model,
                "input": input_content,
            }

            # Add previous_response_id for conversation chaining
            if conversation.previous_response_id:
                api_params["previous_response_id"] = conversation.previous_response_id

            # Add optional parameters if set
            if conversation.frequency_penalty is not None:
                api_params["frequency_penalty"] = conversation.frequency_penalty
            if conversation.presence_penalty is not None:
                api_params["presence_penalty"] = conversation.presence_penalty
            if conversation.seed is not None:
                api_params["seed"] = conversation.seed
            if conversation.temperature is not None:
                api_params["temperature"] = conversation.temperature
            if conversation.top_p is not None:
                api_params["top_p"] = conversation.top_p
            if conversation.reasoning is not None:
                api_params["reasoning"] = conversation.reasoning

            # API call using Responses API
            self.logger.debug("Making API call to OpenAI Responses API.")
            response = await self.openai.responses.create(**api_params)
            response_text = response.output_text if response.output_text else "No response."
            self.logger.debug(f"Received response from OpenAI: {response_text}")

            # Update conversation state with new response ID
            conversation.previous_response_id = response.id
            conversation.response_id_history.append(response.id)
            self.logger.debug(
                f"Updated previous_response_id to: {response.id}"
            )

            # Assemble the response
            append_response_embeds(embeds, response_text)

            if embeds:
                await message.reply(
                    embeds=embeds,
                    view=(
                        self.views[message.author]
                        if message.author in self.views
                        else None
                    ),
                )
                self.logger.debug("Replied with generated response.")
            else:
                self.logger.warning("No embeds to send in the reply.")
                await message.reply(
                    content="An error occurred: No content to send.",
                    view=(
                        self.views[message.author]
                        if message.author in self.views
                        else None
                    ),
                )

        except Exception as e:
            description = format_openai_error(e)
            self.logger.error(
                f"Error in handle_new_message_in_conversation: {description}",
                exc_info=True,
            )
            await message.reply(
                embed=Embed(title="Error", description=description, color=Colour.red())
            )

        finally:
            if typing_task:
                typing_task.cancel()

    async def keep_typing(self, channel):
        """
        Coroutine to keep the typing indicator alive in a channel.

        Args:
            channel: The Discord channel object.
        """
        while True:
            async with channel.typing():
                await asyncio.sleep(5)  # Resend typing indicator every 5 seconds

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener that runs when the bot is ready.
        Logs bot details and attempts to synchronize commands.
        """
        self.logger.info(f"Logged in as {self.bot.user} (ID: {self.bot.owner_id})")
        self.logger.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            self.logger.info("Commands synchronized successfully.")
        except Exception as e:
            self.logger.error(
                f"Error during command synchronization: {e}", exc_info=True
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Event listener that runs when a message is sent.
        Generates a response using chat completion API when a new message from the conversation author is detected.

        Args:
            message: The incoming Discord Message object.
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # Look for a conversation that matches BOTH the channel AND the user
        for conversation in self.conversation_histories.values():
            # Check if message is in the same channel AND from the conversation starter
            if (
                message.channel.id == conversation.channel_id
                and message.author == conversation.conversation_starter
            ):
                if conversation.paused:
                    self.logger.debug(
                        "Ignoring message because conversation %s is paused.",
                        conversation.conversation_id,
                    )
                    return
                # Process the message for the matching conversation
                await self.handle_new_message_in_conversation(message, conversation)
                break  # Stop looping once we've handled the message

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """
        Event listener that runs when an error occurs.

        Args:
            event: The name of the event that raised the error.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.logger.error(f"Error in event {event}: {args} {kwargs}", exc_info=True)

    @slash_command(
        name="check_permissions",
        description="Check if bot has necessary permissions in this channel",
        guild_ids=GUILD_IDS,
    )
    async def check_permissions(self, ctx: ApplicationContext):
        permissions = ctx.channel.permissions_for(ctx.guild.me)
        if permissions.read_messages and permissions.read_message_history:
            await ctx.respond("Bot has permission to read messages and message history.")
        else:
            await ctx.respond("Bot is missing necessary permissions in this channel.")

    @slash_command(
        name="converse",
        description="Starts a conversation with a model.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "persona",
        description="What role you want the model to emulate. (default: You are a helpful assistant.)",
        required=False,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following GPT models. (default: GPT-5.1)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-5.1", value="gpt-5.1"),
            OptionChoice(name="GPT-5.1 Mini", value="gpt-5.1-mini"),
            OptionChoice(name="GPT-5.1 Nano", value="gpt-5.1-nano"),
            OptionChoice(name="GPT-5", value="gpt-5"),
            OptionChoice(name="GPT-5 Mini", value="gpt-5-mini"),
            OptionChoice(name="GPT-5 Nano", value="gpt-5-nano"),
            OptionChoice(name="GPT-4.1", value="gpt-4.1"),
            OptionChoice(name="GPT-4.1 Mini", value="gpt-4.1-mini"),
            OptionChoice(name="GPT-4.1 Nano", value="gpt-4.1-nano"),
            OptionChoice(name="o4 Mini", value="o4-mini"),
            OptionChoice(name="o3", value="o3"),
            OptionChoice(name="o3 Mini", value="o3-mini"),
            OptionChoice(name="o1", value="o1"),
            OptionChoice(name="o1 Mini", value="o1-mini"),
            OptionChoice(name="GPT-4o", value="gpt-4o"),
            OptionChoice(name="GPT-4o Mini", value="gpt-4o-mini"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo"),
        ],
    )
    @option(
        "attachment",
        description="Attachment to append to the prompt. Only images are supported at this time. (default: not set)",
        required=False,
        type=Attachment,
    )
    @option(
        "frequency_penalty",
        description="(Advanced) Controls how much the model should repeat itself. (default: not set)",
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
        model: str = "gpt-5.1",
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

          attachment: An image attachment to append to the prompt. Only images are supported.

          (Advanced) frequency_penalty: Controls how much the model should repeat itself.

          (Advanced) presence_penalty: Controls how much the model should talk about the prompt.

          (Advanced) seed: Seed for deterministic outputs.

          (Advanced) temperature: Controls the randomness of the model.

          (Advanced) top_p: Nucleus sampling.

          Please see https://platform.openai.com/docs/guides/text-generation for more information on advanced parameters.
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        for conversation in self.conversation_histories.values():
            if (
                conversation.conversation_starter == ctx.author
                and conversation.channel_id == ctx.channel_id
            ):
                await ctx.send_followup(
                    embed=Embed(
                        title="Error",
                        description="You already have an active conversation in this channel. Please finish it before starting a new one.",
                        color=Colour.red(),
                    )
                )
                return

        # Build input for Responses API
        # For text-only, use a simple string. For multimodal, use content array.
        if attachment is not None:
            input_content = [
                {"type": INPUT_TEXT_TYPE, "text": prompt},
                {"type": INPUT_IMAGE_TYPE, "image_url": attachment.url},
            ]
        else:
            input_content = prompt  # Simple string for text-only input

        # Create ResponseParameters for the new Responses API
        params = ResponseParameters(
            model=model,
            instructions=persona,
            input=input_content,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            seed=seed,
            temperature=temperature if model not in REASONING_MODELS else None,
            top_p=top_p if model not in REASONING_MODELS else None,
            reasoning={"effort": "medium"} if model in REASONING_MODELS else None,
            conversation_starter=ctx.author,
            conversation_id=ctx.interaction.id,
            channel_id=ctx.channel_id,
            response_id_history=[],
        )

        try:
            # Update initial response description based on input parameters
            description = ""
            description += f"**Prompt:** {prompt}\n"
            description += f"**Model:** {params.model}\n"
            description += f"**Persona:** {params.instructions}\n"
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
            if params.reasoning:
                description += f"**Reasoning Effort:** {params.reasoning.get('effort', 'medium')}\n"

            self.logger.info(
                f"converse: Conversation parameters initialized for interaction ID {ctx.interaction.id}."
            )

            # API call using Responses API
            response = await self.openai.responses.create(**params.to_dict())
            response_text = response.output_text if response.output_text else "No response."

            # Store response ID for conversation chaining
            params.previous_response_id = response.id
            params.response_id_history.append(response.id)
            # Clear input after first call (subsequent calls use previous_response_id)
            params.input = []

            # Assemble the response
            embeds = [
                Embed(
                    title="Conversation Started",
                    description=description,
                    color=Colour.green(),
                ),
            ]
            if attachment is not None:
                embeds.append(
                    Embed(
                        title="Attachment",
                        description=attachment.url,
                        color=Colour.green(),
                    )
                )
            append_response_embeds(embeds, response_text)
            self.views[ctx.author] = ButtonView(self, ctx.author, ctx.interaction.id)

            # Send response
            await ctx.send_followup(
                embeds=embeds,
                view=self.views[ctx.author],
            )

            # Store the conversation as a new entry in the dictionary
            self.conversation_histories[ctx.interaction.id] = params

        except Exception as e:
            error_message = format_openai_error(e)
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )

    @slash_command(
        name="generate_image",
        description="Generates image from a prompt.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "model",
        description="Choose from the following image generation models. (default: GPT-4 Image)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-4 Image", value="gpt-image-1"),
            OptionChoice(name="GPT-4 Image Mini", value="gpt-image-1-mini"),
            OptionChoice(name="DALL-E 3", value="dall-e-3"),
            OptionChoice(name="DALL-E 2", value="dall-e-2"),
        ],
    )
    @option(
        "n",
        description="Number of images to generate. (default: 1)",
        required=False,
        type=int,
    )
    @option(
        "quality",
        description="Image quality. Only supported for GPT-4 Image and DALL-E 3. (default: medium, HD for DALL-E 3)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Low (GPT-4 Image only)", value="low"),
            OptionChoice(name="Medium (GPT-4 Image only)", value="medium"),
            OptionChoice(name="High (GPT-4 Image only)", value="high"),
            OptionChoice(name="Auto (GPT-4 Image only)", value="auto"),
            OptionChoice(name="Standard (DALL-E 3 only)", value="standard"),
            OptionChoice(name="HD (DALL-E 3 only)", value="hd"),
        ],
    )
    @option(
        "size",
        description="Size of the image. (default: 1024x1024)",
        required=False,
        type=str,
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
        description="Style of the image. Only supported by DALL-E 3. (default: natural, not set for others)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Vivid", value="vivid"),
            OptionChoice(name="Natural", value="natural"),
        ],
    )
    async def generate_image(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "gpt-image-1",
        n: int = 1,
        quality: Optional[str] = "medium",
        size: Optional[str] = "1024x1024",
        style: Optional[str] = "natural",
    ):
        """
        Creates an image given a prompt.

        Args:
          prompt: A text description of the desired image(s). The maximum length is 1000
              characters for `dall-e-2` and 4000 characters for `dall-e-3`.

          model: The model to use for image generation. Defaults to `gpt-image-1` (a GPT-4
              based image generation model). You can also select `dall-e-2` or `dall-e-3`.

          n: The number of images to generate. Must be between 1 and 10. For `dall-e-3` and
              `gpt-image-1`, only `n=1` is supported.

          quality: The quality of the image that will be generated. This param is only supported
              for `dall-e-3` and `gpt-image-1`.

          size: The size of the generated images. Must be one of `256x256`, `512x512`, or
              `1024x1024` for `dall-e-2`. Must be one of `1024x1024`, `1792x1024`, or
              `1024x1792` for `dall-e-3` models.

          style: The style of the generated images. Must be one of `vivid` or `natural`. Vivid
              causes the model to lean towards generating hyper-real and dramatic images.
              Natural causes the model to produce more natural, less hyper-real looking
              images. This param is only supported for `dall-e-3`. Ignored when using
              the default `gpt-image-1` model.
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

        # Remove unsupported parameters based on model selection
        if model == "dall-e-2":
            style = None
            quality = None
        if model == "gpt-image-1" or model == "gpt-image-1-mini":
            style = None

        # Set HD quality for DALL-E 3 if an unsupported quality is provided
        if model == "dall-e-3" and quality not in ["standard", "hd"]:
            quality = "hd"

        # Set medium quality for GPT-4 Image if an unsupported quality is provided
        if (model == "gpt-image-1" or model == "gpt-image-1-mini") and quality not in [
            "low",
            "medium",
            "high",
            "auto",
        ]:
            quality = "medium"

        # Initialize parameters for the image generation API
        try:
            # Only set response_format for DALL-E models that support it
            response_format = "url" if model in ["dall-e-2", "dall-e-3"] else None

            image_params = ImageGenerationParameters(
                prompt=prompt,
                model=model,
                n=n,
                quality=quality,
                size=size,
                style=style,
                response_format=response_format,
            )
            self.logger.info(f"Generating {n} image(s) with model {model}")
        except Exception as e:
            error_message = format_openai_error(e)
            self.logger.error(
                f"Error creating image parameters: {error_message}", exc_info=True
            )
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=f"Failed to create image parameters: {error_message}",
                    color=Colour.red(),
                )
            )
            return

        try:
            response = await self.openai.images.generate(**image_params.to_dict())

            # Extract image data from response
            image_urls = []
            image_data = []
            for data_item in response.data:
                # Check if it has url attribute (DALL-E style)
                if hasattr(data_item, "url") and data_item.url:
                    image_urls.append(data_item.url)
                # Check if it has b64_json attribute (base64 style)
                elif hasattr(data_item, "b64_json") and data_item.b64_json:
                    image_data.append(data_item.b64_json)

            if image_urls or image_data:
                image_files = []

                # Process URL-based images (DALL-E models)
                for idx, url in enumerate(image_urls):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                self.logger.warning(
                                    f"Failed to download image {idx}, status: {resp.status}"
                                )
                                continue
                            data = io.BytesIO(await resp.read())
                            filename = f"image{idx}.png"
                            file_obj = File(data, filename)
                            image_files.append(file_obj)

                # Process base64-encoded images (gpt-image-1 model)
                for idx, b64_data in enumerate(image_data):
                    try:
                        import base64

                        image_bytes = base64.b64decode(b64_data)
                        data = io.BytesIO(image_bytes)
                        filename = f"image{len(image_urls) + idx}.png"
                        file_obj = File(data, filename)
                        image_files.append(file_obj)
                    except Exception as e:
                        self.logger.error(f"Error processing base64 image {idx}: {e}")
                        continue

                if len(image_files) <= 0:
                    raise Exception("No images were generated.")

                description = ""
                description += f"**Prompt:** {image_params.prompt}\n"
                description += f"**Model:** {image_params.model}\n"
                description += f"**Size:** {image_params.size}\n"
                if image_params.n > 1:
                    description += f"**Image count:** {image_params.n}\n"
                if image_params.quality:
                    description += f"**Quality:** {image_params.quality}\n"
                if image_params.style:
                    description += f"**Style:** {image_params.style}\n"

                embed = Embed(
                    title="Image Generation",
                    description=description,
                    color=Colour.blue(),
                )
                await ctx.send_followup(embed=embed, files=image_files)
                self.logger.info(
                    f"Successfully generated and sent {len(image_files)} image(s)"
                )

        except Exception as e:
            description = format_openai_error(e)
            self.logger.error(f"Image generation failed: {description}", exc_info=True)
            await ctx.send_followup(
                embed=Embed(title="Error", description=description, color=Colour.red())
            )

    @slash_command(
        name="text_to_speech",
        description="Generates lifelike audio from the input text.",
        guild_ids=GUILD_IDS,
    )
    @option(
        "input",
        description="Text to convert to speech. (max length 4096 characters)",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following TTS models. (default: GPT-4o Mini TTS)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="TTS-1", value="tts-1"),
            OptionChoice(name="TTS-1 HD", value="tts-1-hd"),
            OptionChoice(name="GPT-4o Mini TTS", value="gpt-4o-mini-tts"),
        ],
    )
    @option(
        "voice",
        description="The voice to use when generating the audio. (default: Alloy)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Alloy", value="alloy"),
            OptionChoice(name="Ash (Only supported with GPT-4o Mini TTS)", value="ash"),
            OptionChoice(
                name="Ballad (Only supported with GPT-4o Mini TTS)", value="ballad"
            ),
            OptionChoice(
                name="Coral (Only supported with GPT-4o Mini TTS)", value="coral"
            ),
            OptionChoice(name="Echo", value="echo"),
            OptionChoice(name="Fable", value="fable"),
            OptionChoice(name="Onyx", value="onyx"),
            OptionChoice(name="Nova", value="nova"),
            OptionChoice(
                name="Sage (Only supported with GPT-4o Mini TTS)", value="sage"
            ),
            OptionChoice(name="Shimmer", value="shimmer"),
            OptionChoice(
                name="Verse (Only supported with GPT-4o Mini TTS)", value="verse"
            ),
        ],
    )
    @option(
        "instructions",
        description="Control the voice of your generated audio with additional instructions. (default: not set)",
        required=False,
        type=str,
    )
    @option(
        "response_format",
        description="The format of the audio file output. (default: mp3)",
        required=False,
        type=str,
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
        description="Speed of the generated audio. (default: 1.0)",
        required=False,
        type=float,
    )
    async def text_to_speech(
        self,
        ctx: ApplicationContext,
        input: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
        instructions: str = "",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        """
        Generates lifelike audio from the provided text.

        Args:
          input: Text to convert (max 4096 chars).
          model: TTS model (e.g., gpt-4o-mini-tts, tts-1, tts-1-hd).
          voice: Voice to use.
          instructions: Extra voice style instructions (not for tts-1 / tts-1-hd).
          response_format: Audio file format.
          speed: Playback speed multiplier.
        """
        await ctx.defer()

        params = TextToSpeechParameters(
            input, model, voice, instructions, response_format, speed
        )
        speech_file_path = None
        try:
            response = await self.openai.audio.speech.create(**params.to_dict())
            speech_file_path = (
                Path(__file__).parent / f"{voice}_speech.{response_format}"
            )
            response.write_to_file(speech_file_path)

            description = (
                f"**Text:** {params.input}\n"
                f"**Model:** {params.model}\n"
                f"**Voice:** {params.voice}\n"
                + (f"**Instructions:** {instructions}\n" if params.instructions else "")
                + f"**Response Format:** {response_format}\n"
                + f"**Speed:** {params.speed}\n"
            )

            embed = Embed(
                title="Text-to-Speech", description=description, color=Colour.blue()
            )
            await ctx.send_followup(embed=embed, file=File(speech_file_path))
        except Exception as e:
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=format_openai_error(e),
                    color=Colour.red(),
                )
            )
        finally:
            if speech_file_path and speech_file_path.exists():
                speech_file_path.unlink(missing_ok=True)

    @slash_command(
        name="speech_to_text",
        description="Generates text from the input audio.",
        guild_ids=GUILD_IDS,
    )
    @option(
        "attachment",
        description="Attachment audio file. Max size 25 MB. Supported types: mp3, mp4, mpeg, mpga, m4a, wav, and webm.",
        required=True,
        type=Attachment,
    )
    @option(
        "model",
        description="Model to use for speech-to-text conversion. (default: GPT-4o Transcribe)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Whisper", value="whisper-1"),
            OptionChoice(name="GPT-4o Transcribe", value="gpt-4o-transcribe"),
            OptionChoice(name="GPT-4o Mini Transcribe", value="gpt-4o-mini-transcribe"),
        ],
    )
    @option(
        "action",
        description="Action to perform. (default: Transcription)",
        required=False,
        type=str,
        choices=[
            OptionChoice(
                name="Transcription",
                value="transcription",
            ),
            OptionChoice(
                name="Translation (into English)",
                value="translation",
            ),
        ],
    )
    async def speech_to_text(
        self,
        ctx: ApplicationContext,
        attachment: Attachment,
        model: str = "gpt-4o-transcribe",
        action: str = "transcription",
    ):
        """
        Generates text from the input audio.

        Args:
          model: The model to use for speech-to-text conversion. Supported models are `whisper-1`,
                `gpt-4o-transcribe`, and `gpt-4o-mini-transcribe`.

          attachment: The audio file to generate text from. File uploads are currently limited
                to 25 MB and the following input file types are supported: mp3, mp4, mpeg, mpga,
                m4a, wav, and webm.

          action: The action to perform. Supported actions are `transcription` and `translation`.
        """
        # Acknowledge the interaction immediately - reply can take some time
        await ctx.defer()

        # Initialize variables
        speech_file_path = None
        embeds = []
        response = ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as dl_resp:
                    if dl_resp.status != 200:
                        raise Exception("Failed to download the attachment")
                    speech_file_content = await dl_resp.read()

            speech_file_path = Path(f"/tmp/{attachment.filename}")
            speech_file_path.write_bytes(speech_file_content)

            with open(speech_file_path, "rb") as speech_file:
                if action == "transcription":
                    response = await self.openai.audio.transcriptions.create(
                        model=model, file=speech_file
                    )
                else:  # translation
                    response = await self.openai.audio.translations.create(
                        model=model, file=speech_file
                    )

            description = (
                f"**Model:** {model}\n"
                + f"**Action:** {action}\n"
                + (
                    f"**Output:** {response.text}\n"
                    if getattr(response, "text", None)
                    else ""
                )
            )
            embed = Embed(
                title="Speech-to-Text", description=description, color=Colour.blue()
            )
            await ctx.send_followup(embed=embed, file=File(speech_file_path))
        except Exception as e:
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=format_openai_error(e),
                    color=Colour.red(),
                )
            )
        finally:
            if speech_file_path and speech_file_path.exists():
                speech_file_path.unlink(missing_ok=True)

    @slash_command(
        name="generate_video",
        description="Generates a video based on a prompt using Sora.",
        guild_ids=GUILD_IDS,
    )
    @option(
        "prompt",
        description="Prompt for video generation (describe shot type, subject, action, setting, lighting).",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose Sora model for video generation. (default: Sora 2)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Sora 2 (Fast)", value="sora-2"),
            OptionChoice(name="Sora 2 Pro (High Quality)", value="sora-2-pro"),
        ],
    )
    @option(
        "size",
        description="Resolution of the generated video. (default: 1280x720)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Landscape (1280x720)", value="1280x720"),
            OptionChoice(name="Portrait (720x1280)", value="720x1280"),
            OptionChoice(name="Wide Landscape (1792x1024)", value="1792x1024"),
            OptionChoice(name="Tall Portrait (1024x1792)", value="1024x1792"),
        ],
    )
    @option(
        "seconds",
        description="Duration of the video in seconds. (default: 8)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="4 seconds", value="4"),
            OptionChoice(name="8 seconds", value="8"),
            OptionChoice(name="12 seconds", value="12"),
        ],
    )
    async def generate_video(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
    ):
        """
        Generates a video from a prompt using OpenAI's Sora model.

        Args:
            prompt: A text description of the desired video. For best results, describe
                shot type, subject, action, setting, and lighting.
            model: The Sora model to use. 'sora-2' is faster for iteration,
                'sora-2-pro' produces higher quality output.
            size: The resolution of the generated video.
            seconds: The duration of the video in seconds ('4', '8', or '12').
        """
        await ctx.defer()

        video_params = VideoGenerationParameters(
            prompt=prompt,
            model=model,
            size=size,
            seconds=seconds,
        )

        video_file_path = None
        try:
            # Start the video generation job
            self.logger.info(f"Starting video generation with model {model}")
            video = await self.openai.videos.create(**video_params.to_dict())

            self.logger.info(f"Video job started: {video.id}, status: {video.status}")

            # Poll for completion
            progress = video.progress if hasattr(video, "progress") and video.progress else 0
            poll_count = 0
            max_polls = 60  # 10 minutes with 10-second intervals

            while video.status in ("queued", "in_progress"):
                if poll_count >= max_polls:
                    raise Exception("Video generation timed out after 10 minutes")

                await asyncio.sleep(10)
                video = await self.openai.videos.retrieve(video.id)
                progress = video.progress if hasattr(video, "progress") and video.progress else 0
                poll_count += 1
                self.logger.debug(
                    f"Poll {poll_count}: status={video.status}, progress={progress}%"
                )

            if video.status == "failed":
                raise Exception("Video generation failed. Please try a different prompt.")

            if video.status != "completed":
                raise Exception(f"Unexpected video status: {video.status}")

            self.logger.info(f"Video generation completed: {video.id}")

            # Download the video
            content = await self.openai.videos.download_content(video.id)
            video_bytes = await content.aread()

            video_file_path = Path(__file__).parent / f"video_{video.id}.mp4"
            video_file_path.write_bytes(video_bytes)

            # Build response embed
            description = f"**Prompt:** {video_params.prompt}\n"
            description += f"**Model:** {video_params.model}\n"
            description += f"**Size:** {video_params.size}\n"
            description += f"**Duration:** {video_params.seconds} seconds\n"

            embed = Embed(
                title="Video Generation",
                description=description,
                color=Colour.blue(),
            )

            await ctx.send_followup(embed=embed, file=File(video_file_path))
            self.logger.info("Successfully sent generated video")

        except Exception as e:
            error_message = format_openai_error(e)
            self.logger.error(f"Video generation failed: {error_message}", exc_info=True)
            await ctx.send_followup(
                embed=Embed(
                    title="Error",
                    description=error_message,
                    color=Colour.red(),
                )
            )
        finally:
            if video_file_path and video_file_path.exists():
                video_file_path.unlink(missing_ok=True)
