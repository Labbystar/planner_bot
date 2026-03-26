from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite

from app.config import DB_PATH
from app.utils.time import utc_iso


async def create_notification(reminder_id: int, user_id: int, notification_type: str, scheduled_at_utc: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO reminder_notifications
            (reminder_id, user_id, notification_type, scheduled_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (reminder_id, user_id, notification_type, scheduled_at_utc),
        )
        await db.commit()


async def clear_notifications_for_reminder(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminder_notifications WHERE reminder_id = ?", (reminder_id,))
        await db.commit()


async def get_due_notifications(now_utc: str | None = None) -> list[dict]:
    now_utc = now_utc or utc_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM reminder_notifications
            WHERE sent_at_utc IS NULL AND scheduled_at_utc <= ?
            ORDER BY scheduled_at_utc ASC, id ASC
            """,
            (now_utc,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def mark_notification_sent(notification_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminder_notifications SET sent_at_utc = ? WHERE id = ?",
            (utc_iso(), notification_id),
        )
        await db.commit()


def build_notification_schedule(reminder: dict) -> list[tuple[str, str, int]]:
    """Return (type, when_utc_iso, user_id) rows for a reminder."""
    rows: list[tuple[str, str, int]] = []
    assigned_user_id = reminder.get("assigned_user_id") or reminder.get("owner_user_id")
    if not assigned_user_id or not reminder.get("scheduled_at_utc"):
        return rows

    try:
        dt = datetime.fromisoformat(reminder["scheduled_at_utc"])
    except Exception:
        return rows

    now = datetime.now(timezone.utc)
    schedule = [
        ("pre_deadline_1h", dt - timedelta(hours=1)),
        ("deadline_now", dt),
        ("post_deadline_30m", dt + timedelta(minutes=30)),
    ]
    for n_type, when_dt in schedule:
        if when_dt > now:
            rows.append((n_type, when_dt.isoformat(), int(assigned_user_id)))

    # acceptance reminders only if delegated to another person
    owner_id = reminder.get("owner_user_id")
    if assigned_user_id != owner_id:
        rows.append(("not_accepted_10m", (now + timedelta(minutes=10)).isoformat(), int(assigned_user_id)))
        rows.append(("not_accepted_30m", (now + timedelta(minutes=30)).isoformat(), int(assigned_user_id)))

    return rows


async def sync_notifications_for_reminder(reminder: dict) -> None:
    await clear_notifications_for_reminder(int(reminder["id"]))
    for n_type, when_utc, user_id in build_notification_schedule(reminder):
        await create_notification(int(reminder["id"]), user_id, n_type, when_utc)
