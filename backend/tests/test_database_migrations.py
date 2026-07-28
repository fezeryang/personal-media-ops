import sqlite3
from pathlib import Path

import pytest

from app.database_migrations import (
    DatabaseMigrationRequired,
    get_current_revision,
    get_head_revision,
    require_database_current,
)
from tests.alembic_utils import run_alembic_command

LEGACY_REVISION = "0001_legacy_tasks"
MULTIPLATFORM_REVISION = "0002_multiplatform_tasks"
REGISTERED_PLATFORMS = ("bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks")
LEGACY_TASK_VALUES = (
    "28a58041-9be7-4b39-9dea-2493fe10c249",
    "bili",
    "search",
    "AI Agent",
    "qrcode",
    "succeeded",
    20,
    7,
    "/var/lib/mediaops/crawler-output/tasks/28a58041",
    "/var/log/mediaops/crawler/28a58041.log",
    "/var/lib/mediaops/qrcodes/28a58041.png",
    1234,
    None,
    "2026-07-25T12:00:00Z",
    "2026-07-25T12:00:01Z",
    "2026-07-25T12:01:00Z",
    0,
)


def create_legacy_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE crawler_tasks (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL CHECK (platform = 'bili'),
                crawler_type TEXT NOT NULL CHECK (crawler_type = 'search'),
                keywords TEXT NOT NULL CHECK (length(trim(keywords)) > 0),
                login_type TEXT NOT NULL CHECK (login_type = 'qrcode'),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'pending', 'running', 'waiting_login',
                        'succeeded', 'failed', 'cancelled'
                    )
                ),
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
            );
            CREATE INDEX idx_crawler_tasks_status_created
            ON crawler_tasks (status, created_at);
            """
        )
        connection.execute(
            """
            INSERT INTO crawler_tasks VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            LEGACY_TASK_VALUES,
        )


def read_task_values(database_path: Path) -> tuple[object, ...]:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM crawler_tasks WHERE id = ?",
            (LEGACY_TASK_VALUES[0],),
        ).fetchone()
    assert row is not None
    return row


def test_upgrade_blank_database_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "blank" / "mediaops.db"

    run_alembic_command(database_path, "upgrade", "head")

    assert get_current_revision(database_path) == get_head_revision()
    with sqlite3.connect(database_path) as connection:
        for platform in REGISTERED_PLATFORMS:
            connection.execute(
                """
                INSERT INTO crawler_tasks (
                    id, platform, crawler_type, keywords, login_type, status,
                    requested_count, actual_count, output_dir, log_path,
                    qrcode_path, created_at, cancel_requested
                )
                VALUES (?, ?, 'search', 'test', 'qrcode', 'pending',
                        1, 0, '/output', '/log', '/qrcode',
                        '2026-07-26T00:00:00Z', 0)
                """,
                (f"{platform}-task", platform),
            )


def test_runtime_head_matches_alembic_script_head(tmp_path: Path) -> None:
    result = run_alembic_command(tmp_path / "unused.db", "heads")

    assert result.stdout.split()[0] == get_head_revision()


def test_head_rejects_unregistered_platform(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")

    with (
        sqlite3.connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'youtube-task', 'youtube', 'search', 'test', 'qrcode',
                'pending', 1, 0, '/output', '/log', '/qrcode',
                '2026-07-26T00:00:00Z', 0
            )
            """
        )


def test_upgrade_legacy_database_preserves_bilibili_row(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    create_legacy_database(database_path)
    before = read_task_values(database_path)

    run_alembic_command(database_path, "upgrade", "head")

    assert read_task_values(database_path) == before
    assert get_current_revision(database_path) == get_head_revision()


def test_upgrade_from_0002_preserves_all_existing_platform_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", MULTIPLATFORM_REVISION)
    existing = (
        ("bili-task", "bili", "succeeded", 2),
        ("xhs-task", "xhs", "succeeded", 5),
        ("dy-task", "dy", "failed", 0),
    )
    with sqlite3.connect(database_path) as connection:
        for task_id, platform, status, actual_count in existing:
            connection.execute(
                """
                INSERT INTO crawler_tasks (
                    id, platform, crawler_type, keywords, login_type, status,
                    requested_count, actual_count, output_dir, log_path,
                    qrcode_path, error_message, created_at, finished_at,
                    cancel_requested
                )
                VALUES (?, ?, 'search', 'AI', 'qrcode', ?, 5, ?,
                        ?, ?, ?, ?, '2026-07-26T00:00:00Z',
                        '2026-07-26T00:01:00Z', 0)
                """,
                (
                    task_id,
                    platform,
                    status,
                    actual_count,
                    f"/output/{task_id}",
                    f"/log/{task_id}",
                    f"/qrcode/{task_id}",
                    None if status == "succeeded" else "resource constrained",
                ),
            )
        before = connection.execute(
            "SELECT * FROM crawler_tasks ORDER BY id"
        ).fetchall()

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        after = connection.execute(
            "SELECT * FROM crawler_tasks ORDER BY id"
        ).fetchall()
    assert after == before
    assert get_current_revision(database_path) == get_head_revision()


def test_runtime_rejects_missing_or_outdated_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"

    with pytest.raises(DatabaseMigrationRequired, match="upgrade head"):
        require_database_current(missing)

    create_legacy_database(missing)
    with pytest.raises(DatabaseMigrationRequired, match="upgrade head"):
        require_database_current(missing)


def test_downgrade_refuses_when_multiplatform_rows_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'xhs-task', 'xhs', 'search', 'test', 'qrcode', 'pending',
                1, 0, '/output', '/log', '/qrcode', '2026-07-26T00:00:00Z', 0
            )
            """
        )

    result = run_alembic_command(
        database_path,
        "downgrade",
        LEGACY_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "non-Bilibili" in result.stderr
    assert get_current_revision(database_path) == get_head_revision()


def test_downgrade_to_0002_refuses_when_remaining_platform_rows_exist(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'zhihu-task', 'zhihu', 'search', 'test', 'qrcode', 'pending',
                1, 0, '/output', '/log', '/qrcode',
                '2026-07-28T00:00:00Z', 0
            )
            """
        )

    result = run_alembic_command(
        database_path,
        "downgrade",
        MULTIPLATFORM_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "remaining-platform" in result.stderr
    assert get_current_revision(database_path) == get_head_revision()
