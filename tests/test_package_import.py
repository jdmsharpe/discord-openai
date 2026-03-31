from discord import Bot, Intents

from discord_openai import OpenAICog


def test_package_import_registers_cog():
    bot = Bot(intents=Intents.default())
    bot.add_cog(OpenAICog(bot=bot))
    assert bot.get_cog("OpenAICog") is not None
