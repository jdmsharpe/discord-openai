from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cog import OpenAICog

__all__ = ["OpenAICog"]


def __getattr__(name: str):
    if name == "OpenAICog":
        from .cog import OpenAICog

        return OpenAICog
    raise AttributeError(name)
