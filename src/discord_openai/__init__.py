from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cogs.openai.cog import OpenAICog

__all__ = ["OpenAICog"]


def __getattr__(name: str):
    if name == "OpenAICog":
        from .cogs.openai import OpenAICog

        return OpenAICog
    raise AttributeError(name)
