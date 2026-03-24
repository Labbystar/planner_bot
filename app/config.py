import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Config:
    bot_token: str
    bot_username: str
    default_timezone: str
    db_path: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не найден")

    return Config(
        bot_token=bot_token,
        bot_username=os.getenv("BOT_USERNAME", "").strip(),
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Novosibirsk").strip(),
        db_path=os.getenv("DB_PATH", "planner.db").strip(),
    )
