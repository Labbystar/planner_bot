import aiosqlite


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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('once', 'daily', 'weekly')),
                scheduled_at_utc TEXT,
                local_time TEXT,
                weekday INTEGER,
                creator_timezone_at_creation TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(creator_id) REFERENCES users(user_id)
            )
        """)

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

        await db.commit()
