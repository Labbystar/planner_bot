from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite

from app.config import DB_PATH
from app.utils.time import utc_iso

BASE_SCOPE = "(owner_user_id = ? OR assigned_user_id = ?)"


async def create_reminder(owner_user_id: int, assigned_user_id: int, text: str, scheduled_at_utc: str, category: str, priority: str, note: str | None = None) -> int:
    now = utc_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO reminders (owner_user_id, assigned_user_id, text, note, category, priority, scheduled_at_utc, status, created_at, updated_at, assignee_can_edit)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 0)
            """,
            (owner_user_id, assigned_user_id, text.strip(), note, category, priority, scheduled_at_utc, now, now),
        )
        await db.commit()
        return cur.lastrowid


async def get_reminder(reminder_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def toggle_assignee_edit(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(assignee_can_edit,0) FROM reminders WHERE id = ?", (reminder_id,))
        row = await cur.fetchone()
        current = row[0] if row else 0
        await db.execute("UPDATE reminders SET assignee_can_edit = ?, updated_at = ? WHERE id = ?", (0 if current else 1, utc_iso(), reminder_id))
        await db.commit()


async def list_active_reminders(user_id: int, page: int = 1, per_page: int = 5, category: str | None = None, priority: str | None = None) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    where = [BASE_SCOPE, "status IN ('active','snoozed','sent','done')"]
    params: list[object] = [user_id, user_id]
    if category:
        where.append("category = ?")
        params.append(category)
    if priority:
        where.append("priority = ?")
        params.append(priority)
    where_sql = " AND ".join(where)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"SELECT COUNT(*) FROM reminders WHERE {where_sql}", tuple(params))
        total = (await cur.fetchone())[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur = await db.execute(
            f"SELECT * FROM reminders WHERE {where_sql} ORDER BY scheduled_at_utc ASC LIMIT ? OFFSET ?",
            tuple(params + [per_page, offset]),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows], total_pages


async def list_assigned_to_me(user_id: int, page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    where = "assigned_user_id = ? AND owner_user_id != ? AND status IN ('active','snoozed','sent')"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"SELECT COUNT(*) FROM reminders WHERE {where}", (user_id, user_id))
        total = (await cur.fetchone())[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur = await db.execute(f"SELECT * FROM reminders WHERE {where} ORDER BY scheduled_at_utc ASC LIMIT ? OFFSET ?", (user_id, user_id, per_page, offset))
        return [dict(r) for r in await cur.fetchall()], total_pages


async def list_created_by_me(user_id: int, page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    where = "owner_user_id = ? AND assigned_user_id != ?"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"SELECT COUNT(*) FROM reminders WHERE {where}", (user_id, user_id))
        total = (await cur.fetchone())[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur = await db.execute(f"SELECT * FROM reminders WHERE {where} ORDER BY scheduled_at_utc ASC LIMIT ? OFFSET ?", (user_id, user_id, per_page, offset))
        return [dict(r) for r in await cur.fetchall()], total_pages


async def list_by_time_window(user_id: int, start_utc: str, end_utc: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"""SELECT * FROM reminders WHERE {BASE_SCOPE} AND status IN ('active','snoozed','sent') AND scheduled_at_utc >= ? AND scheduled_at_utc < ? ORDER BY scheduled_at_utc ASC""",
            (user_id, user_id, start_utc, end_utc),
        )
        return [dict(r) for r in await cur.fetchall()]


async def list_overdue(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT * FROM reminders WHERE {BASE_SCOPE} AND status = 'sent' AND scheduled_at_utc < ? ORDER BY scheduled_at_utc DESC",
            (user_id, user_id, now),
        )
        return [dict(r) for r in await cur.fetchall()]


async def search_reminders(user_id: int, query: str, limit: int = 10) -> list[dict]:
    pattern = f"%{query.strip()}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT * FROM reminders WHERE {BASE_SCOPE} AND (text LIKE ? OR COALESCE(note, '') LIKE ?) ORDER BY scheduled_at_utc DESC LIMIT ?",
            (user_id, user_id, pattern, pattern, limit),
        )
        return [dict(r) for r in await cur.fetchall()]


async def mark_done(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?", (utc_iso(), utc_iso(), reminder_id))
        await db.commit()


async def mark_sent(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET status = 'sent', updated_at = ? WHERE id = ?", (utc_iso(), reminder_id))
        await db.commit()


async def snooze(reminder_id: int, minutes: int) -> None:
    reminder = await get_reminder(reminder_id)
    if not reminder:
        return
    current = datetime.fromisoformat(reminder["scheduled_at_utc"])
    next_dt = max(current, datetime.now(timezone.utc)) + timedelta(minutes=minutes)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET status = 'snoozed', scheduled_at_utc = ?, updated_at = ? WHERE id = ?", (next_dt.isoformat(), utc_iso(), reminder_id))
        await db.commit()


async def update_text(reminder_id: int, new_text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET text = ?, updated_at = ? WHERE id = ?", (new_text.strip(), utc_iso(), reminder_id))
        await db.commit()


async def update_when(reminder_id: int, scheduled_at_utc: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET scheduled_at_utc = ?, status = 'active', updated_at = ? WHERE id = ?", (scheduled_at_utc, utc_iso(), reminder_id))
        await db.commit()



async def update_assignee_comment(reminder_id: int, comment: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET assignee_comment = ?, updated_at = ? WHERE id = ?",
            ((comment or '').strip() or None, utc_iso(), reminder_id),
        )
        await db.commit()

async def update_category(reminder_id: int, category: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET category = ?, updated_at = ? WHERE id = ?", (category, utc_iso(), reminder_id))
        await db.commit()


async def update_priority(reminder_id: int, priority: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET priority = ?, updated_at = ? WHERE id = ?", (priority, utc_iso(), reminder_id))
        await db.commit()


async def delete_reminder(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()


async def stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(f"SELECT COUNT(*) FROM reminders WHERE {BASE_SCOPE}", (user_id, user_id))
        total = (await cur.fetchone())[0]
        cur = await db.execute(f"SELECT status, COUNT(*) FROM reminders WHERE {BASE_SCOPE} GROUP BY status", (user_id, user_id))
        by_status = {row[0]: row[1] for row in await cur.fetchall()}
        cur = await db.execute(f"SELECT category, COUNT(*) FROM reminders WHERE {BASE_SCOPE} GROUP BY category", (user_id, user_id))
        by_category = {row[0]: row[1] for row in await cur.fetchall()}
        cur = await db.execute(f"SELECT priority, COUNT(*) FROM reminders WHERE {BASE_SCOPE} GROUP BY priority", (user_id, user_id))
        by_priority = {row[0]: row[1] for row in await cur.fetchall()}
        return {"total": total, "by_status": by_status, "by_category": by_category, "by_priority": by_priority}


async def list_month_counts(user_id: int, start_utc: str, end_utc: str) -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"SELECT substr(scheduled_at_utc, 1, 10) as day_key, COUNT(*) FROM reminders WHERE {BASE_SCOPE} AND scheduled_at_utc >= ? AND scheduled_at_utc < ? AND status IN ('active','snoozed','sent') GROUP BY day_key",
            (user_id, user_id, start_utc, end_utc),
        )
        return {row[0]: row[1] for row in await cur.fetchall()}


async def list_all_reminders(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(f"SELECT * FROM reminders WHERE {BASE_SCOPE} ORDER BY scheduled_at_utc ASC", (user_id, user_id))
        return [dict(r) for r in await cur.fetchall()]
