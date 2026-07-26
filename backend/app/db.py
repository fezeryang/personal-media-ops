import sqlite3
from pathlib import Path

from app.database_migrations import require_database_current


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database(database_path: Path) -> None:
    """Verify the explicitly migrated schema without mutating it."""

    require_database_current(database_path)
    with connect_database(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
