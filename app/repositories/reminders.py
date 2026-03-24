from dataclasses import dataclass
from datetime import datetime, timezone

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
    status: str
    priority: str
    category: str
    completed_at: str | None
    snoozed_until_utc: str | None
    last_fired_at: str | None
    pre_remind_minutes: int
    interval_hours: int | None


@dataclass(slots=True)
class RecipientReminderStateRecord:
    reminder_id: int
    user_id: int
    status: str
    last_delivered_at: str | None
    delivered_count: int
    acknowledged_at: str | None
    last_pre_delivered_at: str | None
    last_skipped_reason: str | None


class RemindersRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _insert_reminder(self, kind: str, creator_id: int, text: str, scheduled_at_utc: str | None,
                               local_time: str | None, weekday: int | None,
                               creator_timezone_at_creation: str, recipients: list[int],
                               category: str, priority: str, pre_remind_minutes: int = 0,
                               interval_hours: int | None = None) -> int:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                INSERT INTO reminders (
                    creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                    creator_timezone_at_creation, is_active, created_at, status, priority, category,
                    completed_at, snoozed_until_utc, last_fired_at, pre_remind_minutes, interval_hours
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 'active', ?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (
                    creator_id, text, kind, scheduled_at_utc, local_time, weekday,
                    creator_timezone_at_creation, now_utc, priority, category,
                    pre_remind_minutes, interval_hours,
                ),
            )
            reminder_id = cur.lastrowid
            rows = [(reminder_id, uid) for uid in recipients]
            await db.executemany(
                "INSERT OR IGNORE INTO reminder_recipients (reminder_id, user_id) VALUES (?, ?)",
                rows,
            )
            await db.executemany(
                "INSERT OR IGNORE INTO recipient_reminder_states (reminder_id, user_id, status, delivered_count) VALUES (?, ?, 'pending', 0)",
                rows,
            )
            await db.commit()
            return reminder_id

    async def add_once_reminder(self, creator_id: int, text: str, scheduled_at_utc: str,
                                creator_timezone_at_creation: str, recipients: list[int],
                                category: str = 'work', priority: str = 'medium', pre_remind_minutes: int = 0) -> int:
        return await self._insert_reminder('once', creator_id, text, scheduled_at_utc, None, None,
                                           creator_timezone_at_creation, recipients, category, priority,
                                           pre_remind_minutes, None)

    async def add_daily_reminder(self, creator_id: int, text: str, local_time: str,
                                 creator_timezone_at_creation: str, recipients: list[int],
                                 category: str = 'work', priority: str = 'medium', pre_remind_minutes: int = 0) -> int:
        return await self._insert_reminder('daily', creator_id, text, None, local_time, None,
                                           creator_timezone_at_creation, recipients, category, priority,
                                           pre_remind_minutes, None)

    async def add_weekly_reminder(self, creator_id: int, text: str, weekday: int, local_time: str,
                                  creator_timezone_at_creation: str, recipients: list[int],
                                  category: str = 'work', priority: str = 'medium', pre_remind_minutes: int = 0) -> int:
        return await self._insert_reminder('weekly', creator_id, text, None, local_time, weekday,
                                           creator_timezone_at_creation, recipients, category, priority,
                                           pre_remind_minutes, None)

    async def add_interval_reminder(self, creator_id: int, text: str, interval_hours: int, start_at_utc: str,
                                    creator_timezone_at_creation: str, recipients: list[int],
                                    category: str = 'work', priority: str = 'medium', pre_remind_minutes: int = 0) -> int:
        return await self._insert_reminder('interval', creator_id, text, start_at_utc, None, None,
                                           creator_timezone_at_creation, recipients, category, priority,
                                           pre_remind_minutes, interval_hours)

    async def _fetch_one(self, query: str, params: tuple) -> ReminderRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(query, params)
            row = await cur.fetchone()
            return ReminderRecord(*row) if row else None

    def _select_fields(self) -> str:
        return (
            "id, creator_id, text, kind, scheduled_at_utc, local_time, weekday, "
            "creator_timezone_at_creation, is_active, status, priority, category, "
            "completed_at, snoozed_until_utc, last_fired_at, pre_remind_minutes, interval_hours"
        )

    async def get_reminder(self, reminder_id: int) -> ReminderRecord | None:
        return await self._fetch_one(f"SELECT {self._select_fields()} FROM reminders WHERE id = ?", (reminder_id,))

    async def list_creator_reminders(self, creator_id: int) -> list[ReminderRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                f"SELECT {self._select_fields()} FROM reminders WHERE creator_id = ? AND is_active = 1 AND status IN ('active', 'snoozed', 'missed') ORDER BY id ASC",
                (creator_id,),
            )
            rows = await cur.fetchall()
            return [ReminderRecord(*row) for row in rows]

    async def get_active_once_reminders(self) -> list[ReminderRecord]:
        return await self._list_by_kinds(["once"])

    async def get_active_recurring_reminders(self) -> list[ReminderRecord]:
        return await self._list_by_kinds(["daily", "weekly", "interval"])

    async def _list_by_kinds(self, kinds: list[str]) -> list[ReminderRecord]:
        placeholders = ",".join("?" for _ in kinds)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                f"SELECT {self._select_fields()} FROM reminders WHERE is_active = 1 AND kind IN ({placeholders}) AND status IN ('active', 'snoozed', 'missed')",
                tuple(kinds),
            )
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
            await db.execute(
                "INSERT OR IGNORE INTO recipient_reminder_states (reminder_id, user_id, status, delivered_count) VALUES (?, ?, 'pending', 0)",
                (reminder_id, user_id),
            )
            await db.commit()

    async def deactivate_reminder(self, reminder_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET is_active = 0, status = 'cancelled' WHERE id = ?", (reminder_id,))
            await db.commit()

    async def delete_reminder_for_creator(self, reminder_id: int, creator_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE reminders SET is_active = 0, status = 'cancelled' WHERE id = ? AND creator_id = ? AND is_active = 1",
                (reminder_id, creator_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def mark_done(self, reminder_id: int) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE reminders SET status = 'done', completed_at = ?, is_active = 0 WHERE id = ?",
                (now_utc, reminder_id),
            )
            await db.execute(
                "UPDATE recipient_reminder_states SET status = 'done', acknowledged_at = COALESCE(acknowledged_at, ?) WHERE reminder_id = ?",
                (now_utc, reminder_id),
            )
            await db.commit()

    async def mark_status(self, reminder_id: int, status: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id))
            await db.commit()

    async def update_priority(self, reminder_id: int, priority: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET priority = ? WHERE id = ?", (priority, reminder_id))
            await db.commit()

    async def update_category(self, reminder_id: int, category: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET category = ? WHERE id = ?", (category, reminder_id))
            await db.commit()

    async def set_pre_remind_minutes(self, reminder_id: int, minutes: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET pre_remind_minutes = ? WHERE id = ?", (minutes, reminder_id))
            await db.commit()

    async def set_snoozed_until(self, reminder_id: int, snoozed_until_utc: str | None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE reminders SET snoozed_until_utc = ?, status = CASE WHEN ? IS NULL THEN 'active' ELSE 'snoozed' END WHERE id = ?",
                (snoozed_until_utc, snoozed_until_utc, reminder_id),
            )
            await db.commit()

    async def set_last_fired_at(self, reminder_id: int, fired_at_utc: str | None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE reminders SET last_fired_at = ? WHERE id = ?", (fired_at_utc, reminder_id))
            await db.commit()

    async def get_user_statistics(self, creator_id: int) -> dict:
        stats = {
            "total": 0,
            "active": 0,
            "done": 0,
            "missed": 0,
            "cancelled": 0,
            "snoozed": 0,
            "with_pre_remind": 0,
            "interval": 0,
            "categories": {},
            "priorities": {},
        }
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT status, category, priority, pre_remind_minutes, kind FROM reminders WHERE creator_id = ?",
                (creator_id,),
            )
            rows = await cur.fetchall()
        stats["total"] = len(rows)
        for status, category, priority, pre_remind_minutes, kind in rows:
            stats[status] = stats.get(status, 0) + 1
            stats["categories"][category] = stats["categories"].get(category, 0) + 1
            stats["priorities"][priority] = stats["priorities"].get(priority, 0) + 1
            if pre_remind_minutes and pre_remind_minutes > 0:
                stats["with_pre_remind"] += 1
            if kind == "interval":
                stats["interval"] += 1
        return stats

    async def get_recipient_state(self, reminder_id: int, user_id: int) -> RecipientReminderStateRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT reminder_id, user_id, status, last_delivered_at, delivered_count, acknowledged_at, last_pre_delivered_at, last_skipped_reason FROM recipient_reminder_states WHERE reminder_id = ? AND user_id = ?",
                (reminder_id, user_id),
            )
            row = await cur.fetchone()
            return RecipientReminderStateRecord(*row) if row else None

    async def list_recipient_states(self, reminder_id: int) -> list[RecipientReminderStateRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT reminder_id, user_id, status, last_delivered_at, delivered_count, acknowledged_at, last_pre_delivered_at, last_skipped_reason FROM recipient_reminder_states WHERE reminder_id = ? ORDER BY user_id ASC",
                (reminder_id,),
            )
            rows = await cur.fetchall()
            return [RecipientReminderStateRecord(*row) for row in rows]

    async def mark_recipient_delivered(self, reminder_id: int, user_id: int, *, pre: bool = False, delivered_at: str | None = None) -> None:
        delivered_at = delivered_at or datetime.now(timezone.utc).isoformat()
        field = 'last_pre_delivered_at' if pre else 'last_delivered_at'
        status = 'pre_sent' if pre else 'sent'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE recipient_reminder_states SET {field} = ?, delivered_count = CASE WHEN ? = 0 THEN delivered_count + 1 ELSE delivered_count END, status = ?, last_skipped_reason = NULL WHERE reminder_id = ? AND user_id = ?",
                (delivered_at, 1 if pre else 0, status, reminder_id, user_id),
            )
            await db.commit()

    async def mark_recipient_ack(self, reminder_id: int, user_id: int) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE recipient_reminder_states SET status = 'acknowledged', acknowledged_at = ? WHERE reminder_id = ? AND user_id = ?",
                (now_utc, reminder_id, user_id),
            )
            await db.commit()

    async def mark_recipient_skipped(self, reminder_id: int, user_id: int, reason: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE recipient_reminder_states SET status = 'skipped', last_skipped_reason = ? WHERE reminder_id = ? AND user_id = ?",
                (reason, reminder_id, user_id),
            )
            await db.commit()
