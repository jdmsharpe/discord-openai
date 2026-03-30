from discord import Bot, Intents

from discord_openai import OpenAIAPI


def test_package_import_and_cog_registration():
    intents = Intents.default()
    bot = Bot(intents=intents)
    bot.add_cog(OpenAIAPI(bot=bot))
    assert bot.get_cog("OpenAIAPI") is not None
