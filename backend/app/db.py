import sqlite3
from pathlib import Path

TASK_STATUSES = (
    "pending",
    "running",
    "waiting_login",
    "succeeded",
    "failed",
    "cancelled",
)


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    statuses = ", ".join(f"'{status}'" for status in TASK_STATUSES)
    with connect_database(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS crawler_tasks (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL CHECK (platform = 'bili'),
                crawler_type TEXT NOT NULL CHECK (crawler_type = 'search'),
                keywords TEXT NOT NULL CHECK (length(trim(keywords)) > 0),
                login_type TEXT NOT NULL CHECK (login_type = 'qrcode'),
                status TEXT NOT NULL CHECK (status IN ({statuses})),
                requested_count INTEGER NOT NULL
                    CHECK (requested_count BETWEEN 1 AND 20),
                actual_count INTEGER NOT NULL DEFAULT 0
                    CHECK (actual_count >= 0),
                output_dir TEXT NOT NULL,
                log_path TEXT NOT NULL,
                qrcode_path TEXT NOT NULL,
                pid INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0
                    CHECK (cancel_requested IN (0, 1))
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_crawler_tasks_status_created
            ON crawler_tasks (status, created_at)
            """
        )
