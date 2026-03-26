from __future__ import annotations

from datetime import datetime, time, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.keyboards.reminders import assignee_actions
from app.services.notifications import get_due_notifications, mark_notification_sent
from app.services.reminders import get_reminder, list_by_time_window, mark_sent, set_overdue
from app.services.users import get_user, list_users, mark_digest_sent
from app.utils.formatting import compact_notification, overdue_notification
from app.utils.time import to_local

scheduler = AsyncIOScheduler(timezone='UTC')


def _is_quiet(local_dt: datetime, user: dict) -> bool:
    if not user.get('quiet_hours_enabled'):
        return False
    start = time.fromisoformat(user.get('quiet_start') or '23:00')
    end = time.fromisoformat(user.get('quiet_end') or '08:00')
    current = local_dt.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


async def _send_smart_notification(bot: Bot, n: dict, reminder: dict) -> None:
    user = await get_user(n["user_id"])
    if not user:
        await mark_notification_sent(n["id"])
        return

    n_type = n["notification_type"]
    status = reminder.get("status")
    # Skip if task already closed/cancelled
    if status in ("confirmed", "cancelled", "pending_confirmation"):
        await mark_notification_sent(n["id"])
        return

    # Acceptance reminders only while task has not been accepted
    if n_type.startswith("not_accepted_") and status != "active":
        await mark_notification_sent(n["id"])
        return

    when_local = to_local(datetime.fromisoformat(reminder["scheduled_at_utc"]), user["timezone_name"])
    title = reminder["text"]

    if n_type == "pre_deadline_1h":
        text = (
            "🔔 Через 1 час срок по задаче\n\n"
            f"📌 {title}\n"
            f"📅 {when_local.strftime('%d.%m.%Y %H:%M')}"
        )
    elif n_type == "deadline_now":
        text = (
            "⏰ Срок по задаче наступил\n\n"
            f"📌 {title}\n"
            f"📅 {when_local.strftime('%d.%m.%Y %H:%M')}"
        )
    elif n_type == "post_deadline_30m":
        text = (
            "⚠️ Задача всё ещё не закрыта\n\n"
            f"📌 {title}\n"
            "Просрочка: 30 минут"
        )
    elif n_type == "not_accepted_10m":
        text = (
            "🔔 Ты ещё не подтвердил задачу\n\n"
            f"📌 {title}"
        )
    elif n_type == "not_accepted_30m":
        text = (
            "⚠️ Задача всё ещё не принята\n\n"
            f"📌 {title}"
        )
    else:
        await mark_notification_sent(n["id"])
        return

    try:
        await bot.send_message(n["user_id"], text)
    finally:
        await mark_notification_sent(n["id"])


async def _process_daily_digests(bot: Bot) -> None:
    users = await list_users()
    now_utc = datetime.now(timezone.utc)

    for user in users:
        if not user.get("digest_enabled", 1):
            continue
        tz_name = user.get("timezone_name") or "Asia/Novosibirsk"
        now_local = to_local(now_utc, tz_name)
        digest_time = user.get("digest_time_local") or "09:00"
        try:
            digest_hour, digest_minute = map(int, digest_time.split(":"))
        except Exception:
            digest_hour, digest_minute = 9, 0

        if (now_local.hour, now_local.minute) < (digest_hour, digest_minute):
            continue

        local_date = now_local.strftime("%Y-%m-%d")
        if user.get("last_digest_date_local") == local_date:
            continue

        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_utc = start_local.astimezone(timezone.utc).isoformat()
        end_utc = end_local.astimezone(timezone.utc).isoformat()

        tasks_today = await list_by_time_window(user["user_id"], start_utc, end_utc)
        tasks_today = [t for t in tasks_today if t.get("assigned_user_id", t.get("owner_user_id")) == user["user_id"] and t.get("status") != "cancelled"]
        urgent = len([t for t in tasks_today if t.get("priority") == "high"])
        overdue = len([t for t in tasks_today if t.get("status") == "overdue"])

        text = (
            "📅 Сегодня у тебя:\n"
            f"• {len(tasks_today)} задач\n"
            f"• {urgent} срочных"
        )
        if overdue:
            text += f"\n• {overdue} просроченных"

        try:
            await bot.send_message(user["user_id"], text)
        finally:
            await mark_digest_sent(user["user_id"], local_date)


async def tick(bot: Bot) -> None:
    now = datetime.now(timezone.utc)

    # Base notifications around deadline / overdue state changes
    import aiosqlite
    from app.config import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT * FROM reminders WHERE status IN ('active', 'snoozed') AND scheduled_at_utc <= ?",
            (now.isoformat(),),
        )
        rows = await cur.fetchall()
        for row in rows:
            reminder = dict(row)
            user_id = reminder.get('assigned_user_id') or reminder.get('owner_user_id')
            user = await get_user(user_id)
            if not user:
                continue
            local_when = to_local(datetime.fromisoformat(reminder['scheduled_at_utc']), user['timezone_name'])
            if _is_quiet(local_when, user):
                continue
            try:
                await bot.send_message(
                    user_id,
                    compact_notification(reminder['text'], local_when, reminder['priority'], reminder['category'], reminder.get('note')),
                    reply_markup=assignee_actions(reminder['id']),
                )
                await mark_sent(reminder['id'])
            except Exception:
                pass

        cur = await db.execute(
            "SELECT * FROM reminders WHERE status IN ('in_progress', 'active', 'snoozed') AND scheduled_at_utc < ? AND overdue_notified_at IS NULL",
            (now.isoformat(),),
        )
        overdue_rows = await cur.fetchall()
        for row in overdue_rows:
            reminder = dict(row)
            await set_overdue(reminder['id'])
            reminder = await get_reminder(reminder['id'])
            assignee_id = reminder.get('assigned_user_id') or reminder.get('owner_user_id')
            owner_id = reminder.get('owner_user_id')
            if assignee_id:
                try:
                    await bot.send_message(assignee_id, overdue_notification(reminder, 'assignee'), parse_mode='HTML')
                except Exception:
                    pass
            if owner_id and owner_id != assignee_id:
                try:
                    await bot.send_message(owner_id, overdue_notification(reminder, 'owner'), parse_mode='HTML')
                except Exception:
                    pass
        await db.commit()

    # Smart notifications
    due = await get_due_notifications(now.isoformat())
    for n in due:
        reminder = await get_reminder(n["reminder_id"])
        if not reminder:
            await mark_notification_sent(n["id"])
            continue
        await _send_smart_notification(bot, n, reminder)

    # Daily digest
    await _process_daily_digests(bot)


def start_scheduler(bot: Bot) -> None:
    scheduler.add_job(tick, IntervalTrigger(minutes=1), args=[bot], id='tick', replace_existing=True)
    scheduler.start()
