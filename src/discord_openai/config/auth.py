import os

from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS = ("BOT_TOKEN", "OPENAI_API_KEY")


def validate_required_config() -> None:
    missing_vars = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing_vars:
        missing_list = ", ".join(missing_vars)
        raise RuntimeError(
            "Missing required environment configuration: "
            f"{missing_list}. Please set these variables before starting the bot."
        )


BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_IDS = [int(id) for id in os.getenv("GUILD_IDS", "").split(",") if id]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_VECTOR_STORE_IDS = [
    store_id for store_id in os.getenv("OPENAI_VECTOR_STORE_IDS", "").split(",") if store_id
]
SHOW_COST_EMBEDS = os.getenv("SHOW_COST_EMBEDS", "true").lower() == "true"
