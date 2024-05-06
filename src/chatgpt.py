import logging
import openai
from discord.ext import commands
from discord.commands import slash_command, option, OptionChoice
from discord import ApplicationContext, Embed, Colour

from config.auth import GUILD_IDS, OPENAI_API_KEY


class ChatGPT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        openai.api_key = OPENAI_API_KEY

    @slash_command(
        name="chat", description="Post query to ChatGPT", guild_ids=GUILD_IDS
    )
    @option("query", description="Prompt", required=True)
    @option(
        "model",
        description="Choose a GPT model",
        required=False,
        choices=[
            OptionChoice(name="GPT-3.5 Turbo", value="gpt-3.5-turbo-0125"),
            OptionChoice(name="GPT-3.5 Turbo 16k", value="gpt-3.5-turbo-16k"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
        ],
    )
    async def chat(
        self, ctx: ApplicationContext, query: str, model: str = "gpt-4-turbo"
    ):
        await ctx.defer()  # Acknowledge the interaction immediately - reply can take some time
        try:
            response = openai.chat.completions.create(
                model=model, messages=[{"role": "user", "content": query}]
            )
            response_text = (
                response.choices[0].message.content
                if response.choices
                else "No response."
            )
            await ctx.followup.send(
                embed=Embed(
                    title="ChatGPT Response",
                    description=response_text,
                    color=Colour.blue(),
                )
            )
        except Exception as e:
            await ctx.followup.send(
                embed=Embed(title="Error", description=str(e), color=Colour.red())
            )

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info('Synchronizing commands...')
        try:
            await self.sync_commands()
            logging.info('Commands synchronized successfully.')
        except Exception as e:
            logging.error(f'Failed to synchronize commands: {e}', exc_info=True)

    async def on_command_error(self, context, exception):
        if isinstance(exception, commands.CommandNotFound):
            logging.warning(f'Command not found: {context.message.content}')
        else:
            logging.error(f'Unexpected error: {exception}', exc_info=True)

    async def on_application_command_error(self, interaction, exception):
        logging.error(f'Error in application command: {exception}', exc_info=True)
        # Respond to the interaction with the error message
        await interaction.response.send_message(f'An error occurred: {exception}', ephemeral=True)
