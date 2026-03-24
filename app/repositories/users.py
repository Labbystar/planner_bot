from datetime import datetime, timezone
from dataclasses import dataclass

import aiosqlite


@dataclass(slots=True)
class UserRecord:
    user_id: int
    username: str | None
    full_name: str
    timezone_name: str
    role: str
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    working_days: str


class UsersRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def upsert_user(self, user_id: int, username: str | None, full_name: str, timezone_name: str) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            total = (await cur.fetchone())[0]
            role = 'admin' if total == 0 else 'user'
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, timezone_name, role, quiet_hours_start, quiet_hours_end, working_days, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, '0,1,2,3,4,5,6', ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    updated_at = excluded.updated_at
            """, (user_id, username, full_name, timezone_name, role, now_utc, now_utc))
            await db.commit()

    async def get_user(self, user_id: int) -> UserRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, username, full_name, timezone_name, role, quiet_hours_start, quiet_hours_end, working_days FROM users WHERE user_id = ?",
                (user_id,),
            )
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

    async def list_users(self) -> list[UserRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, username, full_name, timezone_name, role, quiet_hours_start, quiet_hours_end, working_days FROM users ORDER BY COALESCE(username, full_name), user_id"
            )
            rows = await cur.fetchall()
            return [UserRecord(*row) for row in rows]

    async def set_user_role(self, actor_user_id: int, target_user_id: int, role: str) -> bool:
        if role not in {"user", "manager", "admin"}:
            return False
        actor = await self.get_user(actor_user_id)
        if not actor or actor.role != "admin":
            return False
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
                (role, datetime.now(timezone.utc).isoformat(), target_user_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def set_quiet_hours(self, user_id: int, start: str | None, end: str | None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE users SET quiet_hours_start = ?, quiet_hours_end = ?, updated_at = ? WHERE user_id = ?",
                (start, end, datetime.now(timezone.utc).isoformat(), user_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def set_working_days(self, user_id: int, working_days: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE users SET working_days = ?, updated_at = ? WHERE user_id = ?",
                (working_days, datetime.now(timezone.utc).isoformat(), user_id),
            )
            await db.commit()
            return cur.rowcount > 0
