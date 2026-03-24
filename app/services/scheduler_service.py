import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from aiogram import Bot

from app.repositories.reminders import RemindersRepo, ReminderRecord
from app.repositories.users import UsersRepo
from app.utils.timezones import fmt_local_time_for_user, parse_hhmm

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, scheduler: AsyncIOScheduler, reminders_repo: RemindersRepo, users_repo: UsersRepo):
        self.scheduler = scheduler
        self.reminders_repo = reminders_repo
        self.users_repo = users_repo

    @staticmethod
    def once_job_id(reminder_id: int) -> str:
        return f"once_reminder_{reminder_id}"

    @staticmethod
    def recurring_job_id(reminder_id: int, user_id: int) -> str:
        return f"recurring_reminder_{reminder_id}_user_{user_id}"

    async def send_once_reminder(self, bot: Bot, reminder_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.kind != "once" or reminder.scheduled_at_utc is None:
            return

        dt_utc = datetime.fromisoformat(reminder.scheduled_at_utc)
        recipients = await self.reminders_repo.get_recipients(reminder_id)
        for user_id in recipients:
            user = await self.users_repo.get_user(user_id)
            if not user:
                continue
            local_when = fmt_local_time_for_user(dt_utc, user.timezone_name)
            try:
                await bot.send_message(
                    user_id,
                    "⏰ Напоминание\n\n"
                    f"ID: {reminder.id}\n"
                    "Тип: одноразовое\n"
                    f"Когда у тебя: {local_when}\n"
                    f"Текст: {reminder.text}",
                )
            except Exception:
                logger.exception("Не удалось отправить одноразовое напоминание user_id=%s reminder_id=%s", user_id, reminder_id)

        await self.reminders_repo.deactivate_reminder(reminder_id)
        job = self.scheduler.get_job(self.once_job_id(reminder_id))
        if job:
            self.scheduler.remove_job(self.once_job_id(reminder_id))

    async def send_recurring_reminder(self, bot: Bot, reminder_id: int, user_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.kind not in ("daily", "weekly"):
            return

        user = await self.users_repo.get_user(user_id)
        if not user:
            return

        now_local = datetime.now(ZoneInfo(user.timezone_name))
        try:
            await bot.send_message(
                user_id,
                "⏰ Напоминание\n\n"
                f"ID: {reminder.id}\n"
                f"Тип: {'ежедневное' if reminder.kind == 'daily' else 'еженедельное'}\n"
                f"Твоя таймзона: {user.timezone_name}\n"
                f"Сейчас у тебя: {now_local.strftime('%d.%m.%Y %H:%M')}\n"
                f"Текст: {reminder.text}",
            )
        except Exception:
            logger.exception("Не удалось отправить повторяющееся напоминание user_id=%s reminder_id=%s", user_id, reminder_id)

    def schedule_once_job(self, reminder: ReminderRecord, bot: Bot) -> None:
        if reminder.scheduled_at_utc is None:
            return
        run_at = datetime.fromisoformat(reminder.scheduled_at_utc)
        self.scheduler.add_job(
            self.send_once_reminder,
            trigger=DateTrigger(run_date=run_at, timezone=timezone.utc),
            args=[bot, reminder.id],
            id=self.once_job_id(reminder.id),
            replace_existing=True,
            misfire_grace_time=300,
        )

    def schedule_recurring_job_for_user(self, reminder: ReminderRecord, user_id: int, tz_name: str, bot: Bot) -> None:
        if reminder.local_time is None:
            return
        hour, minute = parse_hhmm(reminder.local_time)
        if reminder.kind == "daily":
            trigger = CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo(tz_name))
        elif reminder.kind == "weekly":
            if reminder.weekday is None:
                return
            trigger = CronTrigger(day_of_week=reminder.weekday, hour=hour, minute=minute, timezone=ZoneInfo(tz_name))
        else:
            return

        self.scheduler.add_job(
            self.send_recurring_reminder,
            trigger=trigger,
            args=[bot, reminder.id, user_id],
            id=self.recurring_job_id(reminder.id, user_id),
            replace_existing=True,
            misfire_grace_time=300,
        )

    async def reschedule_user_recurring_jobs(self, user_id: int, bot: Bot) -> None:
        reminders = await self.reminders_repo.get_active_recurring_reminders()
        user = await self.users_repo.get_user(user_id)
        if not user:
            return

        for reminder in reminders:
            recipients = await self.reminders_repo.get_recipients(reminder.id)
            if user_id not in recipients:
                continue
            existing = self.scheduler.get_job(self.recurring_job_id(reminder.id, user_id))
            if existing:
                self.scheduler.remove_job(self.recurring_job_id(reminder.id, user_id))
            self.schedule_recurring_job_for_user(reminder, user_id, user.timezone_name, bot)

    async def restore_jobs(self, bot: Bot) -> None:
        now_utc = datetime.now(timezone.utc)
        once_reminders = await self.reminders_repo.get_active_once_reminders()
        for reminder in once_reminders:
            if reminder.scheduled_at_utc is None:
                continue
            dt_utc = datetime.fromisoformat(reminder.scheduled_at_utc)
            if dt_utc <= now_utc:
                await self.reminders_repo.deactivate_reminder(reminder.id)
                continue
            self.schedule_once_job(reminder, bot)

        recurring_reminders = await self.reminders_repo.get_active_recurring_reminders()
        for reminder in recurring_reminders:
            recipients = await self.reminders_repo.get_recipients(reminder.id)
            for user_id in recipients:
                user = await self.users_repo.get_user(user_id)
                if user:
                    self.schedule_recurring_job_for_user(reminder, user_id, user.timezone_name, bot)
