from __future__ import annotations

import aiosqlite
from app.config import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            timezone_name TEXT NOT NULL,
            quiet_hours_enabled INTEGER NOT NULL DEFAULT 0,
            quiet_start TEXT,
            quiet_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            note TEXT,
            category TEXT NOT NULL DEFAULT 'work',
            priority TEXT NOT NULL DEFAULT 'medium',
            scheduled_at_utc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
        )
        """)
        await db.commit()
