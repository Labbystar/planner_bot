import aiosqlite


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    cur = await db.execute(f"PRAGMA table_info({table})")
    rows = await cur.fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                timezone_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await _ensure_column(db, 'users', 'role', "TEXT NOT NULL DEFAULT 'user'")
        await _ensure_column(db, 'users', 'quiet_hours_start', 'TEXT')
        await _ensure_column(db, 'users', 'quiet_hours_end', 'TEXT')
        await _ensure_column(db, 'users', 'working_days', "TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6'")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipient_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(owner_user_id, name),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipient_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                UNIQUE(group_id, user_id),
                FOREIGN KEY(group_id) REFERENCES recipient_groups(id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminder_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                kind TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'work',
                priority TEXT NOT NULL DEFAULT 'medium',
                pre_remind_minutes INTEGER NOT NULL DEFAULT 0,
                weekday INTEGER,
                local_time TEXT,
                interval_hours INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(owner_user_id, name),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('once', 'daily', 'weekly', 'interval')),
                scheduled_at_utc TEXT,
                local_time TEXT,
                weekday INTEGER,
                creator_timezone_at_creation TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                priority TEXT NOT NULL DEFAULT 'medium',
                category TEXT NOT NULL DEFAULT 'work',
                completed_at TEXT,
                snoozed_until_utc TEXT,
                last_fired_at TEXT,
                pre_remind_minutes INTEGER NOT NULL DEFAULT 0,
                interval_hours INTEGER,
                FOREIGN KEY(creator_id) REFERENCES users(user_id)
            )
        """)

        await _ensure_column(db, 'reminders', 'status', "TEXT NOT NULL DEFAULT 'active'")
        await _ensure_column(db, 'reminders', 'priority', "TEXT NOT NULL DEFAULT 'medium'")
        await _ensure_column(db, 'reminders', 'category', "TEXT NOT NULL DEFAULT 'work'")
        await _ensure_column(db, 'reminders', 'completed_at', 'TEXT')
        await _ensure_column(db, 'reminders', 'snoozed_until_utc', 'TEXT')
        await _ensure_column(db, 'reminders', 'last_fired_at', 'TEXT')
        await _ensure_column(db, 'reminders', 'pre_remind_minutes', 'INTEGER NOT NULL DEFAULT 0')
        await _ensure_column(db, 'reminders', 'interval_hours', 'INTEGER')

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminder_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                UNIQUE(reminder_id, user_id),
                FOREIGN KEY(reminder_id) REFERENCES reminders(id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipient_reminder_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                last_delivered_at TEXT,
                delivered_count INTEGER NOT NULL DEFAULT 0,
                acknowledged_at TEXT,
                last_pre_delivered_at TEXT,
                last_skipped_reason TEXT,
                UNIQUE(reminder_id, user_id),
                FOREIGN KEY(reminder_id) REFERENCES reminders(id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                reminder_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL,
                share_mode TEXT NOT NULL CHECK(share_mode IN ('copy', 'recipient')),
                expires_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(reminder_id) REFERENCES reminders(id),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS share_acceptances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                share_id INTEGER NOT NULL,
                accepted_by_user_id INTEGER NOT NULL,
                accepted_at TEXT NOT NULL,
                UNIQUE(share_id, accepted_by_user_id),
                FOREIGN KEY(share_id) REFERENCES shares(id),
                FOREIGN KEY(accepted_by_user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminder_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(reminder_id) REFERENCES reminders(id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        await db.commit()
