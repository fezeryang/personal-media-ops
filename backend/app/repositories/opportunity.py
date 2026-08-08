from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping
from pathlib import Path

from app.db import connect_database
from app.repositories.research import utc_now


class OpportunityNotFound(KeyError):
    pass


class OpportunityConflict(RuntimeError):
    pass


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json(value: object, default: object) -> object:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _list(value: object) -> list[object]:
    parsed = _json(value, [])
    return list(parsed) if isinstance(parsed, list) else []


def _dict(value: object) -> dict[str, object]:
    parsed = _json(value, {})
    return dict(parsed) if isinstance(parsed, dict) else {}


def _bool(value: object) -> bool:
    return bool(int(value or 0))


def _new_id() -> str:
    return str(uuid.uuid4())


class OpportunityRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @staticmethod
    def _decode_opportunity(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["scores"] = _dict(item.pop("score_json", "{}"))
        item["score_explanation"] = _dict(item.pop("explanation_json", "{}"))
        item["unknowns"] = _list(item.pop("unknowns_json", "[]"))
        item["content_details"] = _dict(item.pop("content_details_json", "{}"))
        item.pop("owner_id", None)
        return item

    @staticmethod
    def _decode_source(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["is_repost"] = _bool(item.get("is_repost"))
        item.pop("opportunity_id", None)
        return item

    @staticmethod
    def _decode_version(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["snapshot"] = _dict(item.pop("snapshot_json", "{}"))
        item.pop("opportunity_id", None)
        return item

    @staticmethod
    def _decode_score(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["scores"] = _dict(item.pop("scores_json", "{}"))
        item["explanation"] = _dict(item.pop("explanation_json", "{}"))
        item.pop("opportunity_id", None)
        return item

    @staticmethod
    def _decode_plan(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        for field in (
            "critical_assumptions_json", "unknowns_json", "validation_questions_json",
            "evidence_needed_json", "success_criteria_json", "failure_criteria_json",
        ):
            item[field.removesuffix("_json")] = _list(item.pop(field, "[]"))
        item.pop("owner_id", None)
        return item

    @staticmethod
    def _decode_action(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item.pop("owner_id", None)
        return item

    def _assert_source_owner(
        self,
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        source_type: str,
        source_id: str,
        content_id: str | None = None,
        finding_id: str | None = None,
    ) -> None:
        checks: dict[str, tuple[str, tuple[object, ...]]] = {
            "research_task": (
                "SELECT id FROM research_tasks WHERE id = ? AND user_id = ?",
                (source_id, owner_id),
            ),
            "discovery_candidate": (
                "SELECT id FROM research_discovery_candidates WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ),
            "monitoring_change": (
                """
                SELECT change.id FROM monitoring_changes change
                JOIN monitoring_missions mission ON mission.id = change.mission_id
                WHERE change.id = ? AND mission.owner_id = ?
                """,
                (source_id, owner_id),
            ),
            "research_space": (
                "SELECT id FROM research_spaces WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ),
            "opportunity": (
                "SELECT id FROM opportunities WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ),
            "validation_plan": (
                "SELECT id FROM validation_plans WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ),
            "action": (
                "SELECT id FROM opportunity_actions WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ),
        }
        if source_type in checks:
            row = connection.execute(*checks[source_type]).fetchone()
            if row is None:
                raise OpportunityNotFound(f"{source_type}:{source_id}")
        elif source_type in {"content", "evidence"}:
            row = connection.execute("SELECT id FROM library_contents WHERE id = ?", (content_id or source_id,)).fetchone()
            if row is None:
                raise OpportunityNotFound(f"content:{content_id or source_id}")
        elif source_type == "finding":
            row = connection.execute(
                """
                SELECT finding.id FROM findings finding
                JOIN research_tasks task ON task.id = finding.research_task_id
                WHERE finding.id = ? AND task.user_id = ?
                """,
                (finding_id or source_id, owner_id),
            ).fetchone()
            if row is None:
                raise OpportunityNotFound(f"finding:{finding_id or source_id}")
        elif source_type != "manual":
            raise OpportunityConflict(f"unsupported opportunity source type: {source_type}")

    def get_opportunity_for_origin(
        self,
        *,
        owner_id: str,
        source_type: str,
        source_id: str,
        opportunity_type: str,
    ) -> dict[str, object] | None:
        origin_column = {
            "research_task": "related_research_task_id",
            "discovery_candidate": "related_discovery_candidate_id",
            "monitoring_change": "related_monitoring_change_id",
        }.get(source_type)
        if origin_column is None:
            return None
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                f"SELECT id FROM opportunities WHERE owner_id = ? AND opportunity_type = ? AND {origin_column} = ? AND status != 'archived' ORDER BY updated_at DESC, id DESC LIMIT 1",
                (owner_id, opportunity_type, source_id),
            ).fetchone()
        return self.get_opportunity(owner_id=owner_id, opportunity_id=str(row["id"]), detail=True) if row is not None else None

    def list_opportunities(
        self,
        *,
        owner_id: str,
        limit: int = 30,
        readiness: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        bounded = max(1, min(limit, 100))
        clauses = ["owner_id = ?"]
        values: list[object] = [owner_id]
        if readiness:
            clauses.append("readiness = ?")
            values.append(readiness)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.append(bounded)
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM opportunities
                WHERE {' AND '.join(clauses)} AND status != 'archived'
                ORDER BY CASE readiness WHEN 'validation_ready' THEN 0 WHEN 'review_ready' THEN 1 WHEN 'needs_more_evidence' THEN 2 ELSE 3 END,
                         json_extract(score_json, '$.confidence') DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [self._decode_opportunity(row) for row in rows]

    def get_opportunity(self, *, owner_id: str, opportunity_id: str, detail: bool = True) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM opportunities WHERE id = ? AND owner_id = ?",
                (opportunity_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            item = self._decode_opportunity(row)
            if not detail:
                return item
            item["sources"] = [
                self._decode_source(source)
                for source in connection.execute(
                    "SELECT * FROM opportunity_sources WHERE opportunity_id = ? ORDER BY CASE source_role WHEN 'core' THEN 0 WHEN 'counterevidence' THEN 1 ELSE 2 END, created_at, id",
                    (opportunity_id,),
                ).fetchall()
            ]
            item["versions"] = [
                self._decode_version(version)
                for version in connection.execute(
                    "SELECT * FROM opportunity_versions WHERE opportunity_id = ? ORDER BY version DESC, created_at DESC",
                    (opportunity_id,),
                ).fetchall()
            ]
            item["score_history"] = [
                self._decode_score(score)
                for score in connection.execute(
                    "SELECT * FROM opportunity_scores WHERE opportunity_id = ? ORDER BY version DESC, created_at DESC",
                    (opportunity_id,),
                ).fetchall()
            ]
            item["feedback"] = [
                dict(feedback)
                for feedback in connection.execute(
                    "SELECT id, opportunity_id, feedback_type, note, undone_at, created_at FROM opportunity_feedback WHERE owner_id = ? AND opportunity_id = ? ORDER BY created_at DESC, id DESC",
                    (owner_id, opportunity_id),
                ).fetchall()
            ]
            plans = [
                self._decode_plan(plan)
                for plan in connection.execute(
                    "SELECT * FROM validation_plans WHERE owner_id = ? AND opportunity_id = ? ORDER BY updated_at DESC, id DESC",
                    (owner_id, opportunity_id),
                ).fetchall()
            ]
            for plan in plans:
                plan["results"] = [
                    dict(result)
                    for result in connection.execute(
                        "SELECT id, plan_id, outcome, what_happened, result, evidence_json, user_notes, next_step, created_at FROM validation_results WHERE owner_id = ? AND plan_id = ? ORDER BY created_at DESC, id DESC",
                        (owner_id, plan["id"]),
                    ).fetchall()
                ]
                for result in plan["results"]:
                    if isinstance(result, dict):
                        result["evidence"] = _list(result.pop("evidence_json", "[]"))
            item["validation_plans"] = plans
            actions = [
                self._decode_action(action)
                for action in connection.execute(
                    "SELECT * FROM opportunity_actions WHERE owner_id = ? AND opportunity_id = ? ORDER BY updated_at DESC, id DESC",
                    (owner_id, opportunity_id),
                ).fetchall()
            ]
            for action in actions:
                action["outcomes"] = []
                for outcome in connection.execute(
                    "SELECT * FROM action_outcomes WHERE owner_id = ? AND action_id = ? ORDER BY created_at DESC, id DESC",
                    (owner_id, action["id"]),
                ).fetchall():
                    decoded = dict(outcome)
                    decoded["evidence"] = _list(decoded.pop("evidence_json", "[]"))
                    decoded["metrics"] = _dict(decoded.pop("metrics_json", "{}"))
                    decoded.pop("owner_id", None)
                    action["outcomes"].append(decoded)
            item["actions"] = actions
        return item

    def _assert_opportunity_owner(self, connection: sqlite3.Connection, owner_id: str, opportunity_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM opportunities WHERE id = ? AND owner_id = ?",
            (opportunity_id, owner_id),
        ).fetchone()
        if row is None:
            raise OpportunityNotFound(opportunity_id)
        return row

    def create_signal(self, *, owner_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        identifier = _new_id()
        now = utc_now()
        aggregation_key = str(payload.get("aggregation_key") or payload.get("title") or "").strip().casefold()
        if not aggregation_key:
            raise OpportunityConflict("signal aggregation key is required")
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_source_owner(
                connection,
                owner_id=owner_id,
                source_type=str(payload["source_type"]),
                source_id=str(payload["source_id"]),
                content_id=str(payload.get("content_id") or "") or None,
                finding_id=str(payload.get("finding_id") or "") or None,
            )
            connection.execute(
                """
                INSERT INTO opportunity_signals (
                    id, owner_id, signal_type, title, summary, evidence_id, content_id, finding_id,
                    discovery_candidate_id, monitoring_change_id, source_type, source_id,
                    source_platform, source_url, entity_key, event_key, observed_at,
                    aggregation_key, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier, owner_id, payload["signal_type"], payload["title"], payload["summary"],
                    payload.get("evidence_id"), payload.get("content_id"), payload.get("finding_id"),
                    payload.get("discovery_candidate_id"), payload.get("monitoring_change_id"),
                    payload["source_type"], payload["source_id"], payload.get("source_platform"),
                    payload.get("source_url"), payload.get("entity_key"), payload.get("event_key"),
                    payload.get("observed_at"), aggregation_key, _dump(payload.get("metadata", {})), now, now,
                ),
            )
            row = connection.execute("SELECT * FROM opportunity_signals WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise OpportunityConflict("signal could not be persisted")
        result = dict(row)
        result["metadata"] = _dict(result.pop("metadata_json", "{}"))
        result.pop("owner_id", None)
        return result

    def create_opportunity(
        self,
        *,
        owner_id: str,
        payload: Mapping[str, object],
        scores: Mapping[str, float],
        score_explanation: Mapping[str, object],
        readiness: str,
        status: str,
    ) -> dict[str, object]:
        identifier = _new_id()
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for source in payload.get("sources", []):
                if not isinstance(source, Mapping):
                    raise OpportunityConflict("invalid opportunity source")
                if str(source.get("source_type")) == "manual" and not any(
                    source.get(key) for key in ("evidence_id", "content_id", "finding_id")
                ):
                    raise OpportunityConflict("manual opportunity sources require an evidence reference")
                self._assert_source_owner(
                    connection,
                    owner_id=owner_id,
                    source_type=str(source["source_type"]),
                    source_id=str(source["source_id"]),
                    content_id=str(source.get("content_id") or "") or None,
                    finding_id=str(source.get("finding_id") or "") or None,
                )
            connection.execute(
                """
                INSERT INTO opportunities (
                    id, owner_id, opportunity_type, title, description, target_user, problem,
                    why_attention, why_now, next_step, status, readiness, version,
                    score_json, explanation_json, unknowns_json, content_details_json,
                    related_research_task_id, related_monitoring_mission_id,
                    related_monitoring_change_id, related_discovery_candidate_id,
                    research_space_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier, owner_id, payload["opportunity_type"], payload["title"], payload["description"],
                    payload["target_user"], payload["problem"], payload["why_attention"], payload["why_now"],
                    payload["next_step"], status, readiness, _dump(scores), _dump(score_explanation),
                    _dump(payload.get("unknowns", [])), _dump(payload.get("content_details", {})),
                    payload.get("related_research_task_id"), payload.get("related_monitoring_mission_id"),
                    payload.get("related_monitoring_change_id"), payload.get("related_discovery_candidate_id"),
                    payload.get("research_space_id"), now, now,
                ),
            )
            for source in payload.get("sources", []):
                assert isinstance(source, Mapping)
                connection.execute(
                    """
                    INSERT INTO opportunity_sources (
                        id, opportunity_id, signal_id, source_type, source_id, evidence_id,
                        content_id, finding_id, source_role, evidence_kind, support_explanation,
                        source_platform, source_url, source_title, independent_group, is_repost, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _new_id(), identifier, source.get("signal_id"), source["source_type"], source["source_id"],
                        source.get("evidence_id"), source.get("content_id"), source.get("finding_id"),
                        source.get("source_role", "supporting"), source.get("evidence_kind", "unknown"),
                        source["support_explanation"], source.get("source_platform"), source.get("source_url"),
                        source.get("source_title"), source.get("independent_group"), int(bool(source.get("is_repost"))), now,
                    ),
                )
            snapshot = dict(payload)
            snapshot.pop("sources", None)
            snapshot.update({"scores": dict(scores), "readiness": readiness, "status": status, "version": 1})
            connection.execute(
                "INSERT INTO opportunity_versions (id, opportunity_id, version, snapshot_json, readiness_before, readiness_after, change_reason, created_at) VALUES (?, ?, 1, ?, NULL, ?, ?, ?)",
                (_new_id(), identifier, _dump(snapshot), readiness, "initial_evidence_bound_candidate", now),
            )
            connection.execute(
                "INSERT INTO opportunity_scores (id, opportunity_id, version, scores_json, explanation_json, readiness, created_at) VALUES (?, ?, 1, ?, ?, ?, ?)",
                (_new_id(), identifier, _dump(scores), _dump(score_explanation), readiness, now),
            )
        result = self.get_opportunity(owner_id=owner_id, opportunity_id=identifier, detail=True)
        if result is None:
            raise OpportunityConflict("opportunity could not be read after creation")
        return result

    def add_feedback(self, *, owner_id: str, opportunity_id: str, feedback_type: str, note: str | None) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_opportunity_owner(connection, owner_id, opportunity_id)
            identifier = _new_id()
            connection.execute(
                "INSERT INTO opportunity_feedback (id, owner_id, opportunity_id, feedback_type, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, owner_id, opportunity_id, feedback_type, note, now),
            )
            status = "accepted" if feedback_type == "valuable" else "rejected" if feedback_type == "reject" else "deferred" if feedback_type == "defer" else None
            if status:
                connection.execute("UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?", (status, now, opportunity_id))
            row = connection.execute("SELECT id, opportunity_id, feedback_type, note, undone_at, created_at FROM opportunity_feedback WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise OpportunityConflict("feedback could not be persisted")
        return dict(row)

    def create_validation_plan(self, *, owner_id: str, opportunity_id: str, values: Mapping[str, object]) -> dict[str, object]:
        now = utc_now()
        identifier = _new_id()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            opportunity = self._assert_opportunity_owner(connection, owner_id, opportunity_id)
            if str(opportunity["readiness"]) not in {"review_ready", "validation_ready", "validated"}:
                raise OpportunityConflict("opportunity needs more evidence before a validation plan")
            connection.execute(
                """
                INSERT INTO validation_plans (
                    id, owner_id, opportunity_id, source_version, status, opportunity_hypothesis,
                    target_user, problem_hypothesis, value_hypothesis, critical_assumptions_json,
                    unknowns_json, validation_questions_json, evidence_needed_json, cheapest_next_test,
                    success_criteria_json, failure_criteria_json, estimated_effort, risk, next_decision,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier, owner_id, opportunity_id, int(opportunity["version"]),
                    values["opportunity_hypothesis"], values["target_user"], values["problem_hypothesis"],
                    values["value_hypothesis"], _dump(values["critical_assumptions"]), _dump(values["unknowns"]),
                    _dump(values["validation_questions"]), _dump(values["evidence_needed"]), values["cheapest_next_test"],
                    _dump(values["success_criteria"]), _dump(values["failure_criteria"]), values["estimated_effort"],
                    values["risk"], values["next_decision"], now, now,
                ),
            )
            connection.execute("UPDATE opportunities SET status = 'review_ready', updated_at = ? WHERE id = ? AND status NOT IN ('validated', 'invalidated')", (now, opportunity_id))
        result = self.get_opportunity(owner_id=owner_id, opportunity_id=opportunity_id, detail=True)
        if result is None:
            raise OpportunityNotFound(opportunity_id)
        plan = next((item for item in result["validation_plans"] if isinstance(item, dict) and item.get("id") == identifier), None)
        if not isinstance(plan, dict):
            raise OpportunityConflict("validation plan could not be read")
        return plan

    def update_validation_plan_status(self, *, owner_id: str, plan_id: str, status: str) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM validation_plans WHERE id = ? AND owner_id = ?", (plan_id, owner_id)).fetchone()
            if row is None:
                raise OpportunityNotFound(plan_id)
            allowed: dict[str, set[str]] = {
                "draft": {"ready", "abandoned"},
                "ready": {"in_progress", "abandoned"},
                "in_progress": {"completed", "abandoned"},
                "completed": set(),
                "abandoned": set(),
            }
            if status not in allowed.get(str(row["status"]), set()):
                raise OpportunityConflict(f"validation plan cannot transition to {status}")
            approved_at = now if status in {"ready", "in_progress"} else None
            connection.execute("UPDATE validation_plans SET status = ?, approved_at = COALESCE(approved_at, ?), updated_at = ? WHERE id = ?", (status, approved_at, now, plan_id))
            if status == "in_progress":
                connection.execute("UPDATE opportunities SET status = 'validating', updated_at = ? WHERE id = ?", (now, row["opportunity_id"]))
        result = self.get_plan(owner_id=owner_id, plan_id=plan_id)
        if result is None:
            raise OpportunityNotFound(plan_id)
        return result

    def get_plan(self, *, owner_id: str, plan_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute("SELECT * FROM validation_plans WHERE id = ? AND owner_id = ?", (plan_id, owner_id)).fetchone()
            if row is None:
                return None
            plan = self._decode_plan(row)
            plan["results"] = []
            for result in connection.execute("SELECT id, plan_id, outcome, what_happened, result, evidence_json, user_notes, next_step, created_at FROM validation_results WHERE owner_id = ? AND plan_id = ? ORDER BY created_at DESC, id DESC", (owner_id, plan_id)).fetchall():
                item = dict(result)
                item["evidence"] = _list(item.pop("evidence_json", "[]"))
                plan["results"].append(item)
        return plan

    def record_validation_result(self, *, owner_id: str, plan_id: str, values: Mapping[str, object]) -> dict[str, object]:
        now = utc_now()
        identifier = _new_id()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            plan = connection.execute("SELECT * FROM validation_plans WHERE id = ? AND owner_id = ?", (plan_id, owner_id)).fetchone()
            if plan is None:
                raise OpportunityNotFound(plan_id)
            if str(plan["status"]) not in {"in_progress", "ready"}:
                raise OpportunityConflict("validation plan must be approved before recording a result")
            connection.execute(
                "INSERT INTO validation_results (id, owner_id, plan_id, outcome, what_happened, result, evidence_json, user_notes, next_step, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (identifier, owner_id, plan_id, values["outcome"], values["what_happened"], values["result"], _dump(values["evidence"]), values.get("user_notes"), values["next_step"], now),
            )
            outcome = str(values["outcome"])
            next_status = "validated" if outcome in {"supported", "not_supported"} else "validating"
            next_readiness = "validated" if outcome in {"supported", "not_supported"} else "needs_more_evidence"
            opportunity = self._assert_opportunity_owner(connection, owner_id, str(plan["opportunity_id"]))
            version = int(opportunity["version"]) + 1
            snapshot = dict(opportunity)
            snapshot.update({"validation_result": dict(values), "version": version, "readiness": next_readiness, "status": next_status})
            connection.execute("UPDATE validation_plans SET status = 'completed', updated_at = ? WHERE id = ?", (now, plan_id))
            connection.execute("UPDATE opportunities SET version = ?, readiness = ?, status = ?, updated_at = ? WHERE id = ?", (version, next_readiness, next_status, now, plan["opportunity_id"]))
            connection.execute("INSERT INTO opportunity_versions (id, opportunity_id, version, snapshot_json, readiness_before, readiness_after, change_reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (_new_id(), plan["opportunity_id"], version, _dump(snapshot), opportunity["readiness"], next_readiness, "validation_result_recorded", now))
            connection.execute("INSERT INTO opportunity_scores (id, opportunity_id, version, scores_json, explanation_json, readiness, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (_new_id(), plan["opportunity_id"], version, opportunity["score_json"], opportunity["explanation_json"], next_readiness, now))
            row = connection.execute("SELECT id, plan_id, outcome, what_happened, result, evidence_json, user_notes, next_step, created_at FROM validation_results WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise OpportunityConflict("validation result could not be persisted")
        result = dict(row)
        result["evidence"] = _list(result.pop("evidence_json", "[]"))
        return result

    def create_action(self, *, owner_id: str, values: Mapping[str, object]) -> dict[str, object]:
        identifier = _new_id()
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if values.get("opportunity_id"):
                self._assert_opportunity_owner(connection, owner_id, str(values["opportunity_id"]))
            if values.get("validation_plan_id"):
                plan = connection.execute("SELECT id, opportunity_id, status FROM validation_plans WHERE id = ? AND owner_id = ?", (values["validation_plan_id"], owner_id)).fetchone()
                if plan is None:
                    raise OpportunityNotFound(str(values["validation_plan_id"]))
                if str(plan["status"]) not in {"ready", "in_progress", "completed"}:
                    raise OpportunityConflict("validation plan must be approved before creating an action")
            source_type = str(values["source_type"])
            source_id = str(values["source_id"])
            if source_type != "manual":
                self._assert_source_owner(
                    connection,
                    owner_id=owner_id,
                    source_type=source_type,
                    source_id=source_id,
                    content_id=source_id if source_type in {"content", "evidence"} else None,
                )
            if source_type == "opportunity" and values.get("opportunity_id") != source_id:
                raise OpportunityConflict("action source opportunity must match opportunity_id")
            connection.execute(
                "INSERT INTO opportunity_actions (id, owner_id, opportunity_id, validation_plan_id, source_type, source_id, action_type, title, why, expected_result, success_criteria, status, user_notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?)",
                (identifier, owner_id, values.get("opportunity_id"), values.get("validation_plan_id"), values["source_type"], values["source_id"], values["action_type"], values["title"], values["why"], values["expected_result"], values["success_criteria"], values.get("user_notes"), now, now),
            )
            row = connection.execute("SELECT * FROM opportunity_actions WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise OpportunityConflict("action could not be persisted")
        result = self._decode_action(row)
        result["outcomes"] = []
        return result

    def update_action(self, *, owner_id: str, action_id: str, status: str, user_notes: str | None) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM opportunity_actions WHERE id = ? AND owner_id = ?", (action_id, owner_id)).fetchone()
            if row is None:
                raise OpportunityNotFound(action_id)
            allowed: dict[str, set[str]] = {
                "proposed": {"approved", "abandoned"},
                "approved": {"in_progress", "abandoned"},
                "in_progress": {"completed", "abandoned"},
                "completed": set(),
                "abandoned": set(),
            }
            if status not in allowed.get(str(row["status"]), set()):
                raise OpportunityConflict(f"action cannot transition to {status}")
            started = now if status == "in_progress" else None
            completed = now if status == "completed" else None
            connection.execute("UPDATE opportunity_actions SET status = ?, user_notes = COALESCE(?, user_notes), started_at = COALESCE(started_at, ?), completed_at = COALESCE(completed_at, ?), updated_at = ? WHERE id = ?", (status, user_notes, started, completed, now, action_id))
            if row["opportunity_id"] and status in {"approved", "in_progress"}:
                connection.execute("UPDATE opportunities SET status = 'converted_to_action', updated_at = ? WHERE id = ? AND status IN ('accepted', 'validation_ready', 'validated', 'review_ready')", (now, row["opportunity_id"]))
            refreshed = connection.execute("SELECT * FROM opportunity_actions WHERE id = ?", (action_id,)).fetchone()
        if refreshed is None:
            raise OpportunityNotFound(action_id)
        result = self._decode_action(refreshed)
        result["outcomes"] = []
        return result

    def record_outcome(self, *, owner_id: str, action_id: str, values: Mapping[str, object]) -> dict[str, object]:
        now = utc_now()
        outcome_id = _new_id()
        memory_id = _new_id()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            action = connection.execute("SELECT * FROM opportunity_actions WHERE id = ? AND owner_id = ?", (action_id, owner_id)).fetchone()
            if action is None:
                raise OpportunityNotFound(action_id)
            if str(action["status"]) != "completed":
                raise OpportunityConflict("complete the action before recording its outcome")
            connection.execute(
                "INSERT INTO action_outcomes (id, owner_id, action_id, what_happened, result, evidence_json, metrics_json, lesson, next_step, published_url, manual_views, manual_engagement, user_observation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (outcome_id, owner_id, action_id, values["what_happened"], values["result"], _dump(values["evidence"]), _dump(values["metrics"]), values["lesson"], values["next_step"], values.get("published_url"), values.get("manual_views"), values.get("manual_engagement"), values.get("user_observation"), now),
            )
            opportunity_id = action["opportunity_id"]
            memory_key = f"opportunity:{opportunity_id or action_id}:outcome"
            memory_value = {
                "what_happened": values["what_happened"],
                "result": values["result"],
                "lesson": values["lesson"],
                "next_step": values["next_step"],
                "outcome_id": outcome_id,
            }
            connection.execute("UPDATE research_memory_items SET is_current = 0, updated_at = ? WHERE memory_key = ? AND is_current = 1", (now, memory_key))
            connection.execute(
                "INSERT INTO research_memory_items (id, research_task_id, memory_type, memory_key, value_json, source_content_id, source_query_id, source_finding_id, confidence, is_current, created_at, updated_at, source_opportunity_id, source_action_id, source_outcome_id) VALUES (?, NULL, 'opportunity_outcome', ?, ?, NULL, NULL, NULL, ?, 1, ?, ?, ?, ?, ?)",
                (memory_id, memory_key, _dump(memory_value), 0.8 if values["result"] else 0.5, now, now, opportunity_id, action_id, outcome_id),
            )
            connection.execute("UPDATE action_outcomes SET memory_update_id = ? WHERE id = ?", (memory_id, outcome_id))
            row = connection.execute("SELECT * FROM action_outcomes WHERE id = ?", (outcome_id,)).fetchone()
        if row is None:
            raise OpportunityConflict("outcome could not be persisted")
        result = dict(row)
        result["evidence"] = _list(result.pop("evidence_json", "[]"))
        result["metrics"] = _dict(result.pop("metrics_json", "{}"))
        result.pop("owner_id", None)
        return result

    def list_memory_updates(self, *, owner_id: str, opportunity_id: str | None = None, limit: int = 30) -> list[dict[str, object]]:
        bounded = max(1, min(limit, 100))
        with connect_database(self.database_path) as connection:
            clause = "memory.source_opportunity_id IS NOT NULL AND opportunity.owner_id = ?"
            values: list[object] = [owner_id]
            if opportunity_id:
                clause += " AND memory.source_opportunity_id = ?"
                values.append(opportunity_id)
            values.append(bounded)
            rows = connection.execute(
                f"""
                SELECT memory.id, memory.memory_type, memory.memory_key, memory.value_json,
                       memory.confidence, memory.is_current, memory.source_opportunity_id,
                       memory.source_action_id, memory.source_outcome_id, memory.created_at,
                       memory.updated_at
                FROM research_memory_items memory
                LEFT JOIN opportunities opportunity ON opportunity.id = memory.source_opportunity_id
                WHERE {clause}
                ORDER BY memory.updated_at DESC, memory.id DESC LIMIT ?
                """,
                values,
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["value"] = _dict(item.pop("value_json", "{}"))
            item["is_current"] = _bool(item.get("is_current"))
            result.append(item)
        return result

    def analysis_source(self, *, owner_id: str, source_type: str, source_id: str) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            self._assert_source_owner(connection, owner_id=owner_id, source_type=source_type, source_id=source_id)
            if source_type == "research_task":
                rows = connection.execute(
                    """
                    SELECT f.id AS finding_id, fc.content_id, c.platform, c.title, c.description,
                           c.source_url, c.author_name, c.published_at, fc.support_type,
                           fc.support_strength, fc.support_explanation,
                           fc.source_independence, COALESCE(cd.is_repost, 0) AS is_repost,
                           (c.platform || ':' || COALESCE(c.author_name, c.id)) AS independent_group,
                           f.statement, f.kind,
                           f.counterevidence_status
                    FROM findings f
                    LEFT JOIN finding_contents fc ON fc.finding_id = f.id
                    LEFT JOIN library_contents c ON c.id = fc.content_id
                    LEFT JOIN research_content_decisions cd
                      ON cd.research_task_id = f.research_task_id AND cd.content_id = fc.content_id
                    WHERE f.research_task_id = ?
                    ORDER BY f.updated_at DESC, c.updated_at DESC
                    LIMIT 100
                    """,
                    (source_id,),
                ).fetchall()
                return [dict(row) for row in rows if row["content_id"]]
            if source_type == "discovery_candidate":
                rows = connection.execute(
                    """
                    SELECT candidate.id AS candidate_id, candidate.title, candidate.summary,
                           source.content_id, source.platform, source.source_title, source.source_url,
                           source.is_repost, source.independent_group, candidate.candidate_type
                    FROM research_discovery_candidates candidate
                    LEFT JOIN research_discovery_candidate_sources source ON source.candidate_id = candidate.id
                    WHERE candidate.id = ? AND candidate.owner_id = ?
                    ORDER BY source.created_at, source.id LIMIT 100
                    """,
                    (source_id, owner_id),
                ).fetchall()
                return [dict(row) for row in rows if row["content_id"]]
            if source_type == "monitoring_change":
                rows = connection.execute(
                    """
                    SELECT change.id AS monitoring_change_id, change.title, change.summary,
                           source.content_id, source.platform, source.source_title, source.source_url,
                           source.is_repost, source.independent_group, change.change_type
                    FROM monitoring_changes change
                    JOIN monitoring_missions mission ON mission.id = change.mission_id
                    LEFT JOIN monitoring_change_sources source ON source.change_id = change.id
                    WHERE change.id = ? AND mission.owner_id = ?
                    ORDER BY source.created_at, source.id LIMIT 100
                    """,
                    (source_id, owner_id),
                ).fetchall()
                return [dict(row) for row in rows if row["content_id"]]
            if source_type == "research_space":
                rows = connection.execute(
                    """
                    SELECT item.item_type, item.item_id, item.note,
                           candidate.title, candidate.summary, candidate.source_content_id AS content_id,
                           candidate.source_platform AS platform
                    FROM research_space_items item
                    LEFT JOIN research_discovery_candidates candidate
                      ON item.item_type = 'discovery_candidate' AND candidate.id = item.item_id
                    WHERE item.space_id = ?
                    ORDER BY item.position, item.created_at LIMIT 100
                    """,
                    (source_id,),
                ).fetchall()
                return [dict(row) for row in rows if row["content_id"]]
            return []
