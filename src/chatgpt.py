import logging
import openai
from discord.ext import commands
from discord.commands import slash_command, option, OptionChoice
from discord import ApplicationContext, Colour, Embed, File
from pathlib import Path

from config.auth import GUILD_IDS, OPENAI_API_KEY


class ChatGPT(commands.Cog):
    def __init__(self, bot):
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.bot = bot
        openai.api_key = OPENAI_API_KEY

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        logging.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            logging.info("Commands synchronized successfully.")
        except Exception as e:
            logging.error(f"Error during command synchronization: {e}", exc_info=True)

    @slash_command(
        name="chat",
        description="Generate text in response to prompt.",
        guild_ids=GUILD_IDS,
    )
    @option("prompt", description="Prompt", required=True)
    @option(
        "personality",
        description="A description of what role you want the model to emulate",
        required=False,
    )
    @option(
        "model",
        description="Choose from the following GPT models (default: GPT-4 Turbo for cheaper cost)",
        required=False,
        choices=[
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo-0125"),
            OptionChoice(name="GPT-3.5 Turbo 16k", value="gpt-3.5-turbo-16k"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
        ],
    )
    async def chat(
        self,
        ctx: ApplicationContext,
        prompt: str,
        personality: str = "You are a helpful assistant.",
        model: str = "gpt-4-turbo",
    ):
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        try:
            response = openai.chat.completions.create(
                messages=[
                    {"role": "system", "content": personality},
                    {"role": "user", "content": prompt},
                ],
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
        "size",
        description="Size of the image in pixels (default: 1024x1024)",
        required=False,
        choices=[
            OptionChoice(name="1024x1024", value="1024x1024"),
            OptionChoice(name="1024x1792 (landscape)", value="1024x1792"),
            OptionChoice(name="1792x1024 (portrait)", value="1792x1024"),
        ],
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
        "n",
        description="Number of images to generate (default: 1)",
        required=False,
        type=int,
    )
    @option(
        "model",
        description="Choose from the following DALL-E models (default: dall-e-3)",
        required=False,
        choices=[
            OptionChoice(name="DALL-E 3", value="dall-e-3"),
            OptionChoice(name="DALL-E 2", value="dall-e-2"),
        ],
    )
    async def generate_image(
        self,
        ctx: ApplicationContext,
        prompt: str,
        n: int = 1,
        quality: str = "standard",
        model: str = "dall-e-3",
        size: str = "1024x1024",
        style: str = "",
    ):
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        if model == "dall-e-2" and n > 10 or model == "dall-e-3" and n > 1:
            await ctx.followup.send(
                embed=Embed(
                    title="Error",
                    description="The maximum number of images for DALL-E 2 is 10 and for DALL-E 3 is 1.",
                    color=Colour.red(),
                )
            )
            return
        try:
            response = openai.images.generate(
                prompt=prompt, n=n, quality=quality, model=model, size=size, style=style
            )
            image_url = response.data[0].url if response.data else "No image."
            embed = Embed(
                title="DALL-E Image Generation",
                description=f"**Your Prompt:**\n{prompt}",
                color=Colour.blue(),
            )
            embed.set_image(url=image_url)  # Setting the image URL in the embed
            embed.image.url
            await ctx.followup.send(embed=embed)
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )

    @slash_command(
        name="text_to_speech",
        description="Converts text to lifelike spoken audio.",
        guild_ids=GUILD_IDS,
    )
    @option("text", description="Text to convert to speech", required=True)
    @option(
        "voice",
        description="Choose a voice for the speech",
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
    @option(
        "model",
        description="Choose from the following TTS models",
        required=False,
        choices=[
            OptionChoice(name="tts-1", value="tts-1-"),
            OptionChoice(name="tts-1-hd", value="tts-1-hd"),
        ],
    )
    async def text_to_speech(
        self,
        ctx: ApplicationContext,
        text: str,
        model: str = "tts-1",
        voice: str = "alloy",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        try:
            # Generate spoken audio from input text
            response = openai.audio.speech.create(
                input=text,
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
                description=f"**Text:** {text}\n**Voice:** {voice}\n**Audio File:** Attached",
                color=Colour.green(),
            )
            await ctx.followup.send(embed=embed, file=File(speech_file_path))
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )
