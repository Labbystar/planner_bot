from dataclasses import dataclass

from aiogram import Bot

from app.config import Config
from app.repositories.events import EventsRepo
from app.repositories.groups import GroupsRepo
from app.repositories.reminders import RemindersRepo
from app.repositories.shares import SharesRepo
from app.repositories.templates import TemplatesRepo
from app.repositories.users import UsersRepo
from app.services.history_service import HistoryService
from app.services.scheduler_service import SchedulerService
from app.services.sharing_service import SharingService


@dataclass(slots=True)
class AppContext:
    config: Config
    bot: Bot
    users_repo: UsersRepo
    reminders_repo: RemindersRepo
    groups_repo: GroupsRepo
    templates_repo: TemplatesRepo
    shares_repo: SharesRepo
    events_repo: EventsRepo
    history_service: HistoryService
    scheduler_service: SchedulerService
    sharing_service: SharingService
