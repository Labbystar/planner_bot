from datetime import datetime, timezone

from app.repositories.reminders import RemindersRepo
from app.repositories.shares import ShareRecord, SharesRepo
from app.repositories.users import UsersRepo
from app.services.scheduler_service import SchedulerService
from app.utils.tokens import generate_share_token


class SharingService:
    def __init__(self, bot_username: str, shares_repo: SharesRepo, reminders_repo: RemindersRepo, users_repo: UsersRepo, scheduler_service: SchedulerService):
        self.bot_username = bot_username
        self.shares_repo = shares_repo
        self.reminders_repo = reminders_repo
        self.users_repo = users_repo
        self.scheduler_service = scheduler_service

    async def create_share_link(self, owner_user_id: int, reminder_id: int, mode: str) -> str:
        reminder = await self.reminders_repo.get_reminder(reminder_id)
        if not reminder or not reminder.is_active or reminder.creator_id != owner_user_id:
            raise ValueError("Напоминание не найдено или не принадлежит пользователю")
        token = generate_share_token()
        await self.shares_repo.create_share(token, reminder_id, owner_user_id, mode)
        if not self.bot_username:
            return f"share_{token}"
        return f"https://t.me/{self.bot_username}?start=share_{token}"

    async def get_share_preview(self, token: str) -> tuple[ShareRecord, str]:
        share = await self.shares_repo.get_share_by_token(token)
        if not share or not share.is_active:
            raise ValueError("Ссылка недействительна")
        if share.expires_at and datetime.fromisoformat(share.expires_at) <= datetime.now(timezone.utc):
            raise ValueError("Срок действия ссылки истек")
        reminder = await self.reminders_repo.get_reminder(share.reminder_id)
        if not reminder or not reminder.is_active:
            raise ValueError("Исходное напоминание недоступно")

        if reminder.kind == "once":
            description = f"Одноразовое напоминание\nUTC: {reminder.scheduled_at_utc}"
        elif reminder.kind == "daily":
            description = f"Ежедневное напоминание\nВремя: {reminder.local_time}"
        elif reminder.kind == "weekly":
            description = f"Еженедельное напоминание\nДень недели: {reminder.weekday}\nВремя: {reminder.local_time}"
        else:
            description = f"Интервальное напоминание\nКаждые {reminder.interval_hours} часов\nСтарт UTC: {reminder.scheduled_at_utc}"

        pre_text = "без предуведомления" if reminder.pre_remind_minutes == 0 else f"предупреждение за {reminder.pre_remind_minutes} мин"
        preview = (
            "Вам поделились напоминанием:\n\n"
            f"ID источника: {reminder.id}\n"
            f"Режим шаринга: {'копия' if share.share_mode == 'copy' else 'подписка на исходное'}\n"
            f"{description}\n"
            f"{pre_text}\n"
            f"Текст: {reminder.text}"
        )
        return share, preview

    async def accept_share(self, token: str, accepted_by_user_id: int, bot) -> str:
        share = await self.shares_repo.get_share_by_token(token)
        if not share or not share.is_active:
            raise ValueError("Ссылка недействительна")
        if share.expires_at and datetime.fromisoformat(share.expires_at) <= datetime.now(timezone.utc):
            raise ValueError("Срок действия ссылки истек")
        if accepted_by_user_id == share.owner_user_id:
            raise ValueError("Нельзя принимать свою собственную ссылку")
        if not await self.users_repo.user_exists(accepted_by_user_id):
            raise ValueError("Сначала запусти бота через /start")
        if await self.shares_repo.is_already_accepted(share.id, accepted_by_user_id):
            raise ValueError("Эта ссылка уже была принята")

        reminder = await self.reminders_repo.get_reminder(share.reminder_id)
        if not reminder or not reminder.is_active:
            raise ValueError("Исходное напоминание недоступно")

        if share.share_mode == "recipient":
            await self.reminders_repo.add_recipient(reminder.id, accepted_by_user_id)
            if reminder.kind in ("daily", "weekly"):
                user = await self.users_repo.get_user(accepted_by_user_id)
                if user:
                    self.scheduler_service.schedule_recurring_job_for_user(reminder, accepted_by_user_id, user.timezone_name, bot)
                    self.scheduler_service.schedule_pre_jobs(reminder, bot, accepted_by_user_id, user.timezone_name)
            await self.shares_repo.mark_accepted(share.id, accepted_by_user_id)
            return f"Готово. Ты подписан на напоминание ID {reminder.id}."

        recipient_user = await self.users_repo.get_user(accepted_by_user_id)
        if not recipient_user:
            raise ValueError("Пользователь не найден")

        if reminder.kind == "once":
            new_id = await self.reminders_repo.add_once_reminder(
                creator_id=accepted_by_user_id,
                text=reminder.text,
                scheduled_at_utc=reminder.scheduled_at_utc,
                creator_timezone_at_creation=recipient_user.timezone_name,
                recipients=[accepted_by_user_id],
                category=reminder.category,
                priority=reminder.priority,
                pre_remind_minutes=reminder.pre_remind_minutes,
            )
            new_reminder = await self.reminders_repo.get_reminder(new_id)
            if new_reminder:
                self.scheduler_service.schedule_once_job(new_reminder, bot)
                self.scheduler_service.schedule_pre_jobs(new_reminder, bot)
        elif reminder.kind == "daily":
            new_id = await self.reminders_repo.add_daily_reminder(
                creator_id=accepted_by_user_id,
                text=reminder.text,
                local_time=reminder.local_time,
                creator_timezone_at_creation=recipient_user.timezone_name,
                recipients=[accepted_by_user_id],
                category=reminder.category,
                priority=reminder.priority,
                pre_remind_minutes=reminder.pre_remind_minutes,
            )
            new_reminder = await self.reminders_repo.get_reminder(new_id)
            if new_reminder:
                self.scheduler_service.schedule_recurring_job_for_user(new_reminder, accepted_by_user_id, recipient_user.timezone_name, bot)
                self.scheduler_service.schedule_pre_jobs(new_reminder, bot, accepted_by_user_id, recipient_user.timezone_name)
        elif reminder.kind == "weekly":
            new_id = await self.reminders_repo.add_weekly_reminder(
                creator_id=accepted_by_user_id,
                text=reminder.text,
                weekday=reminder.weekday,
                local_time=reminder.local_time,
                creator_timezone_at_creation=recipient_user.timezone_name,
                recipients=[accepted_by_user_id],
                category=reminder.category,
                priority=reminder.priority,
                pre_remind_minutes=reminder.pre_remind_minutes,
            )
            new_reminder = await self.reminders_repo.get_reminder(new_id)
            if new_reminder:
                self.scheduler_service.schedule_recurring_job_for_user(new_reminder, accepted_by_user_id, recipient_user.timezone_name, bot)
                self.scheduler_service.schedule_pre_jobs(new_reminder, bot, accepted_by_user_id, recipient_user.timezone_name)
        else:
            new_id = await self.reminders_repo.add_interval_reminder(
                creator_id=accepted_by_user_id,
                text=reminder.text,
                interval_hours=reminder.interval_hours,
                start_at_utc=reminder.scheduled_at_utc,
                creator_timezone_at_creation=recipient_user.timezone_name,
                recipients=[accepted_by_user_id],
                category=reminder.category,
                priority=reminder.priority,
                pre_remind_minutes=reminder.pre_remind_minutes,
            )
            new_reminder = await self.reminders_repo.get_reminder(new_id)
            if new_reminder:
                self.scheduler_service.schedule_interval_job(new_reminder, bot)
                self.scheduler_service.schedule_pre_jobs(new_reminder, bot)

        await self.shares_repo.mark_accepted(share.id, accepted_by_user_id)
        return "Готово. Напоминание добавлено тебе как отдельная копия."
