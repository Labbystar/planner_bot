from __future__ import annotations

from datetime import datetime, time, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.keyboards.reminders import reminder_actions
from app.services.users import get_user
from app.utils.formatting import compact_notification
from app.utils.time import to_local

scheduler = AsyncIOScheduler(timezone="UTC")


def _is_quiet(local_dt: datetime, user: dict) -> bool:
    if not user.get("quiet_hours_enabled"):
        return False
    start = time.fromisoformat(user.get("quiet_start") or "23:00")
    end = time.fromisoformat(user.get("quiet_end") or "08:00")
    current = local_dt.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


async def tick(bot: Bot) -> None:
    now = datetime.now(timezone.utc)

    import aiosqlite
    from app.config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM reminders WHERE status IN ('active','snoozed') AND scheduled_at_utc <= ?", (now.isoformat(),))
        rows = await cur.fetchall()
        for row in rows:
            reminder = dict(row)
            recipient_id = reminder.get("assigned_user_id") or reminder["owner_user_id"]
            user = await get_user(recipient_id)
            if not user:
                continue
            local_dt = to_local(datetime.fromisoformat(reminder["scheduled_at_utc"]), user["timezone_name"])
            if _is_quiet(local_dt, user):
                continue
            text = compact_notification(reminder["text"], local_dt, reminder["priority"], reminder["category"], reminder.get("note"))
            await bot.send_message(user["user_id"], text, reply_markup=reminder_actions(reminder["id"]))
            await db.execute("UPDATE reminders SET status = 'sent', updated_at = ? WHERE id = ?", (now.isoformat(), reminder['id']))
        await db.commit()


def start_scheduler(bot: Bot) -> None:
    scheduler.add_job(tick, IntervalTrigger(minutes=1), args=[bot], id="tick", replace_existing=True)
    scheduler.start()
