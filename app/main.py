from __future__ import annotations

from aiogram import Bot, Dispatcher
from app.config import BOT_TOKEN
from app.db import init_db
from app.handlers import create, menu, reminder_actions, settings, start
from app.scheduler import start_scheduler
from app.handlers import stats, admin
from app.handlers import menu_sections

async def main() -> None:
    await init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(create.router)
    dp.include_router(menu.router)
    dp.include_router(reminder_actions.router)
    dp.include_router(settings.router)
    dp.include_router(stats.router)
    dp.include_router(admin.router)
    dp.include_router(menu_sections.router)
    start_scheduler(bot)
    await dp.start_polling(bot)
