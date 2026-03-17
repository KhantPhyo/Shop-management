import sqlite3
import bcrypt
from config import Config


def get_db():
    """Get a database connection with Row factory for dict-like access"""
    db = sqlite3.connect(Config.DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db


def close_db(e=None):
    """Close database connection (Flask teardown)"""
    pass  # We use per-request connections via get_db()


def init_db():
    """Initialize database: create tables and seed admin"""
    db = sqlite3.connect(Config.DATABASE_PATH)
    db.row_factory = sqlite3.Row

    db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            leader_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            telegram_bot_token TEXT NOT NULL,
            telegram_chat_id TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            shop_id INTEGER NOT NULL REFERENCES shops(id),
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            schedule_type TEXT DEFAULT 'one_time',
            schedule_day INTEGER,
            schedule_time TEXT,
            deadline TIMESTAMP,
            fine_amount_mmk INTEGER DEFAULT 0,
            accepted_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            rejection_reason TEXT,
            required_report_type TEXT DEFAULT 'photo',
            created_by TEXT DEFAULT 'web',
            reminder_count INTEGER DEFAULT 0,
            last_reminder_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS task_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            report_type TEXT NOT NULL,
            file_path TEXT,
            file_name TEXT,
            text_content TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            action TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scheduled_tasks_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_template_id INTEGER NOT NULL REFERENCES tasks(id),
            cron_expression TEXT NOT NULL,
            next_run_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            last_generated_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            target_type TEXT NOT NULL DEFAULT 'all',
            target_shop_id INTEGER REFERENCES shops(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcement_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id INTEGER NOT NULL REFERENCES announcements(id),
            shop_id INTEGER NOT NULL REFERENCES shops(id),
            response TEXT NOT NULL,
            responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Migration: add required_report_type if missing
    try:
        db.execute("SELECT required_report_type FROM tasks LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE tasks ADD COLUMN required_report_type TEXT DEFAULT 'photo'")
        db.commit()

    # Seed admin user if not exists
    existing = db.execute(
        "SELECT id FROM admins WHERE username = ?", (Config.ADMIN_USERNAME,)
    ).fetchone()

    if not existing:
        password_hash = bcrypt.hashpw(
            Config.ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (Config.ADMIN_USERNAME, password_hash)
        )
        db.commit()

    db.close()


def init_app(app):
    """Initialize database with Flask app"""
    init_db()
    app.teardown_appcontext(close_db)
