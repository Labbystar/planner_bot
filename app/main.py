import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Config, load_config
from app.db import init_db
from app.context import AppContext
from app.handlers import reminders, sharing, start, timezone
from app.repositories.reminders import RemindersRepo
from app.repositories.shares import SharesRepo
from app.repositories.users import UsersRepo
from app.services.scheduler_service import SchedulerService
from app.services.sharing_service import SharingService
from app.utils.timezones import validate_timezone_name

logging.basicConfig(level=logging.INFO)


def _register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(timezone.router)
    dp.include_router(reminders.router)
    dp.include_router(sharing.router)


async def main() -> None:
    config = load_config()
    validate_timezone_name(config.default_timezone)
    await init_db(config.db_path)

    users_repo = UsersRepo(config.db_path)
    reminders_repo = RemindersRepo(config.db_path)
    shares_repo = SharesRepo(config.db_path)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler_service = SchedulerService(scheduler, reminders_repo, users_repo)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    sharing_service = SharingService(config.bot_username, shares_repo, reminders_repo, users_repo, scheduler_service)

    app = AppContext(
        config=config,
        bot=bot,
        users_repo=users_repo,
        reminders_repo=reminders_repo,
        shares_repo=shares_repo,
        scheduler_service=scheduler_service,
        sharing_service=sharing_service,
    )

    dp = Dispatcher()
    dp["app"] = app
    _register_handlers(dp)

    scheduler.start()
    await scheduler_service.restore_jobs(bot)
    await dp.start_polling(bot)
