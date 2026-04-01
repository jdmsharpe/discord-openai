import importlib
import sys
from contextlib import contextmanager


@contextmanager
def _fresh_package(prefix: str):
    original_modules = {
        name: module
        for name, module in list(sys.modules.items())
        if name == prefix or name.startswith(f"{prefix}.")
    }

    for name in original_modules:
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(f"{prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(original_modules)


def test_top_level_package_import_is_lazy():
    with _fresh_package("discord_openai"):
        package = importlib.import_module("discord_openai")

        assert "discord_openai.cogs.openai.cog" not in sys.modules
        assert "OpenAICog" in package.__all__


def test_cog_package_import_is_lazy():
    with _fresh_package("discord_openai"):
        package = importlib.import_module("discord_openai.cogs.openai")

        assert "discord_openai.cogs.openai.cog" not in sys.modules
        assert "OpenAICog" in package.__all__
