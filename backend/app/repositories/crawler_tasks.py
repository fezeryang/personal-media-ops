import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import connect_database, initialize_database

CANCELLABLE_STATUSES = ("pending", "running", "waiting_login")


class TaskNotCancellableError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _row_to_task(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    task = dict(row)
    task["cancel_requested"] = bool(task["cancel_requested"])
    task["mode"] = task["crawler_type"]
    for key in ("target_ids", "target_urls", "creator_ids", "creator_urls"):
        raw_value = task.get(key, "[]")
        try:
            parsed = json.loads(str(raw_value))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"crawler task contains invalid {key} JSON") from error
        if not isinstance(parsed, list) or not all(
            isinstance(value, str) for value in parsed
        ):
            raise RuntimeError(f"crawler task contains invalid {key} values")
        task[key] = parsed
    return task


class CrawlerTaskRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        initialize_database(self.database_path)

    @staticmethod
    def new_id() -> str:
        return str(uuid4())

    def create(
        self,
        *,
        platform: str,
        crawler_type: str,
        keywords: str | None,
        login_type: str,
        requested_count: int,
        target_ids: Sequence[str] = (),
        target_urls: Sequence[str] = (),
        creator_ids: Sequence[str] = (),
        creator_urls: Sequence[str] = (),
        parent_content_id: str | None = None,
        parent_comment_id: str | None = None,
        requested_comment_count: int = 0,
        requested_sub_comment_count: int = 0,
        output_dir: str,
        log_path: str,
        qrcode_path: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = task_id or self.new_id()
        created_at = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO crawler_tasks (
                    id, platform, crawler_type, keywords, login_type, status,
                    requested_count, actual_count, output_dir, log_path,
                    qrcode_path, pid, error_message, created_at, started_at,
                    finished_at, cancel_requested, target_ids, target_urls,
                    creator_ids, creator_urls, parent_content_id,
                    parent_comment_id, requested_comment_count,
                    requested_sub_comment_count
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, 0, ?, ?, ?, NULL, NULL,
                        ?, NULL, NULL, 0, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    platform,
                    crawler_type,
                    keywords,
                    login_type,
                    requested_count,
                    output_dir,
                    log_path,
                    qrcode_path,
                    created_at,
                    json.dumps(target_ids, ensure_ascii=False),
                    json.dumps(target_urls, ensure_ascii=False),
                    json.dumps(creator_ids, ensure_ascii=False),
                    json.dumps(creator_urls, ensure_ascii=False),
                    parent_content_id,
                    parent_comment_id,
                    requested_comment_count,
                    requested_sub_comment_count,
                ),
            )
        task = self.get(identifier)
        if task is None:
            raise RuntimeError("created crawler task could not be read")
        return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return _row_to_task(row)

    def list(self) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM crawler_tasks
                ORDER BY created_at DESC, rowid DESC
                """
            ).fetchall()
        return [_row_to_task(row) for row in rows if row is not None]

    def claim_next(self) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                """
                SELECT 1 FROM crawler_tasks
                WHERE status IN ('running', 'waiting_login')
                LIMIT 1
                """
            ).fetchone()
            if active is not None:
                connection.rollback()
                return None

            pending = connection.execute(
                """
                SELECT id FROM crawler_tasks
                WHERE status = 'pending' AND cancel_requested = 0
                ORDER BY created_at ASC, rowid ASC
                LIMIT 1
                """
            ).fetchone()
            if pending is None:
                connection.rollback()
                return None

            started_at = utc_now()
            updated = connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'running',
                    started_at = COALESCE(started_at, ?),
                    finished_at = NULL,
                    error_message = NULL,
                    pid = NULL
                WHERE id = ? AND status = 'pending' AND cancel_requested = 0
                """,
                (started_at, pending["id"]),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute(
                "SELECT * FROM crawler_tasks WHERE id = ?",
                (pending["id"],),
            ).fetchone()
            connection.commit()
            return _row_to_task(row)
        finally:
            connection.close()

    def set_pid(self, task_id: str, pid: int) -> None:
        self._update_active(task_id, "pid = ?", (pid,))

    def set_waiting_login(self, task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'waiting_login'
                WHERE id = ? AND status = 'running'
                """,
                (task_id,),
            )

    def set_running(self, task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'running'
                WHERE id = ? AND status = 'waiting_login'
                """,
                (task_id,),
            )

    def complete_success(self, task_id: str, actual_count: int) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'succeeded', actual_count = ?, finished_at = ?,
                    error_message = NULL
                WHERE id = ? AND status IN ('running', 'waiting_login')
                """,
                (actual_count, utc_now(), task_id),
            )

    def complete_failure(self, task_id: str, error_message: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'failed', finished_at = ?, error_message = ?
                WHERE id = ? AND status IN ('running', 'waiting_login')
                """,
                (utc_now(), error_message[:2000], task_id),
            )

    def complete_cancelled(self, task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'cancelled', cancel_requested = 1,
                    finished_at = ?, error_message = NULL
                WHERE id = ? AND status IN ('pending', 'running', 'waiting_login')
                """,
                (utc_now(), task_id),
            )

    def request_cancel(self, task_id: str) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            if row["status"] not in CANCELLABLE_STATUSES:
                connection.rollback()
                raise TaskNotCancellableError(
                    f"task in {row['status']} state cannot be cancelled"
                )
            if row["status"] == "pending":
                connection.execute(
                    """
                    UPDATE crawler_tasks
                    SET status = 'cancelled', cancel_requested = 1,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (utc_now(), task_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE crawler_tasks
                    SET cancel_requested = 1
                    WHERE id = ?
                    """,
                    (task_id,),
                )
            updated = connection.execute(
                "SELECT * FROM crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
            return _row_to_task(updated)
        finally:
            connection.close()

    def is_cancel_requested(self, task_id: str) -> bool:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return bool(row and row["cancel_requested"])

    def fail_interrupted_tasks(self) -> int:
        with connect_database(self.database_path) as connection:
            result = connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'failed',
                    finished_at = ?,
                    error_message = 'Crawler task was interrupted by a worker restart'
                WHERE status IN ('running', 'waiting_login')
                """,
                (utc_now(),),
            )
        return result.rowcount

    def _update_active(
        self,
        task_id: str,
        assignment: str,
        values: tuple[object, ...],
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                f"""
                UPDATE crawler_tasks
                SET {assignment}
                WHERE id = ? AND status IN ('running', 'waiting_login')
                """,
                (*values, task_id),
            )
