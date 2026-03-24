from dataclasses import dataclass

from aiogram import Bot

from app.config import Config
from app.repositories.reminders import RemindersRepo
from app.repositories.shares import SharesRepo
from app.repositories.users import UsersRepo
from app.services.scheduler_service import SchedulerService
from app.services.sharing_service import SharingService


@dataclass(slots=True)
class AppContext:
    config: Config
    bot: Bot
    users_repo: UsersRepo
    reminders_repo: RemindersRepo
    shares_repo: SharesRepo
    scheduler_service: SchedulerService
    sharing_service: SharingService
