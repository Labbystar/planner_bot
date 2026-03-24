from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass(slots=True)
class ReminderEventRecord:
    id: int
    reminder_id: int
    user_id: int
    event_type: str
    payload: str | None
    created_at: str


class EventsRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def add_event(self, reminder_id: int, user_id: int, event_type: str, payload: str | None = None) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO reminder_events (reminder_id, user_id, event_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (reminder_id, user_id, event_type, payload, now_utc),
            )
            await db.commit()
            return cur.lastrowid

    async def list_events_for_user(self, user_id: int, limit: int = 20) -> list[ReminderEventRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT id, reminder_id, user_id, event_type, payload, created_at
                FROM reminder_events
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cur.fetchall()
            return [ReminderEventRecord(*row) for row in rows]

    async def count_events_by_type_for_user(self, user_id: int) -> dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT event_type, COUNT(*) FROM reminder_events WHERE user_id = ? GROUP BY event_type",
                (user_id,),
            )
            rows = await cur.fetchall()
            return {event_type: count for event_type, count in rows}
