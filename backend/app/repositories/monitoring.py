from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import connect_database
from app.services.scheduling import next_scheduled_time


class MonitoringNotFound(KeyError):
    pass


class MonitoringConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json(value: object, default: object) -> object:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _bool(value: object) -> bool:
    return bool(int(value or 0))


def _new_id() -> str:
    return str(uuid.uuid4())


def _next_run(schedule_type: str, config: Mapping[str, object], after: datetime) -> str | None:
    if schedule_type == "manual":
        return None
    if schedule_type == "custom":
        interval_days = int(config.get("interval_days", 1))
        if not 1 <= interval_days <= 7:
            raise ValueError("custom monitoring schedule must be between 1 and 7 days")
        return (after.astimezone(UTC) + timedelta(days=interval_days)).isoformat().replace("+00:00", "Z")
    # Monitoring has one safe daily/weekly cadence and uses the existing DST-aware scheduler.
    timezone = str(config.get("timezone") or "Asia/Shanghai")
    schedule_config = dict(config)
    schedule_config.setdefault("time_of_day", "09:00")
    if schedule_type == "weekly":
        schedule_config.setdefault("weekday", 0)
    return (
        next_scheduled_time(
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            timezone_name=timezone,
            after=after,
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


class MonitoringRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @staticmethod
    def _decode_mission(row: sqlite3.Row, connection: sqlite3.Connection, *, detail: bool) -> dict[str, object]:
        item = dict(row)
        item.pop("owner_id", None)
        item["platforms"] = list(_json(item.pop("platforms_json", "[]"), []))
        item["budget"] = dict(_json(item.pop("budget_json", "{}"), {}))
        item["understanding"] = dict(_json(item.pop("understanding_json", "{}"), {}))
        item["schedule_config"] = dict(_json(item.pop("schedule_config_json", "{}"), {}))
        targets = connection.execute(
            "SELECT * FROM monitoring_targets WHERE mission_id = ? ORDER BY created_at, id",
            (item["id"],),
        ).fetchall()
        item["targets"] = [dict(target) for target in targets]
        if not detail:
            for field in (
                "importance_rule",
                "ignored_content_rule",
                "consecutive_failures",
                "last_error",
                "targets",
            ):
                item.pop(field, None)
        if detail:
            latest = connection.execute(
                """
                SELECT id, run_id, change_type, title, summary, attention_level,
                       relevance_score, novelty_score, updated_at
                FROM monitoring_changes
                WHERE mission_id = ? AND state != 'ignored'
                ORDER BY updated_at DESC, id DESC LIMIT 1
                """,
                (item["id"],),
            ).fetchone()
            item["latest_change"] = dict(latest) if latest is not None else None
        else:
            item["latest_change"] = None
        return item

    def _mission_row(self, owner_id: str, mission_id: str) -> tuple[sqlite3.Connection, sqlite3.Row] | None:
        connection = connect_database(self.database_path)
        row = connection.execute(
            "SELECT * FROM monitoring_missions WHERE id = ? AND owner_id = ?",
            (mission_id, owner_id),
        ).fetchone()
        if row is None:
            connection.close()
            return None
        return connection, row

    def list_missions(self, owner_id: str) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM monitoring_missions
                WHERE owner_id = ? AND status != 'archived'
                ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'active' THEN 1 ELSE 2 END,
                         updated_at DESC, id DESC
                """,
                (owner_id,),
            ).fetchall()
            return [self._decode_mission(row, connection, detail=False) for row in rows]

    def get_mission(self, owner_id: str, mission_id: str, *, detail: bool = True) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM monitoring_missions WHERE id = ? AND owner_id = ?",
                (mission_id, owner_id),
            ).fetchone()
            return self._decode_mission(row, connection, detail=detail) if row is not None else None

    def create_mission(
        self,
        *,
        owner_id: str,
        goal: str,
        title: str,
        mission_type: str,
        targets: Sequence[Mapping[str, object]],
        platforms: Sequence[str],
        schedule_type: str,
        schedule_config: Mapping[str, object],
        importance_rule: str | None,
        ignored_content_rule: str | None,
        budget: Mapping[str, object],
        understanding: Mapping[str, object],
        confirmed: bool,
    ) -> dict[str, object]:
        if not goal.strip():
            raise ValueError("monitoring goal must not be blank")
        status = "active" if confirmed else "draft"
        now_dt = datetime.now(UTC)
        next_run = _next_run(schedule_type, schedule_config, now_dt) if confirmed else None
        identifier = _new_id()
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO monitoring_missions (
                    id, owner_id, goal, title, mission_type, status, schedule_type,
                    schedule_config_json, next_run_at, last_run_at, last_run_status,
                    importance_rule, ignored_content_rule, platforms_json, budget_json,
                    understanding_json, consecutive_failures, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (
                    identifier,
                    owner_id,
                    goal.strip(),
                    title.strip()[:200] or goal.strip()[:200],
                    mission_type,
                    status,
                    schedule_type,
                    _dump(dict(schedule_config)),
                    next_run,
                    importance_rule,
                    ignored_content_rule,
                    _dump(list(dict.fromkeys(platforms))),
                    _dump(dict(budget)),
                    _dump(dict(understanding)),
                    _now(),
                    _now(),
                ),
            )
            for target in targets:
                target_type = str(target["target_type"])
                target_value = str(target["target_value"]).strip()
                connection.execute(
                    """
                    INSERT INTO monitoring_targets
                        (id, mission_id, target_type, target_value, normalized_key, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _new_id(),
                        identifier,
                        target_type,
                        target_value,
                        " ".join(target_value.casefold().split()),
                        _now(),
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        result = self.get_mission(owner_id, identifier, detail=True)
        if result is None:
            raise MonitoringNotFound(identifier)
        return result

    def update_mission(
        self,
        *,
        owner_id: str,
        mission_id: str,
        changes: Mapping[str, object],
    ) -> dict[str, object] | None:
        allowed = {"title", "schedule_type", "schedule_config", "platforms", "importance_rule", "ignored_content_rule", "budget"}
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"unsupported monitoring fields: {sorted(invalid)}")
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM monitoring_missions WHERE id = ? AND owner_id = ?",
                (mission_id, owner_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            values: dict[str, object] = {}
            for key, value in changes.items():
                if key == "schedule_config":
                    values["schedule_config_json"] = _dump(value if isinstance(value, Mapping) else {})
                elif key == "platforms":
                    values["platforms_json"] = _dump(list(value) if isinstance(value, Sequence) and not isinstance(value, str) else [])
                elif key == "budget":
                    values["budget_json"] = _dump(value if isinstance(value, Mapping) else {})
                else:
                    values[key] = value
            schedule_type = str(values.get("schedule_type") or row["schedule_type"])
            schedule_config = _json(values.get("schedule_config_json", row["schedule_config_json"]), {})
            next_run = _next_run(schedule_type, schedule_config if isinstance(schedule_config, Mapping) else {}, datetime.now(UTC)) if str(row["status"]) == "active" else None
            values["next_run_at"] = next_run
            values["updated_at"] = _now()
            assignments = ", ".join(f"{key} = ?" for key in values)
            connection.execute(
                f"UPDATE monitoring_missions SET {assignments} WHERE id = ? AND owner_id = ?",
                (*values.values(), mission_id, owner_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get_mission(owner_id, mission_id, detail=True)

    def set_status(self, *, owner_id: str, mission_id: str, status: str) -> dict[str, object] | None:
        if status not in {"active", "paused", "archived"}:
            raise ValueError("invalid monitoring mission status action")
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM monitoring_missions WHERE id = ? AND owner_id = ?",
                (mission_id, owner_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            config = _json(row["schedule_config_json"], {})
            next_run = _next_run(str(row["schedule_type"]), config if isinstance(config, Mapping) else {}, datetime.now(UTC)) if status == "active" else None
            connection.execute(
                "UPDATE monitoring_missions SET status = ?, next_run_at = ?, updated_at = ? WHERE id = ?",
                (status, next_run, _now(), mission_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get_mission(owner_id, mission_id, detail=True)

    def claim_run(self, *, owner_id: str, mission_id: str, trigger: str) -> dict[str, object]:
        identifier = _new_id()
        now = _now()
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            mission = connection.execute(
                "SELECT * FROM monitoring_missions WHERE id = ? AND owner_id = ?",
                (mission_id, owner_id),
            ).fetchone()
            if mission is None:
                raise MonitoringNotFound(mission_id)
            if str(mission["status"]) not in {"active", "completed_run", "degraded"}:
                raise MonitoringConflict("monitoring mission is not active")
            running = connection.execute(
                "SELECT 1 FROM monitoring_runs WHERE mission_id = ? AND status IN ('queued', 'running', 'waiting_platform', 'waiting_login') LIMIT 1",
                (mission_id,),
            ).fetchone()
            if running is not None:
                raise MonitoringConflict("monitoring mission already has an active run")
            connection.execute(
                """
                INSERT INTO monitoring_runs
                    (id, mission_id, status, trigger, started_at, baseline_created,
                     change_count, notification_count, resource_json, created_at, claimed_at)
                VALUES (?, ?, 'running', ?, ?, 0, 0, 0, '{}', ?, ?)
                """,
                (identifier, mission_id, trigger, now, now, now),
            )
            connection.execute(
                "UPDATE monitoring_missions SET status = 'running', updated_at = ? WHERE id = ?",
                (now, mission_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        result = self.get_run(owner_id, identifier)
        if result is None:
            raise MonitoringNotFound(identifier)
        return result

    def claim_due_runs(self, *, now: datetime, limit: int = 1) -> list[dict[str, object]]:
        claimed: list[dict[str, object]] = []
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT * FROM monitoring_missions
                WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at, created_at LIMIT ?
                """,
                (now.astimezone(UTC).isoformat().replace("+00:00", "Z"), max(1, min(limit, 3))),
            ).fetchall()
            for row in rows:
                running = connection.execute(
                    "SELECT 1 FROM monitoring_runs WHERE mission_id = ? AND status IN ('queued', 'running', 'waiting_platform', 'waiting_login') LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if running is not None:
                    continue
                run_id = _new_id()
                timestamp = _now()
                connection.execute(
                    "INSERT INTO monitoring_runs (id, mission_id, status, trigger, started_at, baseline_created, change_count, notification_count, resource_json, created_at, claimed_at) VALUES (?, ?, 'running', 'scheduled', ?, 0, 0, 0, '{}', ?, ?)",
                    (run_id, row["id"], timestamp, timestamp, timestamp),
                )
                config = _json(row["schedule_config_json"], {})
                next_run = _next_run(str(row["schedule_type"]), config if isinstance(config, Mapping) else {}, now)
                connection.execute(
                    "UPDATE monitoring_missions SET status = 'running', next_run_at = ?, updated_at = ? WHERE id = ?",
                    (next_run, timestamp, row["id"]),
                )
                claimed.append({"id": run_id, "mission_id": str(row["id"])})
            connection.commit()
        return claimed

    def get_run(self, owner_id: str, run_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT run.* FROM monitoring_runs run
                JOIN monitoring_missions mission ON mission.id = run.mission_id
                WHERE run.id = ? AND mission.owner_id = ?
                """,
                (run_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["baseline_created"] = _bool(result["baseline_created"])
            result["resource"] = dict(_json(result.pop("resource_json", "{}"), {}))
            result["queries"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM monitoring_run_queries WHERE run_id = ? ORDER BY created_at, id",
                    (run_id,),
                ).fetchall()
            ]
            return result

    def attach_research_task(
        self,
        *,
        owner_id: str,
        run_id: str,
        research_task_id: str,
        resource: Mapping[str, object],
    ) -> dict[str, object] | None:
        """Link a monitoring run to the existing Research Runtime queue.

        Monitoring owns the mission and notification lifecycle; ResearchTask
        remains the only execution runtime for model/tool/crawler work.
        """
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT run.id FROM monitoring_runs run
                JOIN monitoring_missions mission ON mission.id = run.mission_id
                WHERE run.id = ? AND mission.owner_id = ?
                """,
                (run_id, owner_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE monitoring_runs SET research_task_id = ?, baseline_created = ?, resource_json = ? WHERE id = ?",
                (research_task_id, int(bool(resource.get("baseline_created"))), _dump(dict(resource)), run_id),
            )
            connection.commit()
        return self.get_run(owner_id, run_id)

    def update_waiting_state(
        self,
        *,
        owner_id: str,
        run_id: str,
        run_status: str,
        mission_status: str,
        failure_reason: str | None = None,
    ) -> dict[str, object] | None:
        if run_status not in {"running", "waiting_platform", "waiting_login"}:
            raise ValueError("invalid monitoring waiting status")
        if mission_status not in {"running", "waiting_platform", "waiting_login"}:
            raise ValueError("invalid monitoring mission waiting status")
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE monitoring_runs
                SET status = ?, failure_reason = ?
                WHERE id = ? AND mission_id IN (
                    SELECT mission.id FROM monitoring_missions mission
                    WHERE mission.owner_id = ?
                )
                """,
                (run_status, failure_reason, run_id, owner_id),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            connection.execute(
                """
                UPDATE monitoring_missions
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = (SELECT mission_id FROM monitoring_runs WHERE id = ?)
                  AND owner_id = ?
                """,
                (mission_status, failure_reason, _now(), run_id, owner_id),
            )
            connection.commit()
        return self.get_run(owner_id, run_id)

    def linked_active_runs(self, *, limit: int = 3) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT run.*, mission.owner_id, mission.goal, mission.platforms_json,
                       mission.budget_json
                FROM monitoring_runs run
                JOIN monitoring_missions mission ON mission.id = run.mission_id
                WHERE run.research_task_id IS NOT NULL
                  AND run.status IN ('running', 'waiting_platform', 'waiting_login')
                ORDER BY run.created_at, run.id
                LIMIT ?
                """,
                (max(1, min(limit, 3)),),
            ).fetchall()
            return [self._run_from_connection(connection, row) | {
                "owner_id": row["owner_id"],
                "goal": row["goal"],
                "platforms": list(_json(row["platforms_json"], [])),
                "budget": dict(_json(row["budget_json"], {})),
            } for row in rows]

    def get_mission_for_run(self, run_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT mission.* FROM monitoring_missions mission
                JOIN monitoring_runs run ON run.mission_id = mission.id
                WHERE run.id = ?
                """,
                (run_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_runs(self, owner_id: str, mission_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT run.* FROM monitoring_runs run
                JOIN monitoring_missions mission ON mission.id = run.mission_id
                WHERE run.mission_id = ? AND mission.owner_id = ?
                ORDER BY run.created_at DESC, run.id DESC LIMIT ?
                """,
                (mission_id, owner_id, max(1, min(limit, 100))),
            ).fetchall()
            return [self._run_from_connection(connection, row) for row in rows]

    @staticmethod
    def _run_from_connection(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["baseline_created"] = _bool(result["baseline_created"])
        result["resource"] = dict(_json(result.pop("resource_json", "{}"), {}))
        result["queries"] = [dict(item) for item in connection.execute("SELECT * FROM monitoring_run_queries WHERE run_id = ? ORDER BY created_at, id", (row["id"],)).fetchall()]
        return result

    def add_run_query(self, *, run_id: str, platform: str, query: str, query_role: str, status: str, result_count: int, new_content_count: int, reason: str | None) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "INSERT INTO monitoring_run_queries (id, run_id, platform, query, query_role, status, result_count, new_content_count, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (_new_id(), run_id, platform, query[:1_000], query_role[:100], status[:50], max(0, result_count), max(0, new_content_count), reason, _now()),
            )

    def latest_baseline(self, owner_id: str, mission_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT baseline.* FROM monitoring_baselines baseline
                JOIN monitoring_missions mission ON mission.id = baseline.mission_id
                WHERE baseline.mission_id = ? AND mission.owner_id = ?
                ORDER BY version DESC LIMIT 1
                """,
                (mission_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            item["snapshot"] = dict(_json(item.pop("snapshot_json", "{}"), {}))
            return item

    def save_baseline(self, *, mission_id: str, run_id: str, snapshot: Mapping[str, object]) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            version_row = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM monitoring_baselines WHERE mission_id = ?", (mission_id,)).fetchone()
            version = int(version_row[0]) if version_row else 1
            identifier = _new_id()
            connection.execute(
                "INSERT INTO monitoring_baselines (id, mission_id, source_run_id, version, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, mission_id, run_id, version, _dump(dict(snapshot)), _now()),
            )
            connection.commit()
        return {"id": identifier, "mission_id": mission_id, "source_run_id": run_id, "version": version, "snapshot": dict(snapshot), "created_at": _now()}

    def _change_from_connection(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["explanation"] = dict(_json(item.pop("explanation_json", "{}"), {}))
        item["sources"] = [
            dict(source)
            | {"is_repost": _bool(source["is_repost"])}
            for source in connection.execute("SELECT * FROM monitoring_change_sources WHERE change_id = ? ORDER BY created_at, id", (item["id"],)).fetchall()
        ]
        memory = connection.execute("SELECT * FROM monitoring_memory_updates WHERE change_id = ? ORDER BY created_at DESC LIMIT 1", (item["id"],)).fetchone()
        if memory is not None:
            memory_item = dict(memory)
            memory_item["old_value"] = _json(memory_item.pop("old_value_json", "null"), None)
            memory_item["new_value"] = _json(memory_item.pop("new_value_json", "{}"), {})
            memory_item["evidence"] = _json(memory_item.pop("evidence_json", "[]"), [])
            item["memory_update"] = memory_item
        else:
            item["memory_update"] = None
        item["source_type"] = "monitoring"
        return item

    def save_change(
        self,
        *,
        mission_id: str,
        run_id: str,
        change: Mapping[str, object],
        attention: Mapping[str, object],
        memory_update: Mapping[str, object] | None,
    ) -> dict[str, object]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM monitoring_changes WHERE mission_id = ? AND fingerprint = ?", (mission_id, str(change["fingerprint"]))).fetchone()
            identifier = str(existing["id"]) if existing is not None else _new_id()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO monitoring_changes (
                        id, mission_id, run_id, change_type, fingerprint, title, summary,
                        first_seen_at, latest_seen_at, relevance_score, novelty_score,
                        evidence_strength_score, source_independence_score, cross_platform_score,
                        actionability_score, persistence_score, noise_risk_score, attention_level,
                        state, explanation_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
                    """,
                    (
                        identifier, mission_id, run_id, change.get("change_type", "new_claim"), change["fingerprint"], change.get("title", ""), change.get("summary", ""),
                        change.get("first_seen_at"), change.get("latest_seen_at"), change.get("relevance_score", 0), change.get("novelty_score", 0), change.get("evidence_strength_score", 0), change.get("source_independence_score", 0), change.get("cross_platform_score", 0), change.get("actionability_score", 0), change.get("persistence_score", 0), change.get("noise_risk_score", 0), attention.get("level", "normal_record"), _dump(change.get("explanation", {})), _now(), _now(),
                    ),
                )
                evidence = change.get("evidence")
                if isinstance(evidence, list):
                    for source in evidence:
                        if not isinstance(source, Mapping):
                            continue
                        connection.execute(
                            "INSERT OR IGNORE INTO monitoring_change_sources (id, change_id, content_id, platform, source_url, source_title, source_author, published_at, is_repost, independent_group, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (_new_id(), identifier, source.get("content_id"), source.get("platform"), source.get("source_url"), source.get("source_title"), source.get("source_author"), source.get("published_at"), int(bool(source.get("is_repost"))), source.get("independent_group"), _now()),
                        )
            else:
                connection.execute("UPDATE monitoring_changes SET run_id = ?, latest_seen_at = COALESCE(?, latest_seen_at), updated_at = ? WHERE id = ?", (run_id, change.get("latest_seen_at"), _now(), identifier))
            if memory_update is not None:
                connection.execute(
                    "INSERT INTO monitoring_memory_updates (id, mission_id, change_id, memory_key, old_value_json, new_value_json, evidence_json, changed_at, confidence, confirmation_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (_new_id(), mission_id, identifier, memory_update.get("memory_key", identifier), _dump(memory_update.get("old_value")), _dump(memory_update.get("new_value", {})), _dump(memory_update.get("evidence_ids", [])), memory_update.get("changed_at"), memory_update.get("confidence", 0), memory_update.get("confirmation_status", "recorded"), _now()),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        with connect_database(self.database_path) as connection:
            row = connection.execute("SELECT * FROM monitoring_changes WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise MonitoringNotFound(identifier)
            return self._change_from_connection(connection, row)

    def list_changes(self, owner_id: str, mission_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute("SELECT change.* FROM monitoring_changes change JOIN monitoring_missions mission ON mission.id = change.mission_id WHERE change.mission_id = ? AND mission.owner_id = ? ORDER BY change.updated_at DESC, change.id DESC LIMIT ?", (mission_id, owner_id, max(1, min(limit, 200)))).fetchall()
            return [self._change_from_connection(connection, row) for row in rows]

    def get_change(self, owner_id: str, change_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute("SELECT change.* FROM monitoring_changes change JOIN monitoring_missions mission ON mission.id = change.mission_id WHERE change.id = ? AND mission.owner_id = ?", (change_id, owner_id)).fetchone()
            return self._change_from_connection(connection, row) if row is not None else None

    def complete_run(self, *, owner_id: str, run_id: str, status: str, change_count: int, notification_count: int, baseline_created: bool, resource: Mapping[str, object], failure_reason: str | None = None) -> dict[str, object] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT run.*, mission.schedule_type, mission.schedule_config_json, mission.next_run_at, mission.consecutive_failures FROM monitoring_runs run JOIN monitoring_missions mission ON mission.id = run.mission_id WHERE run.id = ? AND mission.owner_id = ?", (run_id, owner_id)).fetchone()
            if row is None:
                connection.rollback()
                return None
            finished = _now()
            successful = status in {"completed", "no_meaningful_change"}
            scheduled = str(row["schedule_type"]) != "manual"
            failure_count = 0 if successful else int(row["consecutive_failures"] or 0) + 1
            backoff_until: str | None = None
            mission_status = (
                "active" if scheduled else "completed_run"
                if successful
                else "active" if scheduled
                else "degraded" if status == "degraded"
                else "failed"
            )
            next_run_at: str | None = row["next_run_at"]
            if not successful and scheduled:
                retry_at = datetime.now(UTC) + timedelta(seconds=min(3_600, 60 * (2 ** min(failure_count - 1, 6))))
                backoff_until = retry_at.isoformat().replace("+00:00", "Z")
                schedule_config = _json(row["schedule_config_json"], {})
                scheduled_at = _next_run(
                    str(row["schedule_type"]),
                    schedule_config if isinstance(schedule_config, Mapping) else {},
                    datetime.now(UTC),
                )
                next_run_at = max(item for item in (scheduled_at, backoff_until) if item is not None)
            connection.execute("UPDATE monitoring_runs SET status = ?, completed_at = ?, baseline_created = ?, change_count = ?, notification_count = ?, resource_json = ?, failure_reason = ?, backoff_until = ? WHERE id = ?", (status, finished, int(baseline_created), max(0, change_count), max(0, notification_count), _dump(dict(resource)), failure_reason, backoff_until, run_id))
            connection.execute("UPDATE monitoring_missions SET status = ?, next_run_at = ?, last_run_at = ?, last_run_status = ?, consecutive_failures = ?, last_error = ?, updated_at = ? WHERE id = ?", (mission_status, next_run_at, finished, status, failure_count, failure_reason, finished, row["mission_id"]))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get_run(owner_id, run_id)

    def create_notification(self, *, owner_id: str, mission_id: str, change: Mapping[str, object]) -> dict[str, object] | None:
        level = str(change.get("attention_level") or "normal_record")
        if level in {"silent_memory", "ignored"}:
            return None
        identifier = _new_id()
        with connect_database(self.database_path) as connection:
            connection.execute("INSERT OR IGNORE INTO monitoring_notifications (id, owner_id, mission_id, change_id, level, status, created_at) VALUES (?, ?, ?, ?, ?, 'unread', ?)", (identifier, owner_id, mission_id, change["id"], level, _now()))
            row = connection.execute("SELECT * FROM monitoring_notifications WHERE owner_id = ? AND change_id = ?", (owner_id, change["id"])).fetchone()
            if row is None:
                return None
            return dict(row) | {"title": change.get("title", ""), "summary": change.get("summary", "")}

    def list_notifications(self, owner_id: str, *, status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        clauses = ["notification.owner_id = ?"]
        values: list[object] = [owner_id]
        if status:
            clauses.append("notification.status = ?")
            values.append(status)
        values.append(max(1, min(limit, 200)))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(f"SELECT notification.*, change.title, change.summary FROM monitoring_notifications notification JOIN monitoring_changes change ON change.id = notification.change_id WHERE {' AND '.join(clauses)} ORDER BY notification.created_at DESC LIMIT ?", values).fetchall()
            return [dict(row) for row in rows]

    def update_notification(self, *, owner_id: str, notification_id: str, action: str, until: str | None = None) -> dict[str, object] | None:
        if action not in {"read", "defer", "ignore"}:
            raise ValueError("invalid notification action")
        status = {"read": "read", "defer": "deferred", "ignore": "ignored"}[action]
        timestamp = _now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute("UPDATE monitoring_notifications SET status = ?, read_at = CASE WHEN ? = 'read' THEN ? ELSE read_at END, deferred_until = CASE WHEN ? = 'deferred' THEN ? ELSE deferred_until END, ignored_at = CASE WHEN ? = 'ignored' THEN ? ELSE ignored_at END WHERE id = ? AND owner_id = ?", (status, status, timestamp, status, until, status, timestamp, notification_id, owner_id))
            if updated.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute("SELECT notification.*, change.title, change.summary FROM monitoring_notifications notification JOIN monitoring_changes change ON change.id = notification.change_id WHERE notification.id = ?", (notification_id,)).fetchone()
            connection.commit()
            return dict(row) if row is not None else None

    def list_inbox_changes(self, owner_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute("SELECT change.*, mission.title AS mission_title FROM monitoring_changes change JOIN monitoring_missions mission ON mission.id = change.mission_id WHERE mission.owner_id = ? AND change.attention_level NOT IN ('silent_memory', 'ignored') AND change.state != 'ignored' ORDER BY change.updated_at DESC LIMIT ?", (owner_id, max(1, min(limit, 100)))).fetchall()
            result: list[dict[str, object]] = []
            for row in rows:
                sources = connection.execute(
                    "SELECT platform, independent_group, source_url, content_id, is_repost FROM monitoring_change_sources WHERE change_id = ?",
                    (row["id"],),
                ).fetchall()
                groups = {
                    str(source["independent_group"] or source["platform"] or source["source_url"] or source["content_id"])
                    for source in sources
                }
                platforms = {str(source["platform"]) for source in sources if source["platform"]}
                first_platform = next(iter(platforms), None)
                result.append(
                    {
                        "id": row["id"],
                        "source_type": "monitoring",
                        "mission_id": row["mission_id"],
                        "research_task_id": None,
                        "candidate_type": "event",
                        "title": row["title"],
                        "summary": row["summary"],
                        "normalized_key": row["fingerprint"],
                        "parent_candidate_id": None,
                        "source_seed_id": None,
                        "source_content_id": None,
                        "source_platform": first_platform,
                        "relevance_score": row["relevance_score"],
                        "novelty_score": row["novelty_score"],
                        "evidence_strength_score": row["evidence_strength_score"],
                        "source_independence_score": row["source_independence_score"],
                        "cross_platform_score": row["cross_platform_score"],
                        "counterevidence_score": 0.0,
                        "actionability_score": row["actionability_score"],
                        "feedback_score": 0.0,
                        "noise_risk_score": row["noise_risk_score"],
                        "marketing_risk_score": row["noise_risk_score"],
                        "saturation_score": 0.0,
                        "resource_cost_score": 0.0,
                        "final_score": row["relevance_score"],
                        "score_explanation": {
                            "why_relevant": "与已确认的监控目标相关",
                            "why_new": "相对上次基线出现了新证据",
                            "source_independence": "同源转载已合并",
                            "recommendation": "打开监控任务查看事件、证据与反向证据",
                        },
                        "content_count": len(sources),
                        "independent_source_count": len(groups),
                        "platform_count": len(platforms),
                        "suspected_repost_count": sum(bool(source["is_repost"]) for source in sources),
                        "depth": 0,
                        "state": "generated",
                        "suggested_next_action": "打开监控任务查看变化",
                        "experimental_status": None,
                        "attention_level": row["attention_level"],
                        "change_type": row["change_type"],
                        "source_mission_title": row["mission_title"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
            return result

    def list_matching_contents(self, *, goal: str, targets: Sequence[Mapping[str, object]], platforms: Sequence[str], limit: int = 60) -> list[dict[str, object]]:
        terms = [str(goal).strip(), *(str(item.get("target_value") or "").strip() for item in targets)]
        terms = [term for term in terms if len(term) >= 2]
        clauses: list[str] = []
        values: list[object] = []
        for term in terms[:8]:
            pattern = f"%{term[:120]}%"
            clauses.append("(title LIKE ? OR description LIKE ? OR source_keyword LIKE ?)")
            values.extend([pattern, pattern, pattern])
        platform_values = tuple(dict.fromkeys(str(item).strip() for item in platforms if str(item).strip()))
        platform_clause = ""
        if platform_values:
            platform_clause = " AND platform IN (" + ",".join("?" for _ in platform_values) + ")"
            values.extend(platform_values)
        where = " OR ".join(clauses) if clauses else "1 = 1"
        with connect_database(self.database_path) as connection:
            rows = connection.execute(f"SELECT id, platform, title, description, source_url, author_name, published_at, source_keyword, last_collected_at FROM library_contents WHERE ({where}){platform_clause} ORDER BY COALESCE(published_at, last_collected_at) DESC, id DESC LIMIT ?", (*values, max(1, min(limit, 200)))).fetchall()
            return [dict(row) for row in rows]
