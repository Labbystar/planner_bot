from __future__ import annotations

import aiosqlite
from app.config import DB_PATH


async def _add_column_if_missing(db: aiosqlite.Connection, table: str, name: str, ddl: str) -> None:
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in await cur.fetchall()]
    if name not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


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
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            assigned_user_id INTEGER,
            text TEXT NOT NULL,
            note TEXT,
            category TEXT NOT NULL DEFAULT 'work',
            priority TEXT NOT NULL DEFAULT 'medium',
            scheduled_at_utc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
            FOREIGN KEY(assigned_user_id) REFERENCES users(user_id)
        )
        """)
        await _add_column_if_missing(db, 'reminders', 'assigned_user_id', 'assigned_user_id INTEGER')
        await _add_column_if_missing(db, 'reminders', 'note', 'note TEXT')
        await db.execute("UPDATE reminders SET assigned_user_id = owner_user_id WHERE assigned_user_id IS NULL")
        await _add_column_if_missing(db, 'users', 'is_active', 'is_active INTEGER NOT NULL DEFAULT 1')
        await db.commit()
