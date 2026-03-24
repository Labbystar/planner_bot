from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite

from app.config import DB_PATH
from app.utils.time import utc_iso


async def create_reminder(owner_user_id: int, text: str, scheduled_at_utc: str, category: str, priority: str, note: str | None = None) -> int:
    now = utc_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO reminders (owner_user_id, text, note, category, priority, scheduled_at_utc, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (owner_user_id, text.strip(), note, category, priority, scheduled_at_utc, now, now),
        )
        await db.commit()
        return cur.lastrowid


async def get_reminder(reminder_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_active_reminders(owner_user_id: int, page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) FROM reminders WHERE owner_user_id = ? AND status IN ('active','snoozed')", (owner_user_id,))
        total = (await cur.fetchone())[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur = await db.execute(
            "SELECT * FROM reminders WHERE owner_user_id = ? AND status IN ('active','snoozed') ORDER BY scheduled_at_utc ASC LIMIT ? OFFSET ?",
            (owner_user_id, per_page, offset),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows], total_pages


async def mark_done(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
            (utc_iso(), utc_iso(), reminder_id),
        )
        await db.commit()


async def snooze(reminder_id: int, minutes: int) -> None:
    reminder = await get_reminder(reminder_id)
    if not reminder:
        return
    current = datetime.fromisoformat(reminder["scheduled_at_utc"])
    next_dt = max(current, datetime.now(timezone.utc)) + timedelta(minutes=minutes)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET status = 'snoozed', scheduled_at_utc = ?, updated_at = ? WHERE id = ?",
            (next_dt.isoformat(), utc_iso(), reminder_id),
        )
        await db.commit()


async def delete_reminder(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()
