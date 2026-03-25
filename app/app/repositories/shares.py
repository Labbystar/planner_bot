from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass(slots=True)
class ShareRecord:
    id: int
    token: str
    reminder_id: int
    owner_user_id: int
    share_mode: str
    expires_at: str | None
    is_active: int
    created_at: str


class SharesRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_share(self, token: str, reminder_id: int, owner_user_id: int, share_mode: str, expires_at: str | None = None) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                INSERT INTO shares (token, reminder_id, owner_user_id, share_mode, expires_at, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (token, reminder_id, owner_user_id, share_mode, expires_at, now_utc))
            await db.commit()
            return cur.lastrowid

    async def get_share_by_token(self, token: str) -> ShareRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, token, reminder_id, owner_user_id, share_mode, expires_at, is_active, created_at
                FROM shares WHERE token = ?
            """, (token,))
            row = await cur.fetchone()
            return ShareRecord(*row) if row else None

    async def list_user_shares(self, owner_user_id: int) -> list[ShareRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, token, reminder_id, owner_user_id, share_mode, expires_at, is_active, created_at
                FROM shares WHERE owner_user_id = ? AND is_active = 1
                ORDER BY id DESC
            """, (owner_user_id,))
            rows = await cur.fetchall()
            return [ShareRecord(*row) for row in rows]

    async def deactivate_share_by_token(self, token: str, owner_user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE shares SET is_active = 0 WHERE token = ? AND owner_user_id = ? AND is_active = 1",
                (token, owner_user_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def mark_accepted(self, share_id: int, accepted_by_user_id: int) -> bool:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO share_acceptances (share_id, accepted_by_user_id, accepted_at) VALUES (?, ?, ?)",
                    (share_id, accepted_by_user_id, now_utc),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def is_already_accepted(self, share_id: int, accepted_by_user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT 1 FROM share_acceptances WHERE share_id = ? AND accepted_by_user_id = ?",
                (share_id, accepted_by_user_id),
            )
            return (await cur.fetchone()) is not None
