import asyncio

import pytest


@pytest.fixture(autouse=True)
def _set_required_env_vars(monkeypatch):
    """Set dummy required env vars so the package can be imported in tests."""
    monkeypatch.setenv("BOT_TOKEN", "dummy-token")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")


@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Guarantee a current event loop for every test.

    py-cord's ``Bot()`` constructor calls ``asyncio.get_event_loop()``, which
    raises ``RuntimeError`` on Python 3.11-3.13 when no loop is current — e.g.
    after pytest-asyncio (1.4+) tears down the loop left by a prior async test.
    Sync tests that build a Bot/cog would otherwise fail depending on order.
    """
    try:
        asyncio.get_event_loop()
        created = None
    except RuntimeError:
        created = asyncio.new_event_loop()
        asyncio.set_event_loop(created)
    yield
    if created is not None:
        created.close()
