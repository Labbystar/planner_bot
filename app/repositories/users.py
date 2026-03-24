from datetime import datetime, timezone
from dataclasses import dataclass

import aiosqlite


@dataclass(slots=True)
class UserRecord:
    user_id: int
    username: str | None
    full_name: str
    timezone_name: str


class UsersRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def upsert_user(self, user_id: int, username: str | None, full_name: str, timezone_name: str) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, timezone_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    updated_at = excluded.updated_at
            """, (user_id, username, full_name, timezone_name, now_utc, now_utc))
            await db.commit()

    async def get_user(self, user_id: int) -> UserRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT user_id, username, full_name, timezone_name FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return UserRecord(*row) if row else None

    async def user_exists(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return (await cur.fetchone()) is not None

    async def set_user_timezone(self, user_id: int, timezone_name: str) -> bool:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE users SET timezone_name = ?, updated_at = ? WHERE user_id = ?",
                (timezone_name, now_utc, user_id),
            )
            await db.commit()
            return cur.rowcount > 0
