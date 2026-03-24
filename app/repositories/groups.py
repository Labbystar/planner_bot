from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass(slots=True)
class GroupRecord:
    id: int
    owner_user_id: int
    name: str
    created_at: str


class GroupsRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_group(self, owner_user_id: int, name: str, member_ids: list[int]) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO recipient_groups (owner_user_id, name, created_at) VALUES (?, ?, ?)",
                (owner_user_id, name, datetime.now(timezone.utc).isoformat()),
            )
            gid = cur.lastrowid
            await db.executemany(
                "INSERT OR IGNORE INTO recipient_group_members (group_id, user_id) VALUES (?, ?)",
                [(gid, uid) for uid in member_ids],
            )
            await db.commit()
            return gid

    async def list_groups(self, owner_user_id: int) -> list[GroupRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT id, owner_user_id, name, created_at FROM recipient_groups WHERE owner_user_id = ? ORDER BY name",
                (owner_user_id,),
            )
            return [GroupRecord(*row) for row in await cur.fetchall()]

    async def get_group_members(self, group_id: int) -> list[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT user_id FROM recipient_group_members WHERE group_id = ? ORDER BY user_id", (group_id,))
            return [r[0] for r in await cur.fetchall()]

    async def delete_group(self, owner_user_id: int, group_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("DELETE FROM recipient_groups WHERE id = ? AND owner_user_id = ?", (group_id, owner_user_id))
            await db.execute("DELETE FROM recipient_group_members WHERE group_id = ?", (group_id,))
            await db.commit()
            return cur.rowcount > 0
