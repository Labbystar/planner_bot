from __future__ import annotations

import aiosqlite
from app.config import DB_PATH, DEFAULT_TIMEZONE
from app.utils.time import utc_iso, validate_timezone


async def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    now = utc_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT timezone_name FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        tz = row[0] if row else DEFAULT_TIMEZONE
        validate_timezone(tz)
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, timezone_name, quiet_hours_enabled, quiet_start, quiet_end, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, NULL, NULL, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, is_active=1, updated_at=excluded.updated_at
            """,
            (user_id, username, full_name, tz, now, now),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_users(exclude_user_id: int | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if exclude_user_id is None:
            cur = await db.execute("SELECT user_id, username, full_name FROM users WHERE is_active = 1 ORDER BY COALESCE(username, full_name)")
        else:
            cur = await db.execute(
                "SELECT user_id, username, full_name FROM users WHERE is_active = 1 AND user_id != ? ORDER BY COALESCE(username, full_name)",
                (exclude_user_id,),
            )
        return [dict(r) for r in await cur.fetchall()]


async def set_timezone(user_id: int, timezone_name: str) -> None:
    validate_timezone(timezone_name)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET timezone_name = ?, updated_at = ? WHERE user_id = ?", (timezone_name, utc_iso(), user_id))
        await db.commit()


async def toggle_quiet_hours(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT quiet_hours_enabled FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        enabled = 0 if row and row[0] else 1
        await db.execute(
            "UPDATE users SET quiet_hours_enabled = ?, quiet_start = '23:00', quiet_end = '08:00', updated_at = ? WHERE user_id = ?",
            (enabled, utc_iso(), user_id),
        )
        await db.commit()
    return await get_user(user_id)


async def soft_delete_user(user_id: int) -> None:
    now = utc_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        # deactivate profile and hide user from all selectors
        await db.execute(
            "UPDATE users SET is_active = 0, updated_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        # tasks created by this user are cancelled
        await db.execute(
            "UPDATE reminders SET status = 'cancelled', updated_at = ? WHERE owner_user_id = ?",
            (now, user_id),
        )
        # tasks delegated to this user but created by others go back to owners
        await db.execute(
            "UPDATE reminders SET assigned_user_id = owner_user_id, updated_at = ? WHERE assigned_user_id = ? AND owner_user_id != ?",
            (now, user_id, user_id),
        )
        await db.commit()
