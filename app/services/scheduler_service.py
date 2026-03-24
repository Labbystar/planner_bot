import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.keyboards.reminder_actions import reminder_actions_kb
from app.repositories.reminders import ReminderRecord, RemindersRepo
from app.repositories.users import UserRecord, UsersRepo
from app.services.history_service import HistoryService
from app.utils.timezones import fmt_local_time_for_user, parse_hhmm

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, scheduler: AsyncIOScheduler, reminders_repo: RemindersRepo, users_repo: UsersRepo, history_service: HistoryService):
        self.scheduler = scheduler
        self.reminders_repo = reminders_repo
        self.users_repo = users_repo
        self.history_service = history_service

    @staticmethod
    def once_job_id(reminder_id: int) -> str:
        return f"once_reminder_{reminder_id}"

    @staticmethod
    def interval_job_id(reminder_id: int) -> str:
        return f"interval_reminder_{reminder_id}"

    @staticmethod
    def recurring_job_id(reminder_id: int, user_id: int) -> str:
        return f"recurring_reminder_{reminder_id}_user_{user_id}"

    @staticmethod
    def pre_job_id(reminder_id: int, user_id: int | str) -> str:
        return f"pre_reminder_{reminder_id}_{user_id}"

    @staticmethod
    def snooze_job_id(reminder_id: int) -> str:
        return f"snooze_reminder_{reminder_id}"

    @staticmethod
    def _parse_working_days(raw: str | None) -> set[int]:
        if not raw:
            return {0, 1, 2, 3, 4, 5, 6}
        result = set()
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                result.add(int(part))
        return result or {0, 1, 2, 3, 4, 5, 6}

    @staticmethod
    def _in_quiet_hours(user: UserRecord, now_local: datetime) -> bool:
        if not user.quiet_hours_start or not user.quiet_hours_end:
            return False
        sh, sm = parse_hhmm(user.quiet_hours_start)
        eh, em = parse_hhmm(user.quiet_hours_end)
        now_m = now_local.hour * 60 + now_local.minute
        start_m = sh * 60 + sm
        end_m = eh * 60 + em
        if start_m == end_m:
            return False
        if start_m < end_m:
            return start_m <= now_m < end_m
        return now_m >= start_m or now_m < end_m

    async def _is_duplicate(self, reminder_id: int, user_id: int, *, pre: bool = False) -> bool:
        state = await self.reminders_repo.get_recipient_state(reminder_id, user_id)
        if not state:
            return False
        timestamp = state.last_pre_delivered_at if pre else state.last_delivered_at
        if not timestamp:
            return False
        try:
            dt = datetime.fromisoformat(timestamp)
        except Exception:
            return False
        return datetime.now(timezone.utc) - dt < timedelta(seconds=90)

    async def _can_deliver(self, reminder: ReminderRecord, user: UserRecord, *, pre: bool = False) -> tuple[bool, str | None]:
        # one-time reminders are always sent, even during quiet hours, to avoid losing absolute events
        if reminder.kind == "once" and not pre:
            return True, None
        now_local = datetime.now(ZoneInfo(user.timezone_name))
        if reminder.kind in ("daily", "weekly", "interval"):
            if now_local.weekday() not in self._parse_working_days(user.working_days):
                return False, "outside_working_days"
        if self._in_quiet_hours(user, now_local):
            return False, "quiet_hours"
        return True, None

    async def _deliver(self, bot: Bot, reminder: ReminderRecord, user_id: int, header: str, when_text: str | None = None, event_type: str = "sent") -> None:
        text = (
            f"⏰ <b>{header}</b>\n\n"
            f"ID: {reminder.id}\n"
            f"Категория: {reminder.category}\n"
            f"Приоритет: {reminder.priority}\n"
            f"Текст: {reminder.text}"
        )
        if when_text:
            text = text.replace(f"Текст: {reminder.text}", f"Когда: {when_text}\nТекст: {reminder.text}")
        await bot.send_message(user_id, text, reply_markup=reminder_actions_kb(reminder.id))
        await self.history_service.log(reminder.id, user_id, event_type)

    async def send_pre_reminder(self, bot: Bot, reminder_id: int, user_id: int | None = None) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.pre_remind_minutes <= 0:
            return
        recipients = [user_id] if user_id is not None else await self.reminders_repo.get_recipients(reminder_id)
        for uid in recipients:
            user = await self.users_repo.get_user(uid)
            if not user:
                continue
            if await self._is_duplicate(reminder_id, uid, pre=True):
                continue
            can_deliver, reason = await self._can_deliver(reminder, user, pre=True)
            if not can_deliver:
                await self.reminders_repo.mark_recipient_skipped(reminder_id, uid, reason or 'skipped')
                await self.history_service.log(reminder_id, uid, "skipped", {"stage": "pre", "reason": reason})
                continue
            try:
                await self._deliver(bot, reminder, uid, f"Скоро напоминание (за {reminder.pre_remind_minutes} мин)", None, event_type="pre_sent")
                await self.reminders_repo.mark_recipient_delivered(reminder_id, uid, pre=True)
            except Exception:
                logger.exception("Не удалось отправить предуведомление uid=%s reminder=%s", uid, reminder_id)

    async def send_once_reminder(self, bot: Bot, reminder_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.kind != "once" or reminder.scheduled_at_utc is None:
            return
        fired_at = datetime.now(timezone.utc).isoformat()
        await self.reminders_repo.set_last_fired_at(reminder_id, fired_at)
        recipients = await self.reminders_repo.get_recipients(reminder_id)
        dt_utc = datetime.fromisoformat(reminder.scheduled_at_utc)
        for user_id in recipients:
            user = await self.users_repo.get_user(user_id)
            if not user or await self._is_duplicate(reminder_id, user_id):
                continue
            try:
                await self._deliver(bot, reminder, user_id, "Напоминание", fmt_local_time_for_user(dt_utc, user.timezone_name))
                await self.reminders_repo.mark_recipient_delivered(reminder_id, user_id)
            except Exception:
                logger.exception("Не удалось отправить одноразовое напоминание user_id=%s reminder_id=%s", user_id, reminder_id)
        job = self.scheduler.get_job(self.once_job_id(reminder_id))
        if job:
            self.scheduler.remove_job(self.once_job_id(reminder_id))

    async def send_interval_reminder(self, bot: Bot, reminder_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.kind != "interval" or reminder.scheduled_at_utc is None:
            return
        fired_at = datetime.now(timezone.utc).isoformat()
        await self.reminders_repo.set_last_fired_at(reminder_id, fired_at)
        recipients = await self.reminders_repo.get_recipients(reminder_id)
        dt_utc = datetime.now(timezone.utc)
        for user_id in recipients:
            user = await self.users_repo.get_user(user_id)
            if not user or await self._is_duplicate(reminder_id, user_id):
                continue
            can_deliver, reason = await self._can_deliver(reminder, user)
            if not can_deliver:
                await self.reminders_repo.mark_recipient_skipped(reminder_id, user_id, reason or 'skipped')
                await self.history_service.log(reminder_id, user_id, "skipped", {"reason": reason})
                continue
            try:
                await self._deliver(bot, reminder, user_id, f"Интервальное напоминание ({reminder.interval_hours} ч)", fmt_local_time_for_user(dt_utc, user.timezone_name))
                await self.reminders_repo.mark_recipient_delivered(reminder_id, user_id)
            except Exception:
                logger.exception("Не удалось отправить интервальное напоминание user_id=%s reminder_id=%s", user_id, reminder_id)

    async def send_recurring_reminder(self, bot: Bot, reminder_id: int, user_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.kind not in ("daily", "weekly"):
            return
        user = await self.users_repo.get_user(user_id)
        if not user or await self._is_duplicate(reminder_id, user_id):
            return
        can_deliver, reason = await self._can_deliver(reminder, user)
        if not can_deliver:
            await self.reminders_repo.mark_recipient_skipped(reminder_id, user_id, reason or 'skipped')
            await self.history_service.log(reminder_id, user_id, "skipped", {"reason": reason})
            return
        fired_at = datetime.now(timezone.utc).isoformat()
        await self.reminders_repo.set_last_fired_at(reminder_id, fired_at)
        now_local = datetime.now(ZoneInfo(user.timezone_name)).strftime("%d.%m.%Y %H:%M")
        try:
            await self._deliver(bot, reminder, user_id, "Напоминание", now_local)
            await self.reminders_repo.mark_recipient_delivered(reminder_id, user_id)
        except Exception:
            logger.exception("Не удалось отправить повторяющееся напоминание user_id=%s reminder_id=%s", user_id, reminder_id)

    async def send_snoozed_reminder(self, bot: Bot, reminder_id: int) -> None:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or not reminder.snoozed_until_utc:
            return
        recipients = await self.reminders_repo.get_recipients(reminder_id)
        dt_utc = datetime.fromisoformat(reminder.snoozed_until_utc)
        for user_id in recipients:
            user = await self.users_repo.get_user(user_id)
            if not user or await self._is_duplicate(reminder_id, user_id):
                continue
            can_deliver, reason = await self._can_deliver(reminder, user)
            if not can_deliver:
                await self.reminders_repo.mark_recipient_skipped(reminder_id, user_id, reason or 'skipped')
                await self.history_service.log(reminder_id, user_id, "skipped", {"reason": reason, "stage": "snooze"})
                continue
            try:
                await self._deliver(bot, reminder, user_id, "Отложенное напоминание", fmt_local_time_for_user(dt_utc, user.timezone_name))
                await self.reminders_repo.mark_recipient_delivered(reminder_id, user_id)
            except Exception:
                logger.exception("Не удалось отправить snooze user_id=%s reminder_id=%s", user_id, reminder_id)
        await self.reminders_repo.set_snoozed_until(reminder_id, None)
        job = self.scheduler.get_job(self.snooze_job_id(reminder_id))
        if job:
            self.scheduler.remove_job(self.snooze_job_id(reminder_id))

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

    def schedule_interval_job(self, reminder: ReminderRecord, bot: Bot) -> None:
        if reminder.kind != "interval" or reminder.scheduled_at_utc is None or not reminder.interval_hours:
            return
        start = datetime.fromisoformat(reminder.scheduled_at_utc)
        self.scheduler.add_job(
            self.send_interval_reminder,
            trigger=IntervalTrigger(hours=reminder.interval_hours, start_date=start, timezone=timezone.utc),
            args=[bot, reminder.id],
            id=self.interval_job_id(reminder.id),
            replace_existing=True,
            misfire_grace_time=300,
        )

    def _calc_pre_time(self, reminder: ReminderRecord, tz_name: str) -> tuple[int, int, int | None] | None:
        if reminder.pre_remind_minutes <= 0:
            return None
        if reminder.local_time:
            hour, minute = parse_hhmm(reminder.local_time)
            total = hour * 60 + minute - reminder.pre_remind_minutes
            weekday = reminder.weekday
            while total < 0:
                total += 24 * 60
                if weekday is not None:
                    weekday = (weekday - 1) % 7
            return total // 60, total % 60, weekday
        return None

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

    def schedule_pre_jobs(self, reminder: ReminderRecord, bot: Bot, user_id: int | None = None, tz_name: str | None = None) -> None:
        if reminder.pre_remind_minutes <= 0:
            return
        if reminder.kind == "once" and reminder.scheduled_at_utc:
            run_at = datetime.fromisoformat(reminder.scheduled_at_utc) - timedelta(minutes=reminder.pre_remind_minutes)
            if run_at > datetime.now(timezone.utc):
                token = user_id if user_id is not None else "all"
                self.scheduler.add_job(
                    self.send_pre_reminder,
                    trigger=DateTrigger(run_date=run_at, timezone=timezone.utc),
                    args=[bot, reminder.id, user_id],
                    id=self.pre_job_id(reminder.id, token),
                    replace_existing=True,
                    misfire_grace_time=300,
                )
            return
        if reminder.kind == "interval" and reminder.scheduled_at_utc and reminder.interval_hours:
            start = datetime.fromisoformat(reminder.scheduled_at_utc) - timedelta(minutes=reminder.pre_remind_minutes)
            self.scheduler.add_job(
                self.send_pre_reminder,
                trigger=IntervalTrigger(hours=reminder.interval_hours, start_date=start, timezone=timezone.utc),
                args=[bot, reminder.id, user_id],
                id=self.pre_job_id(reminder.id, user_id if user_id is not None else 'all'),
                replace_existing=True,
                misfire_grace_time=300,
            )
            return
        if reminder.kind in ("daily", "weekly") and user_id is not None and tz_name is not None:
            calc = self._calc_pre_time(reminder, tz_name)
            if not calc:
                return
            hour, minute, weekday = calc
            if reminder.kind == "daily":
                trigger = CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo(tz_name))
            else:
                trigger = CronTrigger(day_of_week=weekday, hour=hour, minute=minute, timezone=ZoneInfo(tz_name))
            self.scheduler.add_job(
                self.send_pre_reminder,
                trigger=trigger,
                args=[bot, reminder.id, user_id],
                id=self.pre_job_id(reminder.id, user_id),
                replace_existing=True,
                misfire_grace_time=300,
            )

    async def snooze_reminder(self, reminder_id: int, mode: str, bot: Bot) -> datetime:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        now = datetime.now(timezone.utc)
        if mode == "5m":
            run_at = now + timedelta(minutes=5)
        elif mode == "15m":
            run_at = now + timedelta(minutes=15)
        elif mode == "1h":
            run_at = now + timedelta(hours=1)
        else:
            tomorrow_utc = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            run_at = tomorrow_utc
        await self.reminders_repo.set_snoozed_until(reminder_id, run_at.isoformat())
        self.scheduler.add_job(
            self.send_snoozed_reminder,
            trigger=DateTrigger(run_date=run_at, timezone=timezone.utc),
            args=[bot, reminder_id],
            id=self.snooze_job_id(reminder_id),
            replace_existing=True,
            misfire_grace_time=300,
        )
        return run_at

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
            pre = self.scheduler.get_job(self.pre_job_id(reminder.id, user_id))
            if pre:
                self.scheduler.remove_job(self.pre_job_id(reminder.id, user_id))
            self.schedule_recurring_job_for_user(reminder, user_id, user.timezone_name, bot)
            self.schedule_pre_jobs(reminder, bot, user_id, user.timezone_name)

    def remove_all_jobs_for_reminder(self, reminder: ReminderRecord, scheduler: AsyncIOScheduler) -> None:
        ids = [self.once_job_id(reminder.id), self.interval_job_id(reminder.id), self.pre_job_id(reminder.id, 'all'), self.snooze_job_id(reminder.id)]
        for job_id in ids:
            job = scheduler.get_job(job_id)
            if job:
                scheduler.remove_job(job_id)

    async def restore_jobs(self, bot: Bot) -> None:
        now_utc = datetime.now(timezone.utc)
        once_reminders = await self.reminders_repo.get_active_once_reminders()
        for reminder in once_reminders:
            if reminder.scheduled_at_utc is None:
                continue
            dt_utc = datetime.fromisoformat(reminder.scheduled_at_utc)
            if dt_utc <= now_utc:
                await self.reminders_repo.mark_status(reminder.id, 'missed')
                continue
            self.schedule_once_job(reminder, bot)
            self.schedule_pre_jobs(reminder, bot)
            if reminder.snoozed_until_utc:
                self.scheduler.add_job(
                    self.send_snoozed_reminder,
                    trigger=DateTrigger(run_date=datetime.fromisoformat(reminder.snoozed_until_utc), timezone=timezone.utc),
                    args=[bot, reminder.id],
                    id=self.snooze_job_id(reminder.id),
                    replace_existing=True,
                    misfire_grace_time=300,
                )
        recurring_reminders = await self.reminders_repo.get_active_recurring_reminders()
        for reminder in recurring_reminders:
            if reminder.kind == 'interval':
                self.schedule_interval_job(reminder, bot)
                self.schedule_pre_jobs(reminder, bot)
                continue
            recipients = await self.reminders_repo.get_recipients(reminder.id)
            for user_id in recipients:
                user = await self.users_repo.get_user(user_id)
                if not user:
                    continue
                self.schedule_recurring_job_for_user(reminder, user_id, user.timezone_name, bot)
                self.schedule_pre_jobs(reminder, bot, user_id, user.timezone_name)
