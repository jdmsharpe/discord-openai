__all__ = ["OpenAICog"]


def __getattr__(name: str):
    if name == "OpenAICog":
        from .cog import OpenAICog

        return OpenAICog
    raise AttributeError(name)
