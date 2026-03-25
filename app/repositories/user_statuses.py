import aiosqlite
from datetime import datetime, timezone

async def set_status(db_path, reminder_id, user_id, status):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
        INSERT INTO reminder_user_status (reminder_id, user_id, status, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(reminder_id, user_id)
        DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
        """, (
            reminder_id,
            user_id,
            status,
            datetime.now(timezone.utc).isoformat()
        ))
        await db.commit()

async def get_statuses(db_path, reminder_id):
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("""
        SELECT user_id, status FROM reminder_user_status
        WHERE reminder_id=?
        """, (reminder_id,))
        return await cur.fetchall()
