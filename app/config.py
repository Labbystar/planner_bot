import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Novosibirsk").strip()
DB_PATH = os.getenv("DB_PATH", "napomnime_visual.db").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
