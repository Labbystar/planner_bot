from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass(slots=True)
class TemplateRecord:
    id: int
    owner_user_id: int
    name: str
    text: str
    kind: str
    category: str
    priority: str
    pre_remind_minutes: int
    weekday: int | None
    local_time: str | None
    interval_hours: int | None
    created_at: str


class TemplatesRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_template(self, owner_user_id: int, name: str, text: str, kind: str, category: str, priority: str, pre_remind_minutes: int = 0, weekday: int | None = None, local_time: str | None = None, interval_hours: int | None = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """INSERT INTO reminder_templates (owner_user_id, name, text, kind, category, priority, pre_remind_minutes, weekday, local_time, interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (owner_user_id, name, text, kind, category, priority, pre_remind_minutes, weekday, local_time, interval_hours, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
            return cur.lastrowid

    async def list_templates(self, owner_user_id: int) -> list[TemplateRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT id, owner_user_id, name, text, kind, category, priority, pre_remind_minutes, weekday, local_time, interval_hours, created_at FROM reminder_templates WHERE owner_user_id = ? ORDER BY name",
                (owner_user_id,),
            )
            return [TemplateRecord(*row) for row in await cur.fetchall()]

    async def get_template(self, template_id: int) -> TemplateRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT id, owner_user_id, name, text, kind, category, priority, pre_remind_minutes, weekday, local_time, interval_hours, created_at FROM reminder_templates WHERE id = ?",
                (template_id,),
            )
            row = await cur.fetchone()
            return TemplateRecord(*row) if row else None

    async def delete_template(self, owner_user_id: int, template_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("DELETE FROM reminder_templates WHERE id = ? AND owner_user_id = ?", (template_id, owner_user_id))
            await db.commit()
            return cur.rowcount > 0
