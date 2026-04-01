import pytest


@pytest.fixture(autouse=True)
def _set_required_env_vars(monkeypatch):
    """Set dummy required env vars so the package can be imported in tests."""
    monkeypatch.setenv("BOT_TOKEN", "dummy-token")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
