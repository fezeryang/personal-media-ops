import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.db import connect_database
from app.repositories.crawler_tasks import utc_now
from app.services.scheduling import next_scheduled_time

ACTIVE_TASK_STATUSES = {"pending", "running", "waiting_login"}
TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled"}
PRIVACY_SAFE_CREATOR_ID = re.compile(r"^[0-9a-f]{16}$")


def _new_id() -> str:
    return str(uuid4())


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        raise TypeError("stored schedule config is invalid")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeError("stored schedule config is invalid") from error
    if not isinstance(parsed, dict):
        raise TypeError("stored schedule config is invalid")
    return parsed


class AutomationRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database_path = settings.database_path

    def _subscription_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        include_runs: bool,
    ) -> dict[str, Any]:
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        result["schedule_config"] = _json_object(result["schedule_config"])
        result["platforms"] = [
            dict(item)
            for item in connection.execute(
                """
                SELECT platform, requested_count
                FROM subscription_platforms
                WHERE subscription_id = ?
                ORDER BY position
                """,
                (result["id"],),
            ).fetchall()
        ]
        if include_runs:
            result["runs"] = self._list_runs(
                connection,
                subscription_id=str(result["id"]),
                limit=20,
            )
        return result

    def _list_runs(
        self,
        connection: sqlite3.Connection,
        *,
        subscription_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        runs = connection.execute(
            """
            SELECT * FROM subscription_runs
            WHERE subscription_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (subscription_id, limit),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for run in runs:
            result = dict(run)
            result["platform_results"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT link.platform, link.sequence, link.task_id,
                           task.status AS task_status,
                           link.new_content_count,
                           link.existing_content_count,
                           link.changed_content_count,
                           COALESCE(link.error_summary, task.error_message)
                               AS error_summary
                    FROM subscription_run_tasks link
                    JOIN crawler_tasks task ON task.id = link.task_id
                    WHERE link.run_id = ?
                    ORDER BY link.sequence
                    """,
                    (result["id"],),
                ).fetchall()
            ]
            results.append(result)
        return results

    def get_subscription(
        self,
        *,
        subscription_id: str,
        user_id: str,
        include_runs: bool = True,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
                (subscription_id, user_id),
            ).fetchone()
            return (
                self._subscription_from_row(
                    connection,
                    row,
                    include_runs=include_runs,
                )
                if row is not None
                else None
            )

    def list_subscriptions(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM subscriptions
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                self._subscription_from_row(
                    connection,
                    row,
                    include_runs=False,
                )
                for row in rows
            ]

    def create_subscription(
        self,
        *,
        user_id: str,
        name: str,
        query: str,
        platforms: Sequence[Mapping[str, object]],
        enabled: bool,
        schedule_type: str,
        schedule_config: Mapping[str, object],
        timezone: str,
    ) -> dict[str, Any]:
        identifier = _new_id()
        now_dt = datetime.now(UTC)
        now = _utc(now_dt)
        next_run = (
            next_scheduled_time(
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                timezone_name=timezone,
                after=now_dt,
            )
            if enabled
            else None
        )
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO subscriptions (
                    id, user_id, name, query, enabled, schedule_type,
                    schedule_config, timezone, last_run_at, next_run_at,
                    last_success_at, consecutive_failures, last_error,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, 0, NULL, ?, ?)
                """,
                (
                    identifier,
                    user_id,
                    name,
                    query,
                    int(enabled),
                    schedule_type,
                    json.dumps(schedule_config, separators=(",", ":"), sort_keys=True),
                    timezone,
                    _utc(next_run) if next_run is not None else None,
                    now,
                    now,
                ),
            )
            self._replace_platforms(connection, identifier, platforms)
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (identifier,),
            ).fetchone()
            if row is None:
                raise RuntimeError("created subscription could not be read")
            result = self._subscription_from_row(
                connection,
                row,
                include_runs=False,
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _replace_platforms(
        connection: sqlite3.Connection,
        subscription_id: str,
        platforms: Sequence[Mapping[str, object]],
    ) -> None:
        connection.execute(
            "DELETE FROM subscription_platforms WHERE subscription_id = ?",
            (subscription_id,),
        )
        for position, item in enumerate(platforms):
            connection.execute(
                """
                INSERT INTO subscription_platforms (
                    subscription_id, platform, requested_count, position
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    subscription_id,
                    str(item["platform"]),
                    int(item["requested_count"]),
                    position,
                ),
            )

    def update_subscription(
        self,
        *,
        subscription_id: str,
        user_id: str,
        name: str,
        query: str,
        platforms: Sequence[Mapping[str, object]],
        enabled: bool,
        schedule_type: str,
        schedule_config: Mapping[str, object],
        timezone: str,
    ) -> dict[str, Any] | None:
        now_dt = datetime.now(UTC)
        next_run = (
            next_scheduled_time(
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                timezone_name=timezone,
                after=now_dt,
            )
            if enabled
            else None
        )
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE subscriptions
                SET name = ?, query = ?, enabled = ?, schedule_type = ?,
                    schedule_config = ?, timezone = ?, next_run_at = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    name,
                    query,
                    int(enabled),
                    schedule_type,
                    json.dumps(schedule_config, separators=(",", ":"), sort_keys=True),
                    timezone,
                    _utc(next_run) if next_run is not None else None,
                    utc_now(),
                    subscription_id,
                    user_id,
                ),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            self._replace_platforms(connection, subscription_id, platforms)
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("updated subscription could not be read")
            result = self._subscription_from_row(
                connection,
                row,
                include_runs=False,
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def set_subscription_enabled(
        self,
        *,
        subscription_id: str,
        user_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
                (subscription_id, user_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            next_run = None
            if enabled:
                candidate = next_scheduled_time(
                    schedule_type=str(row["schedule_type"]),
                    schedule_config=_json_object(row["schedule_config"]),
                    timezone_name=str(row["timezone"]),
                    after=datetime.now(UTC),
                )
                next_run = _utc(candidate) if candidate is not None else None
            connection.execute(
                """
                UPDATE subscriptions
                SET enabled = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(enabled), next_run, utc_now(), subscription_id),
            )
            updated = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
            if updated is None:
                raise RuntimeError("subscription disappeared")
            result = self._subscription_from_row(
                connection,
                updated,
                include_runs=False,
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _insert_task(
        self,
        connection: sqlite3.Connection,
        *,
        platform: str,
        mode: str,
        keywords: str | None,
        creator_ids: Sequence[str],
        creator_urls: Sequence[str] = (),
        requested_count: int,
        created_at: str,
    ) -> str:
        task_id = _new_id()
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
            VALUES (
                ?, ?, ?, ?, 'qrcode', 'pending', ?, 0, ?, ?, ?,
                NULL, NULL, ?, NULL, NULL, 0, '[]', '[]', ?, ?,
                NULL, NULL, 0, 0
            )
            """,
            (
                task_id,
                platform,
                mode,
                keywords,
                requested_count,
                str(self.settings.output_root / "tasks" / task_id),
                str(self.settings.log_root / "crawler" / f"{task_id}.log"),
                str(self.settings.qrcode_root / f"{task_id}.png"),
                created_at,
                json.dumps(list(creator_ids), separators=(",", ":")),
                json.dumps(list(creator_urls), separators=(",", ":")),
            ),
        )
        return task_id

    @staticmethod
    def _stored_creator_targets(
        connection: sqlite3.Connection,
        *,
        creator_id: str,
        source_creator_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        provenance = connection.execute(
            """
            SELECT task.creator_ids, task.creator_urls
            FROM crawl_task_entities entity
            JOIN crawler_tasks task ON task.id = entity.task_id
            WHERE entity.entity_type = 'creator'
              AND entity.entity_id = ?
              AND task.crawler_type = 'creator'
              AND task.status = 'succeeded'
            ORDER BY COALESCE(task.finished_at, task.created_at) DESC
            LIMIT 1
            """,
            (creator_id,),
        ).fetchone()
        if provenance is not None:
            creator_ids = tuple(json.loads(str(provenance["creator_ids"])))
            creator_urls = tuple(json.loads(str(provenance["creator_urls"])))
            if creator_ids or creator_urls:
                return creator_ids, creator_urls
        if not PRIVACY_SAFE_CREATOR_ID.fullmatch(source_creator_id):
            return (source_creator_id,), ()
        return (), ()

    def creator_watch_target_available(self, creator_id: str) -> bool:
        with connect_database(self.database_path) as connection:
            creator = connection.execute(
                """
                SELECT source_creator_id
                FROM library_creators
                WHERE id = ?
                """,
                (creator_id,),
            ).fetchone()
            if creator is None:
                return False
            creator_ids, creator_urls = self._stored_creator_targets(
                connection,
                creator_id=creator_id,
                source_creator_id=str(creator["source_creator_id"]),
            )
            return bool(creator_ids or creator_urls)

    def _create_subscription_run(
        self,
        connection: sqlite3.Connection,
        *,
        subscription: sqlite3.Row,
        scheduled_for: str,
        trigger: str,
    ) -> str | None:
        run_id = _new_id()
        created_at = utc_now()
        inserted = connection.execute(
            """
            INSERT OR IGNORE INTO subscription_runs (
                id, subscription_id, scheduled_for, trigger, status,
                started_at, finished_at, new_content_count,
                existing_content_count, changed_content_count,
                error_summary, created_at
            )
            VALUES (?, ?, ?, ?, 'queued', NULL, NULL, 0, 0, 0, NULL, ?)
            """,
            (
                run_id,
                subscription["id"],
                scheduled_for,
                trigger,
                created_at,
            ),
        )
        if inserted.rowcount != 1:
            return None
        platforms = connection.execute(
            """
            SELECT platform, requested_count
            FROM subscription_platforms
            WHERE subscription_id = ?
            ORDER BY position
            """,
            (subscription["id"],),
        ).fetchall()
        for sequence, platform in enumerate(platforms):
            task_id = self._insert_task(
                connection,
                platform=str(platform["platform"]),
                mode="search",
                keywords=str(subscription["query"]),
                creator_ids=(),
                requested_count=int(platform["requested_count"]),
                created_at=utc_now(),
            )
            connection.execute(
                """
                INSERT INTO subscription_run_tasks (
                    run_id, task_id, platform, sequence, new_content_count,
                    existing_content_count, changed_content_count, error_summary
                )
                VALUES (?, ?, ?, ?, 0, 0, 0, NULL)
                """,
                (run_id, task_id, platform["platform"], sequence),
            )
        connection.execute(
            """
            UPDATE subscriptions
            SET last_run_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (scheduled_for, created_at, subscription["id"]),
        )
        return run_id

    def create_manual_subscription_run(
        self,
        *,
        subscription_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            subscription = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
                (subscription_id, user_id),
            ).fetchone()
            if subscription is None:
                connection.rollback()
                return None
            active = connection.execute(
                """
                SELECT 1 FROM subscription_runs
                WHERE subscription_id = ? AND status IN ('queued', 'running')
                LIMIT 1
                """,
                (subscription_id,),
            ).fetchone()
            if active is not None:
                raise sqlite3.IntegrityError("subscription already has an active run")
            scheduled_for = utc_now()
            run_id = self._create_subscription_run(
                connection,
                subscription=subscription,
                scheduled_for=scheduled_for,
                trigger="manual",
            )
            if run_id is None:
                raise sqlite3.IntegrityError("subscription run slot already exists")
            result = self._list_runs(
                connection,
                subscription_id=subscription_id,
                limit=1,
            )[0]
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def schedule_due_subscriptions(self, now: datetime) -> int:
        now_text = _utc(now)
        connection = connect_database(self.database_path)
        created = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            due = connection.execute(
                """
                SELECT * FROM subscriptions
                WHERE enabled = 1 AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                ORDER BY next_run_at, created_at
                """,
                (now_text,),
            ).fetchall()
            for subscription in due:
                scheduled_for = str(subscription["next_run_at"])
                run_id = self._create_subscription_run(
                    connection,
                    subscription=subscription,
                    scheduled_for=scheduled_for,
                    trigger="scheduled",
                )
                config = _json_object(subscription["schedule_config"])
                next_run = next_scheduled_time(
                    schedule_type=str(subscription["schedule_type"]),
                    schedule_config=config,
                    timezone_name=str(subscription["timezone"]),
                    after=_parse(scheduled_for),
                )
                connection.execute(
                    """
                    UPDATE subscriptions
                    SET next_run_at = ?, updated_at = ?
                    WHERE id = ? AND next_run_at = ?
                    """,
                    (
                        _utc(next_run) if next_run is not None else None,
                        utc_now(),
                        subscription["id"],
                        scheduled_for,
                    ),
                )
                if run_id is not None:
                    created += 1
            connection.commit()
            return created
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def reconcile_subscription_runs(self) -> None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            runs = connection.execute(
                """
                SELECT * FROM subscription_runs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at
                """
            ).fetchall()
            for run in runs:
                tasks = connection.execute(
                    """
                    SELECT task.status, task.started_at, task.finished_at,
                           task.error_message, link.new_content_count,
                           link.existing_content_count,
                           link.changed_content_count
                    FROM subscription_run_tasks link
                    JOIN crawler_tasks task ON task.id = link.task_id
                    WHERE link.run_id = ?
                    ORDER BY link.sequence
                    """,
                    (run["id"],),
                ).fetchall()
                if not tasks:
                    continue
                statuses = [str(task["status"]) for task in tasks]
                if any(status in ACTIVE_TASK_STATUSES for status in statuses):
                    if any(status != "pending" for status in statuses):
                        started = min(
                            (
                                str(task["started_at"])
                                for task in tasks
                                if task["started_at"] is not None
                            ),
                            default=None,
                        )
                        connection.execute(
                            """
                            UPDATE subscription_runs
                            SET status = 'running',
                                started_at = COALESCE(started_at, ?)
                            WHERE id = ?
                            """,
                            (started, run["id"]),
                        )
                    continue
                if not all(status in TERMINAL_TASK_STATUSES for status in statuses):
                    continue
                succeeded = statuses.count("succeeded")
                status = (
                    "succeeded"
                    if succeeded == len(statuses)
                    else "partial"
                    if succeeded
                    else "cancelled"
                    if set(statuses) == {"cancelled"}
                    else "failed"
                )
                errors = [
                    str(task["error_message"])
                    for task in tasks
                    if task["error_message"]
                ]
                finished_at = max(
                    (
                        str(task["finished_at"])
                        for task in tasks
                        if task["finished_at"] is not None
                    ),
                    default=utc_now(),
                )
                counts = (
                    sum(int(task["new_content_count"]) for task in tasks),
                    sum(int(task["existing_content_count"]) for task in tasks),
                    sum(int(task["changed_content_count"]) for task in tasks),
                )
                error_summary = "; ".join(errors)[:2000] or None
                connection.execute(
                    """
                    UPDATE subscription_runs
                    SET status = ?, finished_at = ?, new_content_count = ?,
                        existing_content_count = ?, changed_content_count = ?,
                        error_summary = ?
                    WHERE id = ?
                    """,
                    (status, finished_at, *counts, error_summary, run["id"]),
                )
                if status == "succeeded":
                    connection.execute(
                        """
                        UPDATE subscriptions
                        SET last_success_at = ?, consecutive_failures = 0,
                            last_error = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (finished_at, utc_now(), run["subscription_id"]),
                    )
                else:
                    subscription = connection.execute(
                        "SELECT * FROM subscriptions WHERE id = ?",
                        (run["subscription_id"],),
                    ).fetchone()
                    if subscription is None:
                        continue
                    failures = int(subscription["consecutive_failures"]) + 1
                    next_run_at = subscription["next_run_at"]
                    if next_run_at is not None:
                        delay_hours = min(6 * (2 ** (failures - 1)), 24)
                        minimum = datetime.now(UTC) + timedelta(hours=delay_hours)
                        if _parse(str(next_run_at)) < minimum:
                            next_run_at = _utc(minimum)
                    connection.execute(
                        """
                        UPDATE subscriptions
                        SET consecutive_failures = ?, last_error = ?,
                            next_run_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            failures,
                            error_summary or f"subscription run {status}",
                            next_run_at,
                            utc_now(),
                            run["subscription_id"],
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_watch(
        self,
        *,
        user_id: str,
        creator_id: str,
        enabled: bool,
        check_frequency: str,
        requested_count: int,
        timezone: str,
    ) -> dict[str, Any]:
        identifier = _new_id()
        now_dt = datetime.now(UTC)
        now = _utc(now_dt)
        next_check = (
            self._next_watch_time(check_frequency, timezone, now_dt)
            if enabled
            else None
        )
        with connect_database(self.database_path) as connection:
            creator = connection.execute(
                "SELECT platform FROM library_creators WHERE id = ?",
                (creator_id,),
            ).fetchone()
            if creator is None:
                raise LookupError("creator not found")
            connection.execute(
                """
                INSERT INTO creator_watchlist (
                    id, user_id, creator_id, platform, enabled,
                    check_frequency, timezone, requested_count,
                    last_checked_at, next_check_at, last_success_at,
                    consecutive_failures, last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, 0, NULL, ?, ?)
                """,
                (
                    identifier,
                    user_id,
                    creator_id,
                    creator["platform"],
                    int(enabled),
                    check_frequency,
                    timezone,
                    requested_count,
                    _utc(next_check) if next_check else None,
                    now,
                    now,
                ),
            )
        watch = self.get_watch(identifier, user_id=user_id)
        if watch is None:
            raise RuntimeError("created watch could not be read")
        return watch

    @staticmethod
    def _next_watch_time(
        frequency: str,
        timezone: str,
        after: datetime,
    ) -> datetime:
        schedule_config: dict[str, object] = {}
        if frequency == "daily":
            schedule_config["time_of_day"] = "09:00"
        elif frequency == "weekly":
            schedule_config.update({"time_of_day": "09:00", "weekday": 0})
        result = next_scheduled_time(
            schedule_type=frequency,
            schedule_config=schedule_config,
            timezone_name=timezone,
            after=after,
        )
        if result is None:
            raise RuntimeError("watch schedule unexpectedly has no next run")
        return result

    def get_watch(self, watch_id: str, *, user_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT watch.*, creator.display_name AS creator_name
                FROM creator_watchlist watch
                JOIN library_creators creator ON creator.id = watch.creator_id
                WHERE watch.id = ? AND watch.user_id = ?
                """,
                (watch_id, user_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["enabled"] = bool(result["enabled"])
            result["runs"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT * FROM creator_watch_runs
                    WHERE watch_id = ?
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (watch_id,),
                ).fetchall()
            ]
            return result

    def list_watches(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            ids = [
                str(row["id"])
                for row in connection.execute(
                    """
                    SELECT id FROM creator_watchlist
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (user_id,),
                ).fetchall()
            ]
        return [
            watch
            for watch_id in ids
            if (watch := self.get_watch(watch_id, user_id=user_id)) is not None
        ]

    def create_manual_watch_run(
        self,
        *,
        watch_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            watch = connection.execute(
                """
                SELECT watch.*, creator.source_creator_id
                FROM creator_watchlist watch
                JOIN library_creators creator ON creator.id = watch.creator_id
                WHERE watch.id = ? AND watch.user_id = ?
                """,
                (watch_id, user_id),
            ).fetchone()
            if watch is None:
                connection.rollback()
                return None
            active = connection.execute(
                """
                SELECT 1 FROM creator_watch_runs
                WHERE watch_id = ? AND status IN ('queued', 'running')
                LIMIT 1
                """,
                (watch_id,),
            ).fetchone()
            if active is not None:
                raise sqlite3.IntegrityError("watch already has an active run")
            scheduled_for = utc_now()
            run_id = self._create_watch_run(
                connection,
                watch=watch,
                scheduled_for=scheduled_for,
                trigger="manual",
            )
            if run_id is None:
                raise sqlite3.IntegrityError("watch run slot already exists")
            connection.execute(
                """
                UPDATE creator_watchlist
                SET last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (scheduled_for, scheduled_for, watch_id),
            )
            row = connection.execute(
                "SELECT * FROM creator_watch_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("created watch run could not be read")
            result = dict(row)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_watch_run(
        self,
        connection: sqlite3.Connection,
        *,
        watch: sqlite3.Row,
        scheduled_for: str,
        trigger: str,
    ) -> str | None:
        active = connection.execute(
            """
            SELECT 1 FROM creator_watch_runs
            WHERE watch_id = ? AND status IN ('queued', 'running')
            LIMIT 1
            """,
            (watch["id"],),
        ).fetchone()
        if active is not None:
            return None
        creator_ids, creator_urls = self._stored_creator_targets(
            connection,
            creator_id=str(watch["creator_id"]),
            source_creator_id=str(watch["source_creator_id"]),
        )
        if not creator_ids and not creator_urls:
            raise sqlite3.IntegrityError(
                "creator has no reusable platform target"
            )
        task_id = self._insert_task(
            connection,
            platform=str(watch["platform"]),
            mode="creator",
            keywords=None,
            creator_ids=creator_ids,
            creator_urls=creator_urls,
            requested_count=int(watch["requested_count"]),
            created_at=scheduled_for,
        )
        run_id = _new_id()
        inserted = connection.execute(
            """
            INSERT OR IGNORE INTO creator_watch_runs (
                id, watch_id, scheduled_for, trigger, task_id, status,
                started_at, finished_at, new_content_count,
                existing_content_count, changed_content_count,
                error_summary, created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, 'queued', NULL, NULL,
                0, 0, 0, NULL, ?
            )
            """,
            (
                run_id,
                watch["id"],
                scheduled_for,
                trigger,
                task_id,
                utc_now(),
            ),
        )
        if inserted.rowcount != 1:
            connection.execute(
                "DELETE FROM crawler_tasks WHERE id = ?",
                (task_id,),
            )
            return None
        connection.execute(
            """
            UPDATE creator_watchlist
            SET last_checked_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (scheduled_for, utc_now(), watch["id"]),
        )
        return run_id

    def set_watch_enabled(
        self,
        *,
        watch_id: str,
        user_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            watch = connection.execute(
                """
                SELECT watch.*, creator.source_creator_id
                FROM creator_watchlist watch
                JOIN library_creators creator ON creator.id = watch.creator_id
                WHERE watch.id = ? AND watch.user_id = ?
                """,
                (watch_id, user_id),
            ).fetchone()
            if watch is None:
                connection.rollback()
                return None
            next_check = None
            if enabled:
                next_check = _utc(
                    self._next_watch_time(
                        str(watch["check_frequency"]),
                        str(watch["timezone"]),
                        datetime.now(UTC),
                    )
                )
            connection.execute(
                """
                UPDATE creator_watchlist
                SET enabled = ?, next_check_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(enabled), next_check, utc_now(), watch_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get_watch(watch_id, user_id=user_id)

    def schedule_due_watches(self, now: datetime) -> int:
        now_text = _utc(now)
        connection = connect_database(self.database_path)
        created = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            watches = connection.execute(
                """
                SELECT watch.*, creator.source_creator_id
                FROM creator_watchlist watch
                JOIN library_creators creator ON creator.id = watch.creator_id
                WHERE watch.enabled = 1
                  AND watch.next_check_at IS NOT NULL
                  AND watch.next_check_at <= ?
                ORDER BY watch.next_check_at, watch.created_at
                """,
                (now_text,),
            ).fetchall()
            for watch in watches:
                scheduled_for = str(watch["next_check_at"])
                run_id = self._create_watch_run(
                    connection,
                    watch=watch,
                    scheduled_for=scheduled_for,
                    trigger="scheduled",
                )
                next_check = self._next_watch_time(
                    str(watch["check_frequency"]),
                    str(watch["timezone"]),
                    _parse(scheduled_for),
                )
                connection.execute(
                    """
                    UPDATE creator_watchlist
                    SET next_check_at = ?, updated_at = ?
                    WHERE id = ? AND next_check_at = ?
                    """,
                    (
                        _utc(next_check),
                        utc_now(),
                        watch["id"],
                        scheduled_for,
                    ),
                )
                if run_id is not None:
                    created += 1
            connection.commit()
            return created
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def reconcile_watch_runs(self) -> None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            runs = connection.execute(
                """
                SELECT run.*, task.status AS task_status,
                       task.started_at AS task_started_at,
                       task.finished_at AS task_finished_at,
                       task.error_message AS task_error
                FROM creator_watch_runs run
                JOIN crawler_tasks task ON task.id = run.task_id
                WHERE run.status IN ('queued', 'running')
                """
            ).fetchall()
            for run in runs:
                task_status = str(run["task_status"])
                if task_status in ACTIVE_TASK_STATUSES:
                    if task_status != "pending":
                        connection.execute(
                            """
                            UPDATE creator_watch_runs
                            SET status = 'running',
                                started_at = COALESCE(started_at, ?)
                            WHERE id = ?
                            """,
                            (run["task_started_at"], run["id"]),
                        )
                    continue
                status = (
                    "succeeded"
                    if task_status == "succeeded"
                    else "cancelled"
                    if task_status == "cancelled"
                    else "failed"
                )
                error = run["task_error"]
                connection.execute(
                    """
                    UPDATE creator_watch_runs
                    SET status = ?, finished_at = ?, error_summary = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        run["task_finished_at"] or utc_now(),
                        error,
                        run["id"],
                    ),
                )
                if status == "succeeded":
                    connection.execute(
                        """
                        UPDATE creator_watchlist
                        SET last_success_at = ?, consecutive_failures = 0,
                            last_error = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            run["task_finished_at"] or utc_now(),
                            utc_now(),
                            run["watch_id"],
                        ),
                    )
                else:
                    watch = connection.execute(
                        "SELECT * FROM creator_watchlist WHERE id = ?",
                        (run["watch_id"],),
                    ).fetchone()
                    failures = (
                        int(watch["consecutive_failures"]) + 1
                        if watch is not None
                        else 1
                    )
                    next_check = watch["next_check_at"] if watch is not None else None
                    if next_check is not None:
                        delay_hours = min(6 * (2 ** (failures - 1)), 24)
                        minimum = datetime.now(UTC) + timedelta(hours=delay_hours)
                        if _parse(str(next_check)) < minimum:
                            next_check = _utc(minimum)
                    connection.execute(
                        """
                        UPDATE creator_watchlist
                        SET consecutive_failures = ?, last_error = ?,
                            next_check_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            failures,
                            error or f"watch run {status}",
                            next_check,
                            utc_now(),
                            run["watch_id"],
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
