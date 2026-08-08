from __future__ import annotations

import sqlite3
from pathlib import Path

HEAD_REVISION = "0018_stage_8f"


class DatabaseMigrationRequired(RuntimeError):
    pass


def get_head_revision() -> str:
    return HEAD_REVISION


def get_current_revision(database_path: Path) -> str | None:
    if not database_path.is_file():
        return None
    try:
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    return str(row[0]) if row is not None else None


def require_database_current(database_path: Path) -> None:
    current = get_current_revision(database_path)
    head = get_head_revision()
    if current != head:
        raise DatabaseMigrationRequired(
            "database schema is not current "
            f"(current={current or 'none'}, expected={head}); "
            "run `uv run alembic upgrade head`"
        )
