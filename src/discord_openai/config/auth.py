import os

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


BOT_TOKEN = require_env("BOT_TOKEN")
GUILD_IDS = [int(id) for id in os.getenv("GUILD_IDS", "").split(",") if id]
OPENAI_API_KEY = require_env("OPENAI_API_KEY")
OPENAI_VECTOR_STORE_IDS = [
    store_id for store_id in os.getenv("OPENAI_VECTOR_STORE_IDS", "").split(",") if store_id
]
SHOW_COST_EMBEDS = os.getenv("SHOW_COST_EMBEDS", "true").lower() == "true"
