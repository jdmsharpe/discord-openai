from discord import Bot, Intents

from discord_openai import OpenAICog


def test_package_import_and_cog_registration():
    intents = Intents.default()
    bot = Bot(intents=intents)
    bot.add_cog(OpenAICog(bot=bot))
    assert bot.get_cog("OpenAICog") is not None
