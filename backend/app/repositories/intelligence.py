import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import connect_database
from app.repositories.crawler_tasks import utc_now
from app.services.scheduling import next_scheduled_time


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _read_json(value: object) -> object:
    if not isinstance(value, str):
        raise TypeError("stored intelligence JSON is invalid")
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeError("stored intelligence JSON is invalid") from error


class BriefConflictError(RuntimeError):
    pass


class IntelligenceRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def source_topics(self) -> list[str]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT source_keyword AS topic
                FROM library_contents
                WHERE source_keyword IS NOT NULL
                  AND length(trim(source_keyword)) > 0
                UNION
                SELECT query AS topic
                FROM subscriptions
                WHERE length(trim(query)) > 0
                ORDER BY topic COLLATE NOCASE
                """
            ).fetchall()
        return [str(row["topic"]) for row in rows]

    def topic_contents(
        self,
        *,
        topic: str,
        window_start: str,
        window_end: str,
    ) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, platform, view_count, like_count,
                           favorite_count, comment_count, share_count,
                           first_collected_at
                    FROM library_contents
                    WHERE source_keyword = ?
                      AND first_collected_at >= ?
                      AND first_collected_at < ?
                    ORDER BY first_collected_at DESC, id DESC
                    """,
                    (topic, window_start, window_end),
                ).fetchall()
            ]

    def topic_engagement_change(
        self,
        *,
        topic: str,
        window_start: str,
        window_end: str,
    ) -> float:
        metric_columns = (
            "view_count",
            "like_count",
            "favorite_count",
            "comment_count",
            "share_count",
        )
        with connect_database(self.database_path) as connection:
            content_ids = [
                str(row["id"])
                for row in connection.execute(
                    """
                    SELECT id FROM library_contents
                    WHERE source_keyword = ?
                      AND first_collected_at < ?
                    """,
                    (topic, window_end),
                ).fetchall()
            ]
            initial_total = 0
            final_total = 0
            comparable = 0
            for content_id in content_ids:
                snapshots = connection.execute(
                    """
                    SELECT * FROM content_metric_snapshots
                    WHERE content_id = ? AND captured_at >= ?
                      AND captured_at <= ?
                    ORDER BY captured_at ASC
                    """,
                    (content_id, window_start, window_end),
                ).fetchall()
                if len(snapshots) < 2:
                    continue
                first_total = sum(
                    int(snapshots[0][column] or 0)
                    for column in metric_columns
                )
                last_total = sum(
                    int(snapshots[-1][column] or 0)
                    for column in metric_columns
                )
                initial_total += first_total
                final_total += last_total
                comparable += 1
        if comparable == 0:
            return 0
        return max(final_total - initial_total, 0) / max(initial_total, 1)

    def upsert_trend(
        self,
        *,
        topic: str,
        window_start: str,
        window_end: str,
        score: float,
        volume_score: float,
        velocity_score: float,
        cross_platform_score: float,
        engagement_score: float,
        platforms: Sequence[str],
        content_ids: Sequence[str],
        explanation: str,
        evidence: dict[str, object],
        status: str,
        formula_version: str,
    ) -> dict[str, Any]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT id FROM trend_signals
                WHERE topic = ? AND window_start = ? AND window_end = ?
                  AND formula_version = ?
                """,
                (topic, window_start, window_end, formula_version),
            ).fetchone()
            identifier = str(existing["id"]) if existing else str(uuid4())
            created_at = utc_now()
            connection.execute(
                """
                INSERT INTO trend_signals (
                    id, topic, window_start, window_end, score, volume_score,
                    velocity_score, cross_platform_score, engagement_score,
                    platforms, explanation, evidence, status, formula_version,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    topic, window_start, window_end, formula_version
                ) DO UPDATE SET
                    score = excluded.score,
                    volume_score = excluded.volume_score,
                    velocity_score = excluded.velocity_score,
                    cross_platform_score = excluded.cross_platform_score,
                    engagement_score = excluded.engagement_score,
                    platforms = excluded.platforms,
                    explanation = excluded.explanation,
                    evidence = excluded.evidence,
                    status = excluded.status,
                    created_at = excluded.created_at
                """,
                (
                    identifier,
                    topic,
                    window_start,
                    window_end,
                    score,
                    volume_score,
                    velocity_score,
                    cross_platform_score,
                    engagement_score,
                    _json(sorted(set(platforms))),
                    explanation,
                    _json(evidence),
                    status,
                    formula_version,
                    created_at,
                ),
            )
            connection.execute(
                "DELETE FROM trend_signal_contents WHERE trend_id = ?",
                (identifier,),
            )
            for content_id in dict.fromkeys(content_ids):
                connection.execute(
                    """
                    INSERT INTO trend_signal_contents (trend_id, content_id)
                    VALUES (?, ?)
                    """,
                    (identifier, content_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        trend = self.get_trend(identifier)
        if trend is None:
            raise RuntimeError("saved trend could not be read")
        return trend

    @staticmethod
    def _trend_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        result = dict(row)
        platforms = _read_json(result["platforms"])
        evidence = _read_json(result["evidence"])
        if not isinstance(platforms, list) or not isinstance(evidence, dict):
            raise TypeError("stored trend data is invalid")
        result["platforms"] = platforms
        result["evidence"] = evidence
        result["content_ids"] = [
            str(item["content_id"])
            for item in connection.execute(
                """
                SELECT content_id FROM trend_signal_contents
                WHERE trend_id = ?
                ORDER BY content_id
                """,
                (result["id"],),
            ).fetchall()
        ]
        return result

    def get_trend(self, trend_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM trend_signals WHERE id = ?",
                (trend_id,),
            ).fetchone()
            return self._trend_row(connection, row) if row is not None else None

    def list_trends(
        self,
        *,
        window_end_before: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, object]:
        clause = "WHERE window_end <= ?" if window_end_before else ""
        values: list[object] = (
            [window_end_before, limit + 1, offset]
            if window_end_before
            else [limit + 1, offset]
        )
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM trend_signals
                {clause}
                ORDER BY window_end DESC, score DESC, topic COLLATE NOCASE
                LIMIT ? OFFSET ?
                """,
                values,
            ).fetchall()
            has_more = len(rows) > limit
            items = [
                self._trend_row(connection, row)
                for row in rows[:limit]
            ]
        return {
            "items": items,
            "offset": offset,
            "limit": limit,
            "next_offset": offset + len(items),
            "has_more": has_more,
        }

    def brief_source_contents(
        self,
        *,
        window_start: str,
        window_end: str,
    ) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, platform, title, source_url, source_keyword,
                           author_source_id, author_name, view_count,
                           like_count, favorite_count, comment_count,
                           share_count, is_favorite, first_collected_at
                    FROM library_contents
                    WHERE first_collected_at >= ? AND first_collected_at < ?
                    ORDER BY first_collected_at DESC, id DESC
                    LIMIT 100
                    """,
                    (window_start, window_end),
                ).fetchall()
            ]

    def brief_source_content_count(
        self,
        *,
        window_start: str,
        window_end: str,
    ) -> int:
        with connect_database(self.database_path) as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM library_contents
                    WHERE first_collected_at >= ? AND first_collected_at < ?
                    """,
                    (window_start, window_end),
                ).fetchone()[0]
            )

    def brief_source_failures(
        self,
        *,
        window_start: str,
        window_end: str,
    ) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, subscription_id, scheduled_for, status,
                           error_summary
                    FROM subscription_runs
                    WHERE scheduled_for >= ? AND scheduled_for < ?
                      AND status IN ('partial', 'failed')
                    ORDER BY scheduled_for DESC
                    LIMIT 20
                    """,
                    (window_start, window_end),
                ).fetchall()
            ]

    def brief_source_creator_activity(
        self,
        *,
        window_start: str,
        window_end: str,
    ) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT run.id, run.watch_id, run.new_content_count,
                           run.existing_content_count,
                           run.changed_content_count, run.finished_at,
                           creator.id AS creator_id,
                           creator.display_name AS creator_name,
                           creator.platform, creator.profile_url
                    FROM creator_watch_runs run
                    JOIN creator_watchlist watch ON watch.id = run.watch_id
                    JOIN library_creators creator
                      ON creator.id = watch.creator_id
                    WHERE run.status = 'succeeded'
                      AND run.finished_at >= ? AND run.finished_at < ?
                    ORDER BY run.finished_at DESC
                    LIMIT 20
                    """,
                    (window_start, window_end),
                ).fetchall()
            ]

    def create_brief(
        self,
        *,
        user_id: str,
        window_start: str,
        window_end: str,
        timezone: str,
        regenerate: bool,
        items: Sequence[dict[str, object]],
    ) -> dict[str, Any]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT id, version FROM briefs
                WHERE user_id = ? AND window_start = ? AND window_end = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id, window_start, window_end),
            ).fetchone()
            if existing is not None and not regenerate:
                raise BriefConflictError("brief already exists for this window")
            version = int(existing["version"]) + 1 if existing else 1
            if existing is not None:
                connection.execute(
                    """
                    UPDATE briefs SET status = 'superseded'
                    WHERE user_id = ? AND window_start = ? AND window_end = ?
                      AND status = 'ready'
                    """,
                    (user_id, window_start, window_end),
                )
            brief_id = str(uuid4())
            created_at = utc_now()
            connection.execute(
                """
                INSERT INTO briefs (
                    id, user_id, window_start, window_end, timezone, version,
                    generator, ai_provider, status, created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, 'deterministic', 'disabled',
                    'ready', ?
                )
                """,
                (
                    brief_id,
                    user_id,
                    window_start,
                    window_end,
                    timezone,
                    version,
                    created_at,
                ),
            )
            for position, item in enumerate(items):
                item_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO brief_items (
                        id, brief_id, section, conclusion_type, title, body,
                        position, evidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        brief_id,
                        item["section"],
                        item["conclusion_type"],
                        item["title"],
                        item["body"],
                        position,
                        _json(item.get("evidence", {})),
                    ),
                )
                for content_id in dict.fromkeys(item.get("content_ids", [])):
                    connection.execute(
                        """
                        INSERT INTO brief_item_contents (
                            brief_item_id, content_id
                        )
                        VALUES (?, ?)
                        """,
                        (item_id, content_id),
                    )
                for trend_id in dict.fromkeys(item.get("trend_ids", [])):
                    connection.execute(
                        """
                        INSERT INTO brief_item_trends (
                            brief_item_id, trend_id
                        )
                        VALUES (?, ?)
                        """,
                        (item_id, trend_id),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        result = self.get_brief(brief_id, user_id=user_id)
        if result is None:
            raise RuntimeError("created brief could not be read")
        return result

    @staticmethod
    def _brief_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        result = dict(row)
        items: list[dict[str, Any]] = []
        content_evidence: set[str] = set()
        trend_evidence: set[str] = set()
        for item_row in connection.execute(
            """
            SELECT * FROM brief_items
            WHERE brief_id = ?
            ORDER BY position
            """,
            (result["id"],),
        ).fetchall():
            item = dict(item_row)
            evidence = _read_json(item["evidence"])
            if not isinstance(evidence, dict):
                raise TypeError("stored brief evidence is invalid")
            item["evidence"] = evidence
            item["content_ids"] = [
                str(link["content_id"])
                for link in connection.execute(
                    """
                    SELECT content_id FROM brief_item_contents
                    WHERE brief_item_id = ? ORDER BY content_id
                    """,
                    (item["id"],),
                ).fetchall()
            ]
            item["trend_ids"] = [
                str(link["trend_id"])
                for link in connection.execute(
                    """
                    SELECT trend_id FROM brief_item_trends
                    WHERE brief_item_id = ? ORDER BY trend_id
                    """,
                    (item["id"],),
                ).fetchall()
            ]
            content_evidence.update(item["content_ids"])
            trend_evidence.update(item["trend_ids"])
            items.append(item)
        result["items"] = items
        result["evidence_count"] = len(content_evidence) + len(trend_evidence)
        return result

    def get_brief(
        self,
        brief_id: str,
        *,
        user_id: str,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM briefs WHERE id = ? AND user_id = ?",
                (brief_id, user_id),
            ).fetchone()
            return self._brief_row(connection, row) if row is not None else None

    def get_latest_brief(self, *, user_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM briefs
                WHERE user_id = ? AND status = 'ready'
                ORDER BY window_end DESC, version DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return self._brief_row(connection, row) if row is not None else None

    def get_brief_schedule(self, *, user_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM brief_schedules WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result.pop("user_id", None)
        result["enabled"] = bool(result["enabled"])
        return result

    def set_brief_schedule(
        self,
        *,
        user_id: str,
        enabled: bool,
        timezone: str,
        time_of_day: str,
    ) -> dict[str, Any]:
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat().replace("+00:00", "Z")
        next_run = (
            next_scheduled_time(
                schedule_type="daily",
                schedule_config={"time_of_day": time_of_day},
                timezone_name=timezone,
                after=now_dt,
            )
            if enabled
            else None
        )
        next_run_text = (
            next_run.isoformat().replace("+00:00", "Z")
            if next_run is not None
            else None
        )
        with connect_database(self.database_path) as connection:
            existing = connection.execute(
                "SELECT id, created_at FROM brief_schedules WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            identifier = str(existing["id"]) if existing else str(uuid4())
            created_at = str(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO brief_schedules (
                    id, user_id, enabled, timezone, time_of_day,
                    last_run_at, next_run_at, consecutive_failures,
                    last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, 0, NULL, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    timezone = excluded.timezone,
                    time_of_day = excluded.time_of_day,
                    next_run_at = excluded.next_run_at,
                    consecutive_failures = 0,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    identifier,
                    user_id,
                    int(enabled),
                    timezone,
                    time_of_day,
                    next_run_text,
                    created_at,
                    now,
                ),
            )
        result = self.get_brief_schedule(user_id=user_id)
        if result is None:
            raise RuntimeError("saved brief schedule could not be read")
        return result

    def claim_due_brief_schedules(
        self,
        *,
        now: datetime,
    ) -> list[dict[str, Any]]:
        now_text = now.astimezone(UTC).isoformat().replace("+00:00", "Z")
        connection = connect_database(self.database_path)
        claimed: list[dict[str, Any]] = []
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT * FROM brief_schedules
                WHERE enabled = 1 AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                ORDER BY next_run_at
                """,
                (now_text,),
            ).fetchall()
            for row in rows:
                scheduled_for = str(row["next_run_at"])
                next_run = next_scheduled_time(
                    schedule_type="daily",
                    schedule_config={"time_of_day": str(row["time_of_day"])},
                    timezone_name=str(row["timezone"]),
                    after=datetime.fromisoformat(scheduled_for),
                )
                next_run_text = (
                    next_run.isoformat().replace("+00:00", "Z")
                    if next_run is not None
                    else None
                )
                updated = connection.execute(
                    """
                    UPDATE brief_schedules
                    SET last_run_at = ?, next_run_at = ?, updated_at = ?
                    WHERE id = ? AND next_run_at = ?
                    """,
                    (
                        scheduled_for,
                        next_run_text,
                        utc_now(),
                        row["id"],
                        scheduled_for,
                    ),
                )
                if updated.rowcount == 1:
                    item = dict(row)
                    item["scheduled_for"] = scheduled_for
                    claimed.append(item)
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_brief_schedule_outcome(
        self,
        *,
        schedule_id: str,
        error: str | None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            if error is None:
                connection.execute(
                    """
                    UPDATE brief_schedules
                    SET consecutive_failures = 0, last_error = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (utc_now(), schedule_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE brief_schedules
                    SET consecutive_failures = consecutive_failures + 1,
                        last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (error[:2000], utc_now(), schedule_id),
                )
