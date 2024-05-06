import logging
import openai
from discord.ext import commands
from discord.commands import slash_command, option, OptionChoice
from discord import ApplicationContext, Embed, Colour

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
                model=model,
                messages=[
                    {"role": "system", "content": personality},
                    {"role": "user", "content": prompt},
                ],
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
        "n", description="Number of images to generate (default: 1)", required=False, type=int
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
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        model: str = "dall-e-3",
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
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
            )
            image_url = response.data[0].url if response.data else "No image."
            embed = Embed(
                title="ChatGPT Response",
                description=f"**Your Prompt:**\n{prompt}",
                color=Colour.blue(),
            )
            embed.set_image(url=image_url)  # Setting the image URL in the embed
            await ctx.followup.send(embed=embed)
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )
