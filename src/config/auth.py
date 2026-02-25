import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = str(os.getenv("BOT_TOKEN"))
GUILD_IDS = [int(id) for id in os.getenv("GUILD_IDS", "").split(",") if id]
OPENAI_API_KEY = str(os.getenv("OPENAI_API_KEY"))
OPENAI_VECTOR_STORE_IDS = [
    store_id
    for store_id in os.getenv("OPENAI_VECTOR_STORE_IDS", "").split(",")
    if store_id
]
