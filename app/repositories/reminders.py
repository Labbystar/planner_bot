from datetime import datetime, timezone
from dataclasses import dataclass

import aiosqlite


@dataclass(slots=True)
class ReminderRecord:
    id: int
    creator_id: int
    text: str
    kind: str
    scheduled_at_utc: str | None
    local_time: str | None
    weekday: int | None
    creator_timezone_at_creation: str | None
    is_active: int


class RemindersRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def add_once_reminder(self, creator_id: int, text: str, scheduled_at_utc: str, creator_timezone_at_creation: str, recipients: list[int]) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                INSERT INTO reminders (
                    creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                    creator_timezone_at_creation, is_active, created_at
                ) VALUES (?, ?, 'once', ?, NULL, NULL, ?, 1, ?)
            """, (creator_id, text, scheduled_at_utc, creator_timezone_at_creation, now_utc))
            reminder_id = cur.lastrowid
            await db.executemany(
                "INSERT OR IGNORE INTO reminder_recipients (reminder_id, user_id) VALUES (?, ?)",
                [(reminder_id, uid) for uid in recipients],
            )
            await db.commit()
            return reminder_id

    async def add_daily_reminder(self, creator_id: int, text: str, local_time: str, creator_timezone_at_creation: str, recipients: list[int]) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                INSERT INTO reminders (
                    creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                    creator_timezone_at_creation, is_active, created_at
                ) VALUES (?, ?, 'daily', NULL, ?, NULL, ?, 1, ?)
            """, (creator_id, text, local_time, creator_timezone_at_creation, now_utc))
            reminder_id = cur.lastrowid
            await db.executemany(
                "INSERT OR IGNORE INTO reminder_recipients (reminder_id, user_id) VALUES (?, ?)",
                [(reminder_id, uid) for uid in recipients],
            )
            await db.commit()
            return reminder_id

    async def add_weekly_reminder(self, creator_id: int, text: str, weekday: int, local_time: str, creator_timezone_at_creation: str, recipients: list[int]) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                INSERT INTO reminders (
                    creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                    creator_timezone_at_creation, is_active, created_at
                ) VALUES (?, ?, 'weekly', NULL, ?, ?, ?, 1, ?)
            """, (creator_id, text, local_time, weekday, creator_timezone_at_creation, now_utc))
            reminder_id = cur.lastrowid
            await db.executemany(
                "INSERT OR IGNORE INTO reminder_recipients (reminder_id, user_id) VALUES (?, ?)",
                [(reminder_id, uid) for uid in recipients],
            )
            await db.commit()
            return reminder_id

    async def get_reminder(self, reminder_id: int) -> ReminderRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                       creator_timezone_at_creation, is_active
                FROM reminders WHERE id = ?
            """, (reminder_id,))
            row = await cur.fetchone()
            return ReminderRecord(*row) if row else None

    async def list_creator_reminders(self, creator_id: int) -> list[ReminderRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                       creator_timezone_at_creation, is_active
                FROM reminders
                WHERE creator_id = ? AND is_active = 1
                ORDER BY id ASC
            """, (creator_id,))
            rows = await cur.fetchall()
            return [ReminderRecord(*row) for row in rows]

    async def get_active_once_reminders(self) -> list[ReminderRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                       creator_timezone_at_creation, is_active
                FROM reminders
                WHERE is_active = 1 AND kind = 'once'
            """)
            rows = await cur.fetchall()
            return [ReminderRecord(*row) for row in rows]

    async def get_active_recurring_reminders(self) -> list[ReminderRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("""
                SELECT id, creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                       creator_timezone_at_creation, is_active
                FROM reminders
                WHERE is_active = 1 AND kind IN ('daily', 'weekly')
            """)
            rows = await cur.fetchall()
            return [ReminderRecord(*row) for row in rows]

    async def get_recipients(self, reminder_id: int) -> list[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id FROM reminder_recipients WHERE reminder_id = ? ORDER BY user_id ASC",
                (reminder_id,),
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def add_recipient(self, reminder_id: int, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO reminder_recipients (reminder_id, user_id) VALUES (?, ?)",
                (reminder_id, user_id),
            )
            await db.commit()

    async def deactivate_reminder(self, reminder_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET is_active = 0 WHERE id = ?", (reminder_id,))
            await db.commit()

    async def delete_reminder_for_creator(self, reminder_id: int, creator_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE reminders SET is_active = 0 WHERE id = ? AND creator_id = ? AND is_active = 1",
                (reminder_id, creator_id),
            )
            await db.commit()
            return cur.rowcount > 0
