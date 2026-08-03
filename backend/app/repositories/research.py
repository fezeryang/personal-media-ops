from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

from app.db import connect_database

TERMINAL_STATUSES = {"Done", "Failed", "Cancelled"}
RUNNABLE_STATUSES = {"Draft", "Planning", "Researching", "Summarizing", "BudgetExceeded"}


class ResearchTaskConflict(RuntimeError):
    pass


class ResearchTaskNotFound(KeyError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json(value: object, default: object) -> object:
    if not isinstance(value, str):
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _normalized_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", value.casefold()))


def _text_hash(value: object) -> str | None:
    normalized = _normalized_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None


def _decimal(value: object) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def _duration_millis(started_at: object, finished_at: object) -> int | None:
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return None
    try:
        started = datetime.fromisoformat(started_at).astimezone(UTC)
        finished = datetime.fromisoformat(finished_at).astimezone(UTC)
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds() * 1000))


def _row_to_task(row: sqlite3.Row) -> dict[str, object]:
    task = dict(row)
    for field, default in (
        ("platforms", []),
        ("plan", {}),
        ("context", {}),
        ("result", None),
        ("execution_trace", []),
        ("proposed_actions", []),
        ("route_snapshot", {}),
    ):
        task[field] = _json(task.get(field), default)
    task["paused"] = bool(task["paused"])
    task["budget_cost_enabled"] = bool(task["budget_cost_enabled"])
    task["estimated_cost"] = _decimal(task.get("estimated_cost"))
    task["budget_cost_limit"] = _decimal(task.get("budget_cost_limit"))
    task["budget_max_payg_amount"] = _decimal(task.get("budget_max_payg_amount"))
    return task


class ResearchTaskRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    def create(
        self,
        *,
        user_id: str,
        objective: str,
        platforms: list[str],
        crawl_limit: int,
        content_limit: int,
        duration_seconds: int,
        token_limit: int,
        cost_limit: str | None,
        cost_currency: str | None,
        coverage: dict[str, object] | None = None,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_model_calls: int = 100,
        route_policy: str = "balanced",
        max_total_tokens: int | None = None,
        max_crawl_tasks: int | None = None,
        max_new_contents: int | None = None,
        max_runtime_seconds: int | None = None,
        max_payg_amount: str | None = None,
        budget_currency: str | None = None,
    ) -> dict[str, object]:
        identifier = self.new_id()
        now = utc_now()
        requested_coverage = coverage if isinstance(coverage, dict) else {}
        target_platform_count = int(
            requested_coverage.get("target_platform_count", min(3, len(platforms)))
        )
        target_platform_count = max(0, min(len(platforms), target_platform_count))
        coverage_values = {
            "target_platform_count": target_platform_count,
            "target_entity_count": int(requested_coverage.get("target_entity_count", 3)),
            "target_negative_evidence_count": int(
                requested_coverage.get("target_negative_evidence_count", 1)
            ),
            "max_single_entity_evidence_ratio": float(
                requested_coverage.get("max_single_entity_evidence_ratio", 0.6)
            ),
            "target_independent_evidence_count": int(
                requested_coverage.get("target_independent_evidence_count", 5)
            ),
            "target_new_content_count": int(
                requested_coverage.get("target_new_content_count", 5)
            ),
            "low_marginal_value_threshold": float(
                requested_coverage.get("low_marginal_value_threshold", 0.1)
            ),
            "low_marginal_round_limit": int(
                requested_coverage.get("low_marginal_round_limit", 2)
            ),
        }
        if max_input_tokens is None:
            max_input_tokens = token_limit
        if max_output_tokens is None:
            max_output_tokens = token_limit
        max_total_tokens = max_total_tokens if max_total_tokens is not None else token_limit
        max_crawl_tasks = max_crawl_tasks if max_crawl_tasks is not None else crawl_limit
        max_new_contents = max_new_contents if max_new_contents is not None else content_limit
        max_runtime_seconds = max_runtime_seconds if max_runtime_seconds is not None else duration_seconds
        max_payg_amount = max_payg_amount if max_payg_amount is not None else cost_limit
        budget_currency = budget_currency if budget_currency is not None else cost_currency
        # The user may configure a limit before model prices exist. It is only
        # enabled after planning confirms a complete price snapshot.
        budget_cost_enabled = 0
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO research_tasks (
                    id, user_id, task_type, objective, platforms, status,
                    plan, context, result, execution_trace, proposed_actions,
                    route_snapshot, budget_crawl_limit, budget_content_limit,
                    budget_duration_seconds, budget_token_limit,
                    budget_cost_limit, budget_cost_currency, budget_cost_enabled,
                    consumed_crawl_count, consumed_content_count,
                    consumed_duration_seconds, input_tokens, output_tokens,
                    cached_tokens, estimated_cost, current_round, current_step,
                    waiting_crawl_task_id, paused, failure_reason, created_at,
                    started_at, updated_at, finished_at,
                    budget_max_total_tokens, budget_max_crawl_tasks,
                    budget_max_new_contents, budget_max_runtime_seconds,
                    budget_max_payg_amount, budget_currency,
                    budget_max_input_tokens, budget_max_output_tokens,
                    budget_max_model_calls, consumed_model_call_count,
                    route_policy, stop_reason, last_checkpoint_at
                ) VALUES (
                    :id, :user_id, 'research', :objective, :platforms, 'Draft',
                    '{}', '{}', NULL, '[]', '[]', '{}',
                    :crawl_limit, :content_limit, :duration_seconds, :token_limit,
                    :cost_limit, :cost_currency, :cost_enabled,
                    0, 0, 0, 0, 0, 0, NULL, 0, NULL, NULL, 0, NULL,
                    :now, NULL, :now, NULL,
                    :max_total_tokens, :max_crawl_tasks, :max_new_contents,
                    :max_runtime_seconds, :max_payg_amount, :budget_currency,
                    :max_input_tokens, :max_output_tokens, :max_model_calls, 0,
                    :route_policy, NULL, NULL
                )
                """,
                {
                    "id": identifier,
                    "user_id": user_id,
                    "objective": objective,
                    "platforms": _dump(platforms),
                    "crawl_limit": crawl_limit,
                    "content_limit": content_limit,
                    "duration_seconds": duration_seconds,
                    "token_limit": token_limit,
                    "cost_limit": cost_limit,
                    "cost_currency": cost_currency,
                    "cost_enabled": budget_cost_enabled,
                    "now": now,
                    "max_total_tokens": max_total_tokens,
                    "max_crawl_tasks": max_crawl_tasks,
                    "max_new_contents": max_new_contents,
                    "max_runtime_seconds": max_runtime_seconds,
                    "max_payg_amount": max_payg_amount,
                    "budget_currency": budget_currency,
                    "max_input_tokens": max_input_tokens,
                    "max_output_tokens": max_output_tokens,
                    "max_model_calls": max_model_calls,
                    "route_policy": route_policy,
                },
            )
            coverage_id = self.new_id()
            connection.execute(
                """
                INSERT INTO research_coverage_plans (
                    id, research_task_id, target_platform_count, target_entity_count,
                    target_negative_evidence_count, max_single_entity_evidence_ratio,
                    target_independent_evidence_count, target_new_content_count,
                    low_marginal_value_threshold, low_marginal_round_limit,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coverage_id,
                    identifier,
                    coverage_values["target_platform_count"],
                    coverage_values["target_entity_count"],
                    coverage_values["target_negative_evidence_count"],
                    coverage_values["max_single_entity_evidence_ratio"],
                    coverage_values["target_independent_evidence_count"],
                    coverage_values["target_new_content_count"],
                    coverage_values["low_marginal_value_threshold"],
                    coverage_values["low_marginal_round_limit"],
                    now,
                    now,
                ),
            )
            for order_index, platform in enumerate(platforms):
                connection.execute(
                    """
                    INSERT INTO research_platform_coverage (
                        id, research_task_id, platform, order_index,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (self.new_id(), identifier, platform, order_index, now, now),
                )
            self._append_trace_connection(
                connection,
                identifier,
                event="created",
                status="Draft",
                reason="owner_created_task",
                round_number=0,
                step="created",
            )
        task = self.get(user_id=user_id, task_id=identifier, detail=True)
        if task is None:
            raise RuntimeError("created research task could not be read")
        return task

    def save_intent(
        self,
        task_id: str,
        contract: dict[str, object],
        *,
        change_reason: str = "intent_interpreted",
    ) -> dict[str, object]:
        """Persist one auditable Intent Contract and its version snapshot."""
        now = utc_now()
        encoded_fields = {
            "secondary_intents_json": contract.get("secondary_intents", []),
            "subject_json": contract.get("subject", {}),
            "known_entities_json": contract.get("known_entities", []),
            "known_constraints_json": contract.get("known_constraints", []),
            "unknowns_to_discover_json": contract.get("unknowns_to_discover", []),
            "time_scope_json": contract.get("time_scope", {}),
            "platform_preferences_json": contract.get("platform_preferences", []),
            "evidence_requirements_json": contract.get("evidence_requirements", []),
            "negative_evidence_requirements_json": contract.get("negative_evidence_requirements", []),
            "exclusions_json": contract.get("exclusions", []),
            "desired_output_json": contract.get("desired_output", []),
            "success_criteria_json": contract.get("success_criteria", []),
            "ambiguities_json": contract.get("ambiguities", []),
            "assumptions_json": contract.get("assumptions", []),
            "intent_revisions_json": contract.get("intent_revisions", []),
        }
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT objective FROM research_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if task is None:
                raise ResearchTaskNotFound(task_id)
            existing = connection.execute(
                "SELECT id, version FROM research_intents WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()
            version = max(1, int(contract.get("version") or 1))
            if existing is not None:
                version = max(int(existing["version"]) + 1, version)
            contract = dict(contract)
            contract.update(
                {
                    "original_request": str(contract.get("original_request") or task["objective"]),
                    "original_intent": str(contract.get("original_intent") or task["objective"]),
                    "version": version,
                    "created_at": str(contract.get("created_at") or now),
                    "updated_at": now,
                }
            )
            intent_id = str(existing["id"]) if existing is not None else self.new_id()
            values = {
                "id": intent_id,
                "task_id": task_id,
                "original_request": contract["original_request"],
                "original_intent": contract["original_intent"],
                "interpreted_goal": str(contract.get("interpreted_goal") or contract["original_request"]),
                "primary_intent": str(contract.get("primary_intent") or "discovery"),
                "target_audience": contract.get("target_audience"),
                "current_research_hypothesis": str(
                    contract.get("current_research_hypothesis")
                    or contract.get("interpreted_goal")
                    or contract["original_request"]
                ),
                "intent_source": str(contract.get("intent_source") or "fallback_default"),
                "version": version,
                "confidence": max(0.0, min(1.0, float(contract.get("confidence") or 0))),
                "created_at": str(contract["created_at"]),
                "updated_at": now,
            }
            values.update({key: _dump(value) for key, value in encoded_fields.items()})
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO research_intents (
                        id, research_task_id, original_request, original_intent,
                        interpreted_goal, primary_intent, secondary_intents_json,
                        subject_json, known_entities_json, known_constraints_json,
                        unknowns_to_discover_json, time_scope_json,
                        platform_preferences_json, target_audience,
                        evidence_requirements_json, negative_evidence_requirements_json,
                        exclusions_json, desired_output_json, success_criteria_json,
                        confidence, ambiguities_json, assumptions_json,
                        current_research_hypothesis, intent_revisions_json,
                        intent_source, version, created_at, updated_at
                    ) VALUES (
                        :id, :task_id, :original_request, :original_intent,
                        :interpreted_goal, :primary_intent, :secondary_intents_json,
                        :subject_json, :known_entities_json, :known_constraints_json,
                        :unknowns_to_discover_json, :time_scope_json,
                        :platform_preferences_json, :target_audience,
                        :evidence_requirements_json, :negative_evidence_requirements_json,
                        :exclusions_json, :desired_output_json, :success_criteria_json,
                        :confidence, :ambiguities_json, :assumptions_json,
                        :current_research_hypothesis, :intent_revisions_json,
                        :intent_source, :version, :created_at, :updated_at
                    )
                    """,
                    values,
                )
            else:
                connection.execute(
                    """
                    UPDATE research_intents SET
                        original_request = :original_request,
                        original_intent = :original_intent,
                        interpreted_goal = :interpreted_goal,
                        primary_intent = :primary_intent,
                        secondary_intents_json = :secondary_intents_json,
                        subject_json = :subject_json,
                        known_entities_json = :known_entities_json,
                        known_constraints_json = :known_constraints_json,
                        unknowns_to_discover_json = :unknowns_to_discover_json,
                        time_scope_json = :time_scope_json,
                        platform_preferences_json = :platform_preferences_json,
                        target_audience = :target_audience,
                        evidence_requirements_json = :evidence_requirements_json,
                        negative_evidence_requirements_json = :negative_evidence_requirements_json,
                        exclusions_json = :exclusions_json,
                        desired_output_json = :desired_output_json,
                        success_criteria_json = :success_criteria_json,
                        confidence = :confidence,
                        ambiguities_json = :ambiguities_json,
                        assumptions_json = :assumptions_json,
                        current_research_hypothesis = :current_research_hypothesis,
                        intent_revisions_json = :intent_revisions_json,
                        intent_source = :intent_source,
                        version = :version,
                        updated_at = :updated_at
                    WHERE id = :id
                    """,
                    values,
                )
                connection.execute(
                    "UPDATE research_intent_assumptions SET status = 'superseded' WHERE research_task_id = ? AND status = 'active'",
                    (task_id,),
                )
            connection.execute(
                """
                INSERT INTO research_intent_versions (
                    id, research_task_id, version, contract_json, change_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.new_id(), task_id, version, _dump(contract), change_reason, now),
            )
            for assumption in contract.get("assumptions", []):
                if not isinstance(assumption, str) or not assumption.strip():
                    continue
                connection.execute(
                    """
                    INSERT INTO research_intent_assumptions (
                        id, research_task_id, intent_version, assumption, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.new_id(), task_id, version, assumption.strip(), now),
                )
            for priority, unknown in enumerate(contract.get("unknowns_to_discover", [])):
                if not isinstance(unknown, str) or not unknown.strip():
                    continue
                connection.execute(
                    """
                    INSERT INTO research_unknowns (
                        id, research_task_id, unknown, priority, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(research_task_id, unknown) DO UPDATE SET
                        priority = excluded.priority, updated_at = excluded.updated_at
                    """,
                    (self.new_id(), task_id, unknown.strip(), priority, now, now),
                )
            self._append_trace_connection(
                connection,
                task_id,
                event="intent_interpreted",
                status=None,
                reason=change_reason,
                round_number=0,
                step="intent_interpretation",
                tool_arguments={
                    "intent_id": intent_id,
                    "primary_intent": values["primary_intent"],
                    "confidence": values["confidence"],
                    "version": version,
                    "intent_source": values["intent_source"],
                },
            )
        return self.get_intent(task_id)

    def get_intent(self, task_id: str) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM research_intents WHERE research_task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(task_id)
        item = dict(row)
        for field, default in (
            ("secondary_intents_json", []),
            ("subject_json", {}),
            ("known_entities_json", []),
            ("known_constraints_json", []),
            ("unknowns_to_discover_json", []),
            ("time_scope_json", {}),
            ("platform_preferences_json", []),
            ("evidence_requirements_json", []),
            ("negative_evidence_requirements_json", []),
            ("exclusions_json", []),
            ("desired_output_json", []),
            ("success_criteria_json", []),
            ("ambiguities_json", []),
            ("assumptions_json", []),
            ("intent_revisions_json", []),
        ):
            item[field.removesuffix("_json")] = _json(item.get(field), default)
            item.pop(field, None)
        item["clarification_question"] = (
            item.get("ambiguities", [None])[0]
            if float(item.get("confidence") or 0) < 0.45
            and isinstance(item.get("ambiguities"), list)
            and item.get("ambiguities")
            else None
        )
        return item

    def record_information_utility(
        self,
        *,
        task_id: str,
        content_id: str,
        utility_type: str,
        rationale: str,
        confidence: float = 0.5,
        query_id: str | None = None,
        finding_id: str | None = None,
    ) -> dict[str, object]:
        allowed = {
            "core_evidence", "discovery_seed", "background_context", "event_signal",
            "counterevidence", "memory_update", "action_trigger", "noise", "duplicate",
        }
        if utility_type not in allowed:
            raise ValueError("unsupported information utility")
        if not rationale.strip():
            raise ValueError("information utility rationale is required")
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO content_research_utilities (
                    id, research_task_id, content_id, utility_type, rationale,
                    confidence, research_query_id, source_finding_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(research_task_id, content_id, utility_type) DO UPDATE SET
                    rationale = excluded.rationale,
                    confidence = MAX(content_research_utilities.confidence, excluded.confidence),
                    research_query_id = COALESCE(excluded.research_query_id, content_research_utilities.research_query_id),
                    source_finding_id = COALESCE(excluded.source_finding_id, content_research_utilities.source_finding_id)
                """,
                (
                    self.new_id(), task_id, content_id, utility_type, rationale[:500],
                    max(0.0, min(1.0, confidence)), query_id, finding_id, now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM content_research_utilities WHERE research_task_id = ? AND content_id = ? AND utility_type = ?",
                (task_id, content_id, utility_type),
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(content_id)
        return dict(row)

    def save_entity_candidate(
        self,
        *,
        task_id: str,
        entity_type: str,
        normalized_name: str,
        source_content_id: str | None,
        relevance_to_intent: float,
        novelty: float,
        confidence: float,
        suggested_next_action: str | None,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_entity_candidates (
                    id, research_task_id, entity_type, normalized_name,
                    source_content_id, relevance_to_intent, novelty, confidence,
                    suggested_next_action, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(research_task_id, normalized_name, entity_type) DO UPDATE SET
                    source_content_id = COALESCE(excluded.source_content_id, research_entity_candidates.source_content_id),
                    relevance_to_intent = MAX(research_entity_candidates.relevance_to_intent, excluded.relevance_to_intent),
                    novelty = MAX(research_entity_candidates.novelty, excluded.novelty),
                    confidence = MAX(research_entity_candidates.confidence, excluded.confidence),
                    suggested_next_action = COALESCE(excluded.suggested_next_action, research_entity_candidates.suggested_next_action),
                    updated_at = excluded.updated_at
                """,
                (
                    self.new_id(), task_id, entity_type, normalized_name.strip(), source_content_id,
                    max(0.0, min(1.0, relevance_to_intent)), max(0.0, min(1.0, novelty)),
                    max(0.0, min(1.0, confidence)), suggested_next_action, now, now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_entity_candidates WHERE research_task_id = ? AND normalized_name = ? AND entity_type = ?",
                (task_id, normalized_name.strip(), entity_type),
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(normalized_name)
        return dict(row)

    def save_event_candidate(
        self,
        *,
        task_id: str,
        event_type: str,
        title: str,
        summary: str,
        source_content_id: str | None,
        confidence: float,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT id FROM research_event_candidates WHERE research_task_id = ? AND title = ? AND source_content_id IS ?",
                (task_id, title, source_content_id),
            ).fetchone()
            identifier = str(row["id"]) if row is not None else self.new_id()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO research_event_candidates (
                        id, research_task_id, event_type, title, summary,
                        source_content_id, confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, task_id, event_type, title[:300], summary[:1_000], source_content_id, max(0.0, min(1.0, confidence)), now, now),
                )
            else:
                connection.execute(
                    "UPDATE research_event_candidates SET summary = ?, confidence = MAX(confidence, ?), updated_at = ? WHERE id = ?",
                    (summary[:1_000], max(0.0, min(1.0, confidence)), now, identifier),
                )
            saved = connection.execute("SELECT * FROM research_event_candidates WHERE id = ?", (identifier,)).fetchone()
        if saved is None:
            raise ResearchTaskNotFound(title)
        return dict(saved)

    def save_memory_item(
        self,
        *,
        task_id: str,
        memory_type: str,
        memory_key: str,
        value: object,
        confidence: float,
        content_id: str | None = None,
        query_id: str | None = None,
        finding_id: str | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_memory_items SET is_current = 0, updated_at = ? WHERE research_task_id = ? AND memory_type = ? AND memory_key = ? AND is_current = 1",
                (now, task_id, memory_type, memory_key),
            )
            identifier = self.new_id()
            connection.execute(
                """
                INSERT INTO research_memory_items (
                    id, research_task_id, memory_type, memory_key, value_json,
                    source_content_id, source_query_id, source_finding_id,
                    confidence, is_current, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (identifier, task_id, memory_type, memory_key, _dump(value), content_id, query_id, finding_id, max(0.0, min(1.0, confidence)), now, now),
            )
            row = connection.execute("SELECT * FROM research_memory_items WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise ResearchTaskNotFound(memory_key)
        item = dict(row)
        item["value"] = _json(item.pop("value_json"), None)
        item["is_current"] = bool(item["is_current"])
        return item

    def list_memory_keys(self, *, exclude_task_id: str | None = None) -> list[str]:
        with connect_database(self.database_path) as connection:
            if exclude_task_id is None:
                rows = connection.execute(
                    "SELECT DISTINCT memory_key FROM research_memory_items WHERE is_current = 1"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT DISTINCT memory_key FROM research_memory_items
                    WHERE is_current = 1 AND research_task_id != ?
                    """,
                    (exclude_task_id,),
                ).fetchall()
        return [str(row["memory_key"]) for row in rows if row["memory_key"]]

    def save_alignment_review(
        self,
        *,
        task_id: str,
        alignment_score: float,
        covered_requirements: list[str],
        missing_requirements: list[str],
        scope_drift: dict[str, object],
        recommended_next_step: str | None,
        review_status: str,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_alignment_reviews (
                    id, research_task_id, alignment_score, covered_requirements_json,
                    missing_requirements_json, scope_drift_json, recommended_next_step,
                    review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.new_id(), task_id, max(0.0, min(1.0, alignment_score)), _dump(covered_requirements), _dump(missing_requirements), _dump(scope_drift), recommended_next_step, review_status, now),
            )
            row = connection.execute(
                "SELECT * FROM research_alignment_reviews WHERE research_task_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(task_id)
        item = dict(row)
        for field, default in (("covered_requirements_json", []), ("missing_requirements_json", []), ("scope_drift_json", {})):
            item[field.removesuffix("_json")] = _json(item.pop(field), default)
        return item

    def _select_base(self) -> str:
        return """
            SELECT t.*,
                   (SELECT COUNT(*) FROM findings f
                    WHERE f.research_task_id = t.id) AS finding_count,
                   (SELECT COUNT(*) FROM events e
                    WHERE e.research_task_id = t.id) AS event_count,
                   (SELECT COUNT(*) FROM json_each(t.proposed_actions))
                    AS action_count
            FROM research_tasks t
        """

    def list(self, *, user_id: str) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                self._select_base()
                + " WHERE t.user_id = ? ORDER BY t.updated_at DESC, t.id DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_task(row) for row in rows]

    def get(
        self,
        *,
        user_id: str,
        task_id: str,
        detail: bool = False,
    ) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                self._select_base() + " WHERE t.id = ? AND t.user_id = ?",
                (task_id, user_id),
            ).fetchone()
            if row is None:
                return None
            task = _row_to_task(row)
            if not detail:
                return task
            task["findings"] = self._findings_connection(connection, task_id)
            task["queries"] = self._queries_connection(connection, task_id)
            task["events"] = self._events_connection(connection, task_id)
            self._attach_runtime_detail(connection, task, task_id)
        return task

    def get_for_runtime(
        self,
        task_id: str,
        *,
        detail: bool = False,
    ) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                self._select_base() + " WHERE t.id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            task = _row_to_task(row)
            if detail:
                task["findings"] = self._findings_connection(connection, task_id)
                task["queries"] = self._queries_connection(connection, task_id)
                task["events"] = self._events_connection(connection, task_id)
                self._attach_runtime_detail(connection, task, task_id)
        return task

    def _attach_runtime_detail(
        self,
        connection: sqlite3.Connection,
        task: dict[str, object],
        task_id: str,
    ) -> None:
        coverage = connection.execute(
            "SELECT * FROM research_coverage_plans WHERE research_task_id = ?",
            (task_id,),
        ).fetchone()
        if coverage is None:
            task["coverage"] = {
                "target_platform_count": min(3, len(task.get("platforms", []))),
                "target_entity_count": 3,
                "target_negative_evidence_count": 1,
                "max_single_entity_evidence_ratio": 0.6,
                "target_independent_evidence_count": 5,
                "target_new_content_count": 5,
                "low_marginal_value_threshold": 0.1,
                "low_marginal_round_limit": 2,
                "stop_reason": None,
            }
        else:
            task["coverage"] = {
                key: value
                for key, value in dict(coverage).items()
                if key not in {"id", "research_task_id", "created_at", "updated_at"}
            }
        task["platform_coverage"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT * FROM research_platform_coverage
                WHERE research_task_id = ? ORDER BY order_index, platform
                """,
                (task_id,),
            ).fetchall()
        ]
        entities = []
        for row in connection.execute(
            """
            SELECT canonical_name, entity_type, entity_query_count,
                   entity_evidence_count, entity_new_content_count,
                   entity_platform_count, entity_coverage_ratio, saturated
            FROM research_entity_coverage
            WHERE research_task_id = ?
            ORDER BY entity_evidence_count DESC, canonical_name
            """,
            (task_id,),
        ).fetchall():
            item = dict(row)
            item["saturated"] = bool(item.get("saturated"))
            entities.append(item)
        task["entity_coverage"] = entities
        task["content_decisions"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT content_id, research_query_id, decision,
                       not_adopted_reason, source_independence,
                       content_completeness, evidence_quality, is_repost,
                       repost_of_content_id, similarity_score
                FROM research_content_decisions
                WHERE research_task_id = ? ORDER BY created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        for item in task["content_decisions"]:
            item["is_repost"] = bool(item["is_repost"])
        task["step_usage"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT step, sequence, provider_instance_id, vendor, model,
                       billing_mode, estimated_cost, currency, price_source,
                       input_tokens, output_tokens, cached_tokens,
                       latency_ms, fallback_from_provider_instance_id,
                       fallback_reason, invocation_id, created_at
                FROM research_step_usage
                WHERE research_task_id = ? ORDER BY sequence, id
                """,
                (task_id,),
            ).fetchall()
        ]
        budget_events = []
        for row in connection.execute(
            """
            SELECT event_type, amount, unit, provider_instance_id, vendor,
                   billing_mode, currency, estimated_cost, reason, created_at
            FROM research_budget_events
            WHERE research_task_id = ? ORDER BY created_at, id
            """,
            (task_id,),
        ).fetchall():
            item = dict(row)
            item["amount"] = _decimal(item.get("amount"))
            item["estimated_cost"] = _decimal(item.get("estimated_cost"))
            budget_events.append(item)
        task["budget_events"] = budget_events
        task["billing_summary"] = ResearchTaskRepository._billing_summary_connection(
            connection, task_id
        )
        try:
            task["intent_contract"] = ResearchTaskRepository(
                Path(self.database_path)
            ).get_intent(task_id)
        except ResearchTaskNotFound:
            task["intent_contract"] = None
        task["intent_versions"] = [
            {
                **dict(row),
                "contract": _json(row["contract_json"], {}),
            }
            for row in connection.execute(
                """
                SELECT id, research_task_id, version, contract_json,
                       change_reason, created_at
                FROM research_intent_versions
                WHERE research_task_id = ? ORDER BY version, created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        for item in task["intent_versions"]:
            item.pop("contract_json", None)
        task["intent_assumptions"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, research_task_id, intent_version, assumption,
                       status, created_at, resolved_at
                FROM research_intent_assumptions
                WHERE research_task_id = ? ORDER BY created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        task["unknowns"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, research_task_id, unknown, priority, status, evidence_count,
                       resolution, created_at, updated_at
                FROM research_unknowns
                WHERE research_task_id = ? ORDER BY priority, created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        task["information_utilities"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, research_task_id, content_id, utility_type, rationale, confidence,
                       research_query_id, source_finding_id, created_at
                FROM content_research_utilities
                WHERE research_task_id = ? ORDER BY created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        task["entity_candidates"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, research_task_id, entity_type, normalized_name, source_content_id,
                       relevance_to_intent, novelty, confidence,
                       suggested_next_action, status, created_at, updated_at
                FROM research_entity_candidates
                WHERE research_task_id = ? ORDER BY confidence DESC, created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        task["event_candidates"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, research_task_id, event_type, title, summary, source_content_id,
                       confidence, status, created_at, updated_at
                FROM research_event_candidates
                WHERE research_task_id = ? ORDER BY created_at, id
                """,
                (task_id,),
            ).fetchall()
        ]
        memory_items = []
        for row in connection.execute(
            """
            SELECT id, research_task_id, memory_type, memory_key, value_json, source_content_id,
                   source_query_id, source_finding_id, confidence, is_current,
                   created_at, updated_at
            FROM research_memory_items
            WHERE research_task_id = ? ORDER BY updated_at DESC, id DESC
            """,
            (task_id,),
        ).fetchall():
            item = dict(row)
            item["value"] = _json(item.pop("value_json"), None)
            item["is_current"] = bool(item["is_current"])
            memory_items.append(item)
        task["memory_items"] = memory_items
        alignment = connection.execute(
            """
            SELECT id, research_task_id, alignment_score, covered_requirements_json,
                   missing_requirements_json, scope_drift_json,
                   recommended_next_step, review_status, created_at
            FROM research_alignment_reviews
            WHERE research_task_id = ? ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if alignment is None:
            task["alignment_review"] = None
        else:
            item = dict(alignment)
            for field, default in (
                ("covered_requirements_json", []),
                ("missing_requirements_json", []),
                ("scope_drift_json", {}),
            ):
                item[field.removesuffix("_json")] = _json(item.pop(field), default)
            task["alignment_review"] = item

    @staticmethod
    def _billing_summary_connection(
        connection: sqlite3.Connection,
        task_id: str,
    ) -> dict[str, object]:
        rows = connection.execute(
            """
            SELECT COALESCE(i.billing_mode, p.billing_mode, 'unknown') AS billing_mode,
                   COUNT(*) AS call_count,
                   COALESCE(SUM(i.input_tokens), 0) + COALESCE(SUM(i.output_tokens), 0) AS token_count,
                   SUM(i.estimated_cost) AS estimated_cost,
                   SUM(CASE
                       WHEN i.estimated_cost IS NULL
                        AND COALESCE(i.billing_mode, p.billing_mode, 'unknown') != 'subscription_fixed'
                       THEN 1 ELSE 0 END) AS uncosted_call_count
            FROM ai_model_invocations i
            JOIN ai_providers p ON p.id = i.provider_id
            WHERE i.research_task_id = ?
            GROUP BY COALESCE(i.billing_mode, p.billing_mode, 'unknown')
            ORDER BY billing_mode
            """,
            (task_id,),
        ).fetchall()
        result: dict[str, object] = {
            mode: {"calls": 0, "tokens": 0, "estimated_cost": None, "uncosted_calls": 0}
            for mode in (
                "subscription_fixed",
                "pay_as_you_go",
                "relay",
                "prepaid_balance",
                "quota_bundle",
                "unknown",
            )
        }
        for row in rows:
            mode = str(row["billing_mode"])
            if mode not in result:
                mode = "unknown"
            bucket = result[mode]
            if not isinstance(bucket, dict):
                continue
            bucket["calls"] = int(row["call_count"] or 0)
            bucket["tokens"] = int(row["token_count"] or 0)
            bucket["uncosted_calls"] = int(row["uncosted_call_count"] or 0)
            bucket["estimated_cost"] = _decimal(row["estimated_cost"])
        return result

    def list_normalized_queries(self, *, exclude_task_id: str | None = None) -> list[str]:
        with connect_database(self.database_path) as connection:
            if exclude_task_id is None:
                rows = connection.execute(
                    "SELECT normalized_query FROM research_queries"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT normalized_query FROM research_queries "
                    "WHERE research_task_id != ?",
                    (exclude_task_id,),
                ).fetchall()
        return [str(row["normalized_query"]) for row in rows]

    def create_query(
        self,
        *,
        task_id: str,
        intent_id: str | None = None,
        record_type: str = "execution_query",
        gate_status: str = "pending",
        decision: str = "allow",
        query_role: str = "seed_discovery",
        query: str,
        normalized_query: str,
        query_type: str,
        platform: str,
        source_type: str,
        source_content_id: str | None,
        source_finding_id: str | None,
        parent_query_id: str | None,
        generation_reason: str,
        specificity_score: float,
        novelty_score: float,
        noise_risk_score: float,
        relevance_score: float | None = None,
        expected_value_score: float | None = None,
        status: str = "candidate",
        rejection_reason: str | None = None,
        lifecycle_status: str | None = None,
        entity_diversity_bonus: float = 0,
        platform_diversity_bonus: float = 0,
        negative_evidence_bonus: float = 0,
        estimated_resource_use: float = 0,
        unexecuted_reason: str | None = None,
        expected_evidence_role: str | None = None,
    ) -> dict[str, object]:
        identifier = self.new_id()
        now = utc_now()
        resolved_lifecycle = lifecycle_status or {
            "candidate": "generated",
            "approved": "approved_pending",
            "rejected": "rejected_low_relevance",
            "running": "executing",
            "completed": "completed",
            "failed": "failed",
        }.get(status, status)
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM research_tasks WHERE id = ?", (task_id,)
            ).fetchone() is None:
                raise ResearchTaskNotFound(task_id)
            connection.execute(
                """
                INSERT INTO research_queries (
                    id, research_task_id, intent_id, record_type, gate_status,
                    decision, query_role, query, normalized_query, query_type,
                    platform, source_type, source_content_id, source_finding_id,
                    parent_query_id, generation_reason, relevance_score,
                    specificity_score, novelty_score, noise_risk_score,
                    expected_value_score, status, rejection_reason,
                    lifecycle_status, unexecuted_reason, entity_diversity_bonus,
                    platform_diversity_bonus, negative_evidence_bonus,
                    estimated_resource_use, expected_evidence_role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    task_id,
                    intent_id,
                    record_type,
                    gate_status,
                    decision,
                    query_role,
                    query,
                    normalized_query,
                    query_type,
                    platform,
                    source_type,
                    source_content_id,
                    source_finding_id,
                    parent_query_id,
                    generation_reason,
                    relevance_score,
                    specificity_score,
                    novelty_score,
                    noise_risk_score,
                    expected_value_score,
                    status,
                    rejection_reason,
                    resolved_lifecycle,
                    unexecuted_reason,
                    max(0.0, min(1.0, entity_diversity_bonus)),
                    max(0.0, min(1.0, platform_diversity_bonus)),
                    max(0.0, min(1.0, negative_evidence_bonus)),
                    max(0.0, estimated_resource_use),
                    expected_evidence_role,
                    now,
                    now,
                ),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="query_recorded",
                status=None,
                reason="quality_gate_candidate_persisted",
                step="query_gate",
                tool_name=None,
                tool_arguments={
                    "query_id": identifier,
                    "query": query[:500],
                    "status": status,
                    "record_type": record_type,
                    "gate_status": gate_status,
                    "decision": decision,
                    "query_role": query_role,
                    "lifecycle_status": resolved_lifecycle,
                    "rejection_reason": rejection_reason,
                    "unexecuted_reason": unexecuted_reason,
                },
            )
        return self.get_query(identifier)

    def get_query(self, query_id: str) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM research_queries WHERE id = ?", (query_id,)
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(query_id)
        return dict(row)

    def update_query_quality(
        self,
        query_id: str,
        *,
        relevance_score: float | None,
        expected_value_score: float | None,
        status: str,
        rejection_reason: str | None = None,
        lifecycle_status: str | None = None,
        unexecuted_reason: str | None = None,
    ) -> dict[str, object]:
        resolved_lifecycle = lifecycle_status or {
            "candidate": "generated",
            "approved": "approved_pending",
            "rejected": "rejected_low_relevance",
            "running": "executing",
            "completed": "completed",
            "failed": "failed",
        }.get(status, status)
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE research_queries
                SET relevance_score = ?, expected_value_score = ?, status = ?,
                    rejection_reason = ?, lifecycle_status = ?,
                    unexecuted_reason = ?, gate_status = ?, decision = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    relevance_score,
                    expected_value_score,
                    status,
                    rejection_reason,
                    resolved_lifecycle,
                    unexecuted_reason,
                    "reject" if status.startswith("rejected") or status == "rejected" else "allow",
                    "reject" if status.startswith("rejected") or status == "rejected" else "allow",
                    utc_now(),
                    query_id,
                ),
            )
        return self.get_query(query_id)

    def attach_query_crawler(self, query_id: str, crawler_task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_queries SET crawler_task_id = ?, status = 'running', lifecycle_status = 'executing', gate_status = 'allow', decision = 'allow', unexecuted_reason = NULL, updated_at = ? WHERE id = ?",
                (crawler_task_id, utc_now(), query_id),
            )

    def complete_query(
        self,
        query_id: str,
        *,
        result_count: int,
        new_content_count: int,
        existing_content_count: int,
        updated_content_count: int,
        duplicate_evidence_count: int,
        failed: bool = False,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE research_queries
                SET status = ?, executed_at = ?, result_count = ?,
                    new_content_count = ?, existing_content_count = ?,
                    updated_content_count = ?, duplicate_evidence_count = ?,
                    lifecycle_status = ?, gate_status = 'completed', decision = 'allow', unexecuted_reason = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    "failed" if failed else "completed",
                    utc_now(),
                    max(0, result_count),
                    max(0, new_content_count),
                    max(0, existing_content_count),
                    max(0, updated_content_count),
                    max(0, duplicate_evidence_count),
                    "failed" if failed else "completed",
                    utc_now(),
                    query_id,
                ),
            )

            query_row = connection.execute(
                "SELECT research_task_id FROM research_queries WHERE id = ?",
                (query_id,),
            ).fetchone()
            if query_row is not None:
                new_rate = (
                    max(0, new_content_count) / max(1, result_count)
                    if result_count
                    else 0.0
                )
                duplicate_rate = (
                    max(0, duplicate_evidence_count) / max(1, result_count)
                    if result_count
                    else 0.0
                )
                marginal = max(0.0, min(1.0, new_rate * 0.65 + (1 - duplicate_rate) * 0.35))
                connection.execute(
                    """
                    INSERT INTO research_query_metrics (
                        id, research_query_id, new_content_rate,
                        duplicate_rate, collected_result_count,
                        candidate_evidence_count, adopted_evidence_count,
                        not_adopted_count, marginal_value_score, measured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                    ON CONFLICT(research_query_id) DO UPDATE SET
                        new_content_rate = excluded.new_content_rate,
                        duplicate_rate = excluded.duplicate_rate,
                        collected_result_count = excluded.collected_result_count,
                        marginal_value_score = excluded.marginal_value_score,
                        measured_at = excluded.measured_at
                    """,
                    (
                        self.new_id(),
                        query_id,
                        new_rate,
                        duplicate_rate,
                        max(0, result_count),
                        max(0, result_count),
                        marginal,
                        utc_now(),
                    ),
                )

    def set_query_lifecycle(
        self,
        query_id: str,
        *,
        lifecycle_status: str,
        reason: str | None = None,
    ) -> None:
        """Persist the Phase 8C lifecycle while retaining 8C-1 status aliases."""
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE research_queries
                SET lifecycle_status = ?, unexecuted_reason = ?,
                    gate_status = CASE
                        WHEN ? IN ('skipped_budget', 'skipped_saturation', 'skipped_low_marginal_value', 'superseded') THEN 'hold'
                        WHEN ? IN ('rejected_generic', 'rejected_duplicate', 'rejected_low_relevance', 'rejected_low_value', 'cancelled') THEN 'reject'
                        ELSE gate_status END,
                    decision = CASE
                        WHEN ? IN ('skipped_budget', 'skipped_saturation', 'skipped_low_marginal_value', 'superseded') THEN 'hold'
                        WHEN ? IN ('rejected_generic', 'rejected_duplicate', 'rejected_low_relevance', 'rejected_low_value', 'cancelled') THEN 'reject'
                        ELSE decision END,
                    updated_at = ?
                WHERE id = ?
                """,
                (lifecycle_status, reason, lifecycle_status, lifecycle_status, lifecycle_status, lifecycle_status, utc_now(), query_id),
            )

    def claim_held_execution_query(
        self,
        task_id: str,
        *,
        platform: str,
        query_id: str | None = None,
    ) -> dict[str, object] | None:
        """Reuse the next durable plan direction on the next platform.

        A failed or completed platform must not discard the other execution
        directions generated from the Intent Contract. They were persisted as
        held queries during the first round; claiming one here preserves its
        audit identity while making the actual platform binding explicit.
        """
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM research_queries
                WHERE research_task_id = ?
                  AND record_type = 'execution_query'
                  AND status = 'approved'
                  AND lifecycle_status = 'skipped_low_marginal_value'
                  AND (? IS NULL OR id = ?)
                ORDER BY CASE query_role
                    WHEN 'cross_platform_validation' THEN 0
                    WHEN 'counterevidence' THEN 1
                    WHEN 'competitor_scan' THEN 2
                    WHEN 'trend_probe' THEN 3
                    WHEN 'creator_scan' THEN 4
                    WHEN 'pain_point_probe' THEN 5
                    ELSE 6
                END, created_at, id
                LIMIT 1
                """,
                (task_id, query_id, query_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            now = utc_now()
            query_id = str(row["id"])
            connection.execute(
                """
                UPDATE research_queries
                SET platform = ?, lifecycle_status = 'executing',
                    gate_status = 'allow', decision = 'allow',
                    unexecuted_reason = NULL, updated_at = ?
                WHERE id = ?
                """,
                (platform, now, query_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="query_reactivated",
                status=None,
                reason="下一平台继续执行 Intent Contract 已批准的查询方向",
                step="query_gate",
                tool_name=None,
                tool_arguments={
                    "query_id": query_id,
                    "old_platform": row["platform"],
                    "platform": platform,
                    "query_role": row["query_role"],
                },
            )
        return self.get_query(query_id)

    def rebind_execution_query_platform(
        self,
        query_id: str,
        *,
        platform: str,
        query: str,
        normalized_query: str,
    ) -> dict[str, object]:
        """Persist the platform-specific form of a reactivated direction."""
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT research_task_id, platform, query FROM research_queries WHERE id = ?",
                (query_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(query_id)
            now = utc_now()
            connection.execute(
                """
                UPDATE research_queries
                SET platform = ?, query = ?, normalized_query = ?, updated_at = ?
                WHERE id = ?
                """,
                (platform, query, normalized_query, now, query_id),
            )
            self._append_trace_connection(
                connection,
                str(row["research_task_id"]),
                event="query_platform_rebound",
                status=None,
                reason="跨平台复用 held 查询时重新绑定平台证据策略",
                step="query_gate",
                tool_name=None,
                tool_arguments={
                    "query_id": query_id,
                    "old_platform": row["platform"],
                    "new_platform": platform,
                    "old_query": row["query"],
                    "new_query": query,
                },
            )
        return self.get_query(query_id)

    def skip_pending_queries(
        self,
        task_id: str,
        *,
        lifecycle_status: str,
        reason: str,
    ) -> int:
        with connect_database(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE research_queries
                SET lifecycle_status = ?, unexecuted_reason = ?, updated_at = ?
                WHERE research_task_id = ?
                  AND lifecycle_status IN ('generated', 'approved_pending')
                """,
                (lifecycle_status, reason, utc_now(), task_id),
            )
            return int(cursor.rowcount)

    def record_query_metric(
        self,
        query_id: str,
        *,
        new_content_rate: float,
        new_entity_count: int,
        new_independent_evidence_count: int,
        duplicate_rate: float,
        model_token_cost: Decimal | str | None = None,
        payg_cost: Decimal | str | None = None,
        crawl_duration_ms: int | None = None,
        collected_result_count: int = 0,
        candidate_evidence_count: int = 0,
        adopted_evidence_count: int = 0,
        not_adopted_count: int = 0,
        marginal_value_score: float | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_query_metrics (
                    id, research_query_id, new_content_rate, new_entity_count,
                    new_independent_evidence_count, duplicate_rate,
                    model_token_cost, payg_cost, crawl_duration_ms,
                    collected_result_count, candidate_evidence_count,
                    adopted_evidence_count, not_adopted_count,
                    marginal_value_score, measured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(research_query_id) DO UPDATE SET
                    new_content_rate = excluded.new_content_rate,
                    new_entity_count = excluded.new_entity_count,
                    new_independent_evidence_count = excluded.new_independent_evidence_count,
                    duplicate_rate = excluded.duplicate_rate,
                    model_token_cost = excluded.model_token_cost,
                    payg_cost = excluded.payg_cost,
                    crawl_duration_ms = excluded.crawl_duration_ms,
                    collected_result_count = excluded.collected_result_count,
                    candidate_evidence_count = excluded.candidate_evidence_count,
                    adopted_evidence_count = excluded.adopted_evidence_count,
                    not_adopted_count = excluded.not_adopted_count,
                    marginal_value_score = excluded.marginal_value_score,
                    measured_at = excluded.measured_at
                """,
                (
                    self.new_id(),
                    query_id,
                    max(0.0, min(1.0, new_content_rate)),
                    max(0, new_entity_count),
                    max(0, new_independent_evidence_count),
                    max(0.0, min(1.0, duplicate_rate)),
                    str(model_token_cost) if model_token_cost is not None else None,
                    str(payg_cost) if payg_cost is not None else None,
                    max(0, crawl_duration_ms) if crawl_duration_ms is not None else None,
                    max(0, collected_result_count),
                    max(0, candidate_evidence_count),
                    max(0, adopted_evidence_count),
                    max(0, not_adopted_count),
                    (
                        max(0.0, min(1.0, marginal_value_score))
                        if marginal_value_score is not None
                        else None
                    ),
                    utc_now(),
                ),
            )

    def upsert_platform_coverage(
        self,
        task_id: str,
        platform: str,
        *,
        status: str | None = None,
        planned_query_count: int | None = None,
        actual_query_count: int | None = None,
        result_count: int | None = None,
        new_content_count: int | None = None,
        independent_evidence_count: int | None = None,
        negative_evidence_count: int | None = None,
        failure_reason: str | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[object] = []
        for name, value in (
            ("status", status),
            ("planned_query_count", planned_query_count),
            ("actual_query_count", actual_query_count),
            ("result_count", result_count),
            ("new_content_count", new_content_count),
            ("independent_evidence_count", independent_evidence_count),
            ("negative_evidence_count", negative_evidence_count),
            ("failure_reason", failure_reason),
        ):
            if value is not None:
                assignments.append(f"{name} = ?")
                if name in {"status", "failure_reason"}:
                    values.append(value)
                else:
                    values.append(max(0, int(value)))
        if not assignments:
            return
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.extend([task_id, platform])
        with connect_database(self.database_path) as connection:
            cursor = connection.execute(
                f"UPDATE research_platform_coverage SET {', '.join(assignments)} "
                "WHERE research_task_id = ? AND platform = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise ResearchTaskNotFound(f"platform coverage {task_id}/{platform}")

    def upsert_entity_coverage(
        self,
        task_id: str,
        canonical_name: str,
        *,
        entity_type: str = "product",
        query_count_delta: int = 0,
        evidence_count_delta: int = 0,
        new_content_count_delta: int = 0,
        platform: str | None = None,
    ) -> dict[str, object]:
        normalized = canonical_name.strip()
        if not normalized:
            raise ValueError("entity name must not be blank")
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM research_entity_coverage WHERE research_task_id = ? AND canonical_name = ?",
                (task_id, normalized),
            ).fetchone()
            if existing is None:
                identifier = self.new_id()
                connection.execute(
                    """
                    INSERT INTO research_entity_coverage (
                        id, research_task_id, canonical_name, entity_type,
                        entity_query_count, entity_evidence_count,
                        entity_new_content_count, entity_platform_count,
                        platforms_json, entity_coverage_ratio, saturated,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                    """,
                    (
                        identifier,
                        task_id,
                        normalized,
                        entity_type,
                        max(0, query_count_delta),
                        max(0, evidence_count_delta),
                        max(0, new_content_count_delta),
                        1 if platform else 0,
                        _dump([platform] if platform else []),
                        utc_now(),
                        utc_now(),
                    ),
                )
            else:
                existing_platforms = _json(existing["platforms_json"], [])
                existing_platforms = (
                    [str(item) for item in existing_platforms if isinstance(item, str)]
                    if isinstance(existing_platforms, list)
                    else []
                )
                if platform and platform not in existing_platforms:
                    existing_platforms.append(platform)
                connection.execute(
                    """
                    UPDATE research_entity_coverage
                    SET entity_query_count = entity_query_count + ?,
                        entity_evidence_count = entity_evidence_count + ?,
                        entity_new_content_count = entity_new_content_count + ?,
                        entity_platform_count = MIN(7, ?),
                        platforms_json = ?,
                        updated_at = ?
                    WHERE research_task_id = ? AND canonical_name = ?
                    """,
                    (
                        max(0, query_count_delta),
                        max(0, evidence_count_delta),
                        max(0, new_content_count_delta),
                        len(existing_platforms),
                        _dump(existing_platforms),
                        utc_now(),
                        task_id,
                        normalized,
                    ),
                )
            total = connection.execute(
                "SELECT COALESCE(SUM(entity_evidence_count), 0) FROM research_entity_coverage WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()[0]
            threshold_row = connection.execute(
                "SELECT max_single_entity_evidence_ratio FROM research_coverage_plans WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()
            concentration_threshold = float(
                threshold_row[0] if threshold_row is not None else 0.6
            )
            connection.execute(
                """
                UPDATE research_entity_coverage
                SET entity_coverage_ratio = CASE WHEN ? > 0 THEN entity_evidence_count * 1.0 / ? ELSE 0 END,
                    saturated = CASE WHEN ? > 0 AND entity_evidence_count * 1.0 / ? >= ? THEN 1 ELSE 0 END,
                    updated_at = ?
                WHERE research_task_id = ?
                """,
                (total, total, total, total, concentration_threshold, utc_now(), task_id),
            )
            row = connection.execute(
                "SELECT * FROM research_entity_coverage WHERE research_task_id = ? AND canonical_name = ?",
                (task_id, normalized),
            ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(normalized)
        result = dict(row)
        result["saturated"] = bool(result["saturated"])
        result.pop("platforms_json", None)
        return result

    def record_content_decision(
        self,
        *,
        task_id: str,
        content_id: str,
        query_id: str | None = None,
        decision: str = "candidate",
        not_adopted_reason: str | None = None,
    ) -> dict[str, object]:
        """Classify a content once and flag likely cross-platform reposts."""
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, platform, title, description, source_url,
                       author_name, published_at, raw_payload, created_at
                FROM library_contents WHERE id = ?
                """,
                (content_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(content_id)
            title_hash = _text_hash(row["title"])
            body_hash = _text_hash(f"{row['title'] or ''} {row['description'] or ''}")
            repost: sqlite3.Row | None = None
            similarity = None
            if row["source_url"]:
                repost = connection.execute(
                    """
                    SELECT id FROM library_contents
                    WHERE id != ? AND source_url = ?
                      AND (created_at < ? OR (created_at = ? AND id < ?))
                    ORDER BY created_at, id LIMIT 1
                    """,
                    (
                        content_id,
                        row["source_url"],
                        row["created_at"],
                        row["created_at"],
                        content_id,
                    ),
                ).fetchone()
            if repost is None and title_hash:
                repost = connection.execute(
                    """
                    SELECT id FROM library_contents
                    WHERE id != ? AND platform != ? AND title IS NOT NULL
                      AND lower(trim(title)) = lower(trim(?))
                      AND (created_at < ? OR (created_at = ? AND id < ?))
                    ORDER BY created_at, id LIMIT 1
                    """,
                    (
                        content_id,
                        row["platform"],
                        row["title"],
                        row["created_at"],
                        row["created_at"],
                        content_id,
                    ),
                ).fetchone()
            if repost is None and body_hash:
                candidates = connection.execute(
                    """
                    SELECT id, title, description, created_at FROM library_contents
                    WHERE id != ? AND platform != ? AND description IS NOT NULL
                      AND (created_at < ? OR (created_at = ? AND id < ?))
                    ORDER BY created_at, id
                    LIMIT 100
                    """,
                    (
                        content_id,
                        row["platform"],
                        row["created_at"],
                        row["created_at"],
                        content_id,
                    ),
                ).fetchall()
                current_text = _normalized_text(f"{row['title'] or ''} {row['description'] or ''}")
                for candidate in candidates:
                    candidate_text = _normalized_text(f"{candidate['title'] or ''} {candidate['description'] or ''}")
                    similarity = SequenceMatcher(None, current_text, candidate_text).ratio()
                    if similarity >= 0.88:
                        repost = candidate
                        break
            is_repost = repost is not None
            completeness = (
                "complete"
                if row["title"] and row["description"]
                else "partial"
                if row["title"]
                else "missing"
            )
            quality = "high" if row["title"] and row["description"] and row["source_url"] else "medium" if row["title"] else "low"
            now = utc_now()
            connection.execute(
                """
                INSERT INTO research_content_decisions (
                    id, research_task_id, content_id, research_query_id,
                    decision, not_adopted_reason, source_independence,
                    content_completeness, evidence_quality, is_repost,
                    repost_of_content_id, similarity_score, normalized_title_hash,
                    body_summary_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(research_task_id, content_id) DO UPDATE SET
                    research_query_id = COALESCE(excluded.research_query_id, research_content_decisions.research_query_id),
                    decision = CASE WHEN research_content_decisions.decision = 'adopted' THEN 'adopted' ELSE excluded.decision END,
                    not_adopted_reason = excluded.not_adopted_reason,
                    source_independence = excluded.source_independence,
                    content_completeness = excluded.content_completeness,
                    evidence_quality = excluded.evidence_quality,
                    is_repost = excluded.is_repost,
                    repost_of_content_id = excluded.repost_of_content_id,
                    similarity_score = excluded.similarity_score,
                    normalized_title_hash = excluded.normalized_title_hash,
                    body_summary_hash = excluded.body_summary_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    self.new_id(),
                    task_id,
                    content_id,
                    query_id,
                    decision,
                    not_adopted_reason,
                    "repost" if is_repost else "independent",
                    completeness,
                    quality,
                    int(is_repost),
                    str(repost["id"]) if repost is not None else None,
                    similarity,
                    title_hash,
                    body_hash,
                    now,
                    now,
                ),
            )
            saved = connection.execute(
                "SELECT * FROM research_content_decisions WHERE research_task_id = ? AND content_id = ?",
                (task_id, content_id),
            ).fetchone()
        if saved is None:
            raise ResearchTaskNotFound(content_id)
        result = dict(saved)
        result["is_repost"] = bool(result["is_repost"])
        return result

    def mark_content_adopted(self, task_id: str, content_ids: list[str]) -> None:
        if not content_ids:
            return
        with connect_database(self.database_path) as connection:
            placeholders = ",".join("?" for _ in content_ids)
            connection.execute(
                f"UPDATE research_content_decisions SET decision = 'adopted', not_adopted_reason = NULL, updated_at = ? WHERE research_task_id = ? AND content_id IN ({placeholders})",
                (utc_now(), task_id, *dict.fromkeys(content_ids)),
            )

    def refresh_coverage_metrics(self, task_id: str) -> None:
        """Recompute platform evidence counters from durable decisions."""
        with connect_database(self.database_path) as connection:
            platforms = connection.execute(
                "SELECT platform FROM research_platform_coverage WHERE research_task_id = ?",
                (task_id,),
            ).fetchall()
            now = utc_now()
            for row in platforms:
                platform = str(row["platform"])
                independent = connection.execute(
                    """
                    SELECT COUNT(DISTINCT cd.content_id)
                    FROM research_content_decisions cd
                    JOIN library_contents c ON c.id = cd.content_id
                    WHERE cd.research_task_id = ? AND c.platform = ?
                      AND cd.decision = 'adopted' AND cd.is_repost = 0
                    """,
                    (task_id, platform),
                ).fetchone()[0]
                negative = connection.execute(
                    """
                    SELECT COUNT(DISTINCT fc.content_id)
                    FROM finding_contents fc
                    JOIN findings f ON f.id = fc.finding_id
                    JOIN library_contents c ON c.id = fc.content_id
                    WHERE f.research_task_id = ? AND c.platform = ?
                      AND fc.support_type = 'contradictory'
                    """,
                    (task_id, platform),
                ).fetchone()[0]
                connection.execute(
                    """
                    UPDATE research_platform_coverage
                    SET independent_evidence_count = ?, negative_evidence_count = ?, updated_at = ?
                    WHERE research_task_id = ? AND platform = ?
                    """,
                    (int(independent or 0), int(negative or 0), now, task_id, platform),
                )

            # Concentration is measured against unique adopted, non-repost
            # content IDs, not against the sum of entity mentions. One
            # content item may mention several products; using the mention
            # sum would dilute every entity's share.
            entity_rows = connection.execute(
                """
                SELECT canonical_name, entity_new_content_count
                FROM research_entity_coverage
                WHERE research_task_id = ?
                """,
                (task_id,),
            ).fetchall()
            adopted_rows = connection.execute(
                """
                SELECT DISTINCT c.id, c.platform, c.title, c.description
                FROM research_content_decisions cd
                JOIN library_contents c ON c.id = cd.content_id
                WHERE cd.research_task_id = ?
                  AND cd.decision = 'adopted'
                  AND cd.is_repost = 0
                """,
                (task_id,),
            ).fetchall()
            independent_count = len(adopted_rows)
            threshold_row = connection.execute(
                """
                SELECT max_single_entity_evidence_ratio
                FROM research_coverage_plans
                WHERE research_task_id = ?
                """,
                (task_id,),
            ).fetchone()
            threshold = float(threshold_row[0]) if threshold_row is not None else 0.6
            for entity in entity_rows:
                canonical_name = str(entity["canonical_name"])
                normalized_entity = _normalized_text(canonical_name)
                matched = [
                    row
                    for row in adopted_rows
                    if normalized_entity
                    in _normalized_text(f"{row['title'] or ''} {row['description'] or ''}")
                ]
                matched_ids = {str(row["id"]) for row in matched}
                matched_platforms = sorted(
                    {str(row["platform"]) for row in matched if row["platform"]}
                )
                ratio = (
                    len(matched_ids) / independent_count
                    if independent_count
                    else 0.0
                )
                connection.execute(
                    """
                    UPDATE research_entity_coverage
                    SET entity_evidence_count = ?,
                        entity_new_content_count = MIN(entity_new_content_count, ?),
                        entity_platform_count = ?,
                        platforms_json = ?,
                        entity_coverage_ratio = ?,
                        saturated = ?,
                        updated_at = ?
                    WHERE research_task_id = ? AND canonical_name = ?
                    """,
                    (
                        len(matched_ids),
                        len(matched_ids),
                        len(matched_platforms),
                        _dump(matched_platforms),
                        ratio,
                        int(ratio >= threshold and independent_count > 0),
                        utc_now(),
                        task_id,
                        canonical_name,
                    ),
                )

    def finalize_platform_coverage(self, task_id: str) -> None:
        """Close platform rows after the task has no pending crawler work."""
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE research_platform_coverage
                SET status = CASE
                        WHEN failure_reason IS NOT NULL THEN 'failed'
                        WHEN result_count > 0 THEN 'completed'
                        ELSE status
                    END,
                    updated_at = ?
                WHERE research_task_id = ?
                """,
                (utc_now(), task_id),
            )

    def record_finding_entity_coverage(
        self,
        task_id: str,
        content_ids: list[str],
    ) -> None:
        """Attribute an adopted content item only to entities present in it."""
        if not content_ids:
            return
        with connect_database(self.database_path) as connection:
            entities = connection.execute(
                "SELECT canonical_name, entity_type FROM research_entity_coverage WHERE research_task_id = ?",
                (task_id,),
            ).fetchall()
            content_rows = connection.execute(
                f"SELECT id, platform, title, description FROM library_contents WHERE id IN ({','.join('?' for _ in content_ids)})",
                tuple(dict.fromkeys(content_ids)),
            ).fetchall()
            matches: list[tuple[str, str, str | None]] = []
            for content in content_rows:
                text = _normalized_text(f"{content['title'] or ''} {content['description'] or ''}")
                previous_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM finding_contents fc
                    JOIN findings f ON f.id = fc.finding_id
                    WHERE f.research_task_id = ? AND fc.content_id = ?
                    """,
                    (task_id, content["id"]),
                ).fetchone()[0]
                if int(previous_count or 0) != 1:
                    continue
                for entity in entities:
                    normalized_entity = _normalized_text(entity["canonical_name"])
                    if normalized_entity and normalized_entity in text:
                        matches.append((str(entity["canonical_name"]), str(entity["entity_type"]), content["platform"]))
        for canonical_name, entity_type, platform in matches:
            self.upsert_entity_coverage(
                task_id,
                canonical_name,
                entity_type=entity_type,
                evidence_count_delta=1,
                new_content_count_delta=1,
                platform=str(platform) if platform else None,
            )

    def finalize_content_decisions(self, task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT d.id, d.content_id, d.is_repost, d.content_completeness,
                       d.evidence_quality, c.title, c.description
                FROM research_content_decisions d
                JOIN library_contents c ON c.id = d.content_id
                WHERE d.research_task_id = ? AND d.decision IN ('collected', 'candidate')
                """,
                (task_id,),
            ).fetchall()
            for row in rows:
                utility_types = {
                    str(item["utility_type"])
                    for item in connection.execute(
                        """
                        SELECT utility_type FROM content_research_utilities
                        WHERE research_task_id = ? AND content_id = ?
                        """,
                        (task_id, row["content_id"]),
                    ).fetchall()
                }
                if row["is_repost"]:
                    reason = "not_used_duplicate"
                elif row["content_completeness"] in {"missing", "partial"}:
                    reason = "not_used_incomplete"
                elif row["evidence_quality"] == "low":
                    reason = "not_used_low_relevance"
                else:
                    text = f"{row['title'] or ''} {row['description'] or ''}".casefold()
                    if any(term in text for term in ("购买", "优惠", "扫码", "推广")):
                        reason = "not_used_marketing"
                    elif "discovery_seed" in utility_types:
                        reason = "not_used_as_evidence_but_seed"
                    elif "background_context" in utility_types:
                        reason = "not_used_as_evidence_but_background"
                    elif "memory_update" in utility_types:
                        reason = "not_used_as_evidence_but_memory_update"
                    elif "noise" in utility_types:
                        reason = "not_used_no_factual_increment"
                    else:
                        reason = "not_used_no_factual_increment"
                connection.execute(
                    "UPDATE research_content_decisions SET decision = 'not_adopted', not_adopted_reason = ?, updated_at = ? WHERE id = ?",
                    (reason, utc_now(), row["id"]),
                )
        self.refresh_coverage_metrics(task_id)

    def record_budget_event(
        self,
        task_id: str,
        *,
        event_type: str,
        amount: Decimal | str | float | None,
        unit: str,
        provider_instance_id: str | None = None,
        vendor: str | None = None,
        billing_mode: str | None = None,
        currency: str | None = None,
        estimated_cost: Decimal | str | None = None,
        reason: str | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_budget_events (
                    id, research_task_id, event_type, amount, unit,
                    provider_instance_id, vendor, billing_mode, currency,
                    estimated_cost, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.new_id(), task_id, event_type,
                    str(amount) if amount is not None else None, unit,
                    provider_instance_id, vendor, billing_mode, currency,
                    str(estimated_cost) if estimated_cost is not None else None,
                    reason, utc_now(),
                ),
            )

    def save_checkpoint(
        self,
        task_id: str,
        *,
        checkpoint_key: str,
        last_completed_step: str | None,
        payload: dict[str, object],
    ) -> None:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO runtime_checkpoints (
                    research_task_id, checkpoint_key, last_completed_step,
                    payload, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(research_task_id) DO UPDATE SET
                    checkpoint_key = excluded.checkpoint_key,
                    last_completed_step = excluded.last_completed_step,
                    payload = excluded.payload,
                    version = runtime_checkpoints.version + 1,
                    updated_at = excluded.updated_at
                """,
                (task_id, checkpoint_key, last_completed_step, _dump(payload), now, now),
            )
            connection.execute(
                "UPDATE research_tasks SET last_checkpoint_at = ?, updated_at = ? WHERE id = ?",
                (now, now, task_id),
            )

    def load_checkpoint(self, task_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM runtime_checkpoints WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = _json(result.get("payload"), {})
        return result

    def record_evidence_occurrences(
        self,
        *,
        task_id: str,
        content_ids: list[str],
        crawler_task_id: str | None = None,
        query_id: str | None = None,
        finding_id: str | None = None,
        seen_at: str | None = None,
    ) -> int:
        if not content_ids:
            return 0
        seen = seen_at or utc_now()
        inserted_or_updated = 0
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for content_id in dict.fromkeys(content_ids):
                row = connection.execute(
                    """
                    SELECT id, occurrence_count, research_query_id, crawler_task_id,
                           source_query_ids, source_crawler_task_ids
                    FROM evidence_occurrences
                    WHERE research_task_id = ? AND content_id = ?
                      AND (finding_id = ? OR (finding_id IS NULL AND ? IS NULL))
                    LIMIT 1
                    """,
                    (
                        task_id,
                        content_id,
                        finding_id,
                        finding_id,
                    ),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO evidence_occurrences (
                            id, research_task_id, finding_id, content_id,
                            crawler_task_id, research_query_id, first_seen_at,
                            last_seen_at, occurrence_count, source_query_ids,
                            source_crawler_task_ids
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            self.new_id(),
                            task_id,
                            finding_id,
                            content_id,
                            crawler_task_id,
                            query_id,
                            seen,
                            seen,
                            _dump([query_id] if query_id else []),
                            _dump([crawler_task_id] if crawler_task_id else []),
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE evidence_occurrences
                        SET last_seen_at = ?, occurrence_count = occurrence_count + 1,
                            source_query_ids = ?, source_crawler_task_ids = ?
                        WHERE id = ?
                        """,
                        (
                            seen,
                            _dump(list(dict.fromkeys(
                                [str(item) for item in (_json(row["source_query_ids"], []) if isinstance(_json(row["source_query_ids"], []), list) else [])]
                                + ([str(row["research_query_id"])] if row["research_query_id"] else [])
                                + ([query_id] if query_id else [])
                            ))),
                            _dump(list(dict.fromkeys(
                                [str(item) for item in (_json(row["source_crawler_task_ids"], []) if isinstance(_json(row["source_crawler_task_ids"], []), list) else [])]
                                + ([str(row["crawler_task_id"])] if row["crawler_task_id"] else [])
                                + ([crawler_task_id] if crawler_task_id else [])
                            ))),
                            row["id"],
                        ),
                    )
                inserted_or_updated += 1
        return inserted_or_updated

    def claim_next(self) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in RUNNABLE_STATUSES)
            row = connection.execute(
                f"""
                SELECT id FROM research_tasks
                WHERE paused = 0 AND status IN ({placeholders})
                ORDER BY updated_at ASC, created_at ASC, id ASC LIMIT 1
                """,
                tuple(RUNNABLE_STATUSES),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            task = connection.execute(
                self._select_base() + " WHERE t.id = ?",
                (row["id"],),
            ).fetchone()
            connection.commit()
        return _row_to_task(task) if task is not None else None

    def append_trace(
        self,
        task_id: str,
        *,
        event: str,
        status: str | None = None,
        reason: str | None = None,
        round_number: int | None = None,
        step: str | None = None,
        tool_name: str | None = None,
        tool_arguments: dict[str, object] | None = None,
        provider: str | None = None,
        model: str | None = None,
        route_role: str | None = None,
        request_correlation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append_trace_connection(
                connection,
                task_id,
                event=event,
                status=status,
                reason=reason,
                round_number=round_number,
                step=step,
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                provider=provider,
                model=model,
                route_role=route_role,
                request_correlation_id=request_correlation_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                elapsed_ms=elapsed_ms,
            )

    @staticmethod
    def _append_trace_connection(
        connection: sqlite3.Connection,
        task_id: str,
        *,
        event: str,
        status: str | None,
        reason: str | None = None,
        round_number: int | None = None,
        step: str | None = None,
        tool_name: str | None = None,
        tool_arguments: dict[str, object] | None = None,
        provider: str | None = None,
        model: str | None = None,
        route_role: str | None = None,
        request_correlation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        row = connection.execute(
            "SELECT execution_trace FROM research_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise ResearchTaskNotFound(task_id)
        trace = _json(row[0], [])
        if not isinstance(trace, list):
            trace = []
        entry = {
            "sequence": len(trace) + 1,
            "event": event,
            "status": status,
            "reason": reason,
            "round_number": round_number,
            "step": step,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "provider": provider,
            "model": model,
            "route_role": route_role,
            "request_correlation_id": request_correlation_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "elapsed_ms": elapsed_ms,
            "created_at": utc_now(),
        }
        trace.append(entry)
        connection.execute(
            "UPDATE research_tasks SET execution_trace = ?, updated_at = ? WHERE id = ?",
            (_dump(trace), utc_now(), task_id),
        )

    def transition(
        self,
        task_id: str,
        *,
        status: str,
        reason: str,
        step: str | None = None,
        round_number: int | None = None,
        finished: bool = False,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            now = utc_now()
            connection.execute(
                """
                UPDATE research_tasks SET status = ?, current_step = ?,
                    current_round = COALESCE(?, current_round),
                    started_at = CASE WHEN started_at IS NULL AND ? != 'Draft'
                        THEN ? ELSE started_at END,
                    finished_at = CASE WHEN ? THEN ? ELSE finished_at END,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    step,
                    round_number,
                    status,
                    now,
                    int(finished),
                    now,
                    now,
                    task_id,
                ),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="state_transition",
                status=status,
                reason=reason,
                round_number=round_number,
                step=step,
            )

    def set_failure(self, task_id: str, reason: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            if str(row["status"]) in TERMINAL_STATUSES:
                connection.rollback()
                return
            now = utc_now()
            connection.execute(
                "UPDATE research_tasks SET status = 'Failed', failure_reason = ?, finished_at = ?, updated_at = ? WHERE id = ?",
                (reason[:2_000], now, now, task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="failed",
                status="Failed",
                reason=reason[:500],
                step="failed",
            )

    def save_plan(
        self,
        task_id: str,
        *,
        plan: dict[str, object],
        route_snapshot: dict[str, object],
        round_number: int,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            connection.execute(
                "UPDATE research_tasks SET plan = ?, route_snapshot = ?, current_round = ?, updated_at = ? WHERE id = ?",
                (_dump(plan), _dump(route_snapshot), round_number, utc_now(), task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="plan_saved",
                status=str(row["status"]),
                reason="model_plan_persisted",
                round_number=round_number,
                step="plan",
            )

    def set_cost_enabled(self, task_id: str, enabled: bool) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_tasks SET budget_cost_enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), utc_now(), task_id),
            )

    def update_context(
        self,
        task_id: str,
        context: dict[str, object],
        *,
        step: str | None = None,
        round_number: int | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_tasks SET context = ?, current_step = COALESCE(?, current_step), current_round = COALESCE(?, current_round), updated_at = ? WHERE id = ?",
                (_dump(context), step, round_number, utc_now(), task_id),
            )

    def update_result(self, task_id: str, result: dict[str, object]) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_tasks SET result = ?, updated_at = ? WHERE id = ?",
                (_dump(result), utc_now(), task_id),
            )

    def record_usage(
        self,
        task_id: str,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_tokens: int | None,
        estimated_cost: Decimal | str | None,
        provider: str | None,
        model: str | None,
        route_role: str | None,
        request_correlation_id: str | None,
        elapsed_ms: int | None,
        currency: str | None = None,
        price_source: str | None = None,
        provider_instance_id: str | None = None,
        vendor: str | None = None,
        billing_mode: str | None = None,
        fallback_from_provider_instance_id: str | None = None,
        fallback_reason: str | None = None,
        step: str = "unknown",
        invocation_id: str | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT input_tokens, output_tokens, cached_tokens, estimated_cost, consumed_model_call_count FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            existing_cost = Decimal(str(row["estimated_cost"])) if row["estimated_cost"] is not None else None
            added_cost = Decimal(str(estimated_cost)) if estimated_cost is not None else None
            if added_cost is None:
                total_cost = existing_cost
            elif existing_cost is None:
                total_cost = added_cost
            else:
                total_cost = existing_cost + added_cost
            connection.execute(
                """
                UPDATE research_tasks SET input_tokens = input_tokens + ?,
                    output_tokens = output_tokens + ?, cached_tokens = cached_tokens + ?,
                    estimated_cost = ?, consumed_model_call_count = consumed_model_call_count + 1,
                    updated_at = ? WHERE id = ?
                """,
                (
                    input_tokens or 0,
                    output_tokens or 0,
                    cached_tokens or 0,
                    str(total_cost) if total_cost is not None else None,
                    utc_now(),
                    task_id,
                ),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="model_usage",
                status=None,
                reason="gateway_invocation_completed",
                provider=provider,
                model=model,
                route_role=route_role,
                request_correlation_id=request_correlation_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                elapsed_ms=elapsed_ms,
            )
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM research_step_usage WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO research_step_usage (
                    id, research_task_id, step, sequence,
                    provider_instance_id, vendor, model, billing_mode,
                    estimated_cost, currency, price_source,
                    input_tokens, output_tokens, cached_tokens, latency_ms,
                    fallback_from_provider_instance_id, fallback_reason,
                    request_correlation_id, invocation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.new_id(), task_id, step, int(sequence),
                    provider_instance_id, vendor, model, billing_mode,
                    str(estimated_cost) if estimated_cost is not None else None,
                    currency, price_source,
                    input_tokens, output_tokens, cached_tokens, elapsed_ms,
                    fallback_from_provider_instance_id, fallback_reason,
                    request_correlation_id, invocation_id, utc_now(),
                ),
            )
            connection.execute(
                """
                INSERT INTO research_budget_events (
                    id, research_task_id, event_type, amount, unit,
                    provider_instance_id, vendor, billing_mode,
                    currency, estimated_cost, reason, created_at
                ) VALUES (?, ?, 'model_call', ?, 'tokens', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.new_id(), task_id,
                    (input_tokens or 0) + (output_tokens or 0),
                    provider_instance_id, vendor, billing_mode,
                    currency,
                    str(estimated_cost) if estimated_cost is not None else None,
                    step, utc_now(),
                ),
            )

    def record_duration(self, task_id: str) -> int:
        """Persist wall-clock runtime without relying on process memory."""
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT started_at FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            started_at = row["started_at"]
            duration = 0
            if isinstance(started_at, str):
                try:
                    parsed = datetime.fromisoformat(started_at)
                    duration = max(
                        0,
                        int(
                            (
                                datetime.now(UTC)
                                - parsed.astimezone(UTC)
                            ).total_seconds()
                        ),
                    )
                except ValueError:
                    duration = 0
            connection.execute(
                "UPDATE research_tasks SET consumed_duration_seconds = ?, updated_at = ? WHERE id = ?",
                (duration, utc_now(), task_id),
            )
            return duration

    def record_step_usage(
        self,
        task_id: str,
        *,
        step: str,
        latency_ms: int | None = None,
        fallback_from_provider_instance_id: str | None = None,
        fallback_reason: str | None = None,
    ) -> None:
        """Record a deterministic runtime step without fabricating model usage."""
        with connect_database(self.database_path) as connection:
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM research_step_usage WHERE research_task_id = ?",
                (task_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO research_step_usage (
                    id, research_task_id, step, sequence,
                    provider_instance_id, vendor, model, billing_mode,
                    estimated_cost, currency, price_source,
                    input_tokens, output_tokens, cached_tokens, latency_ms,
                    fallback_from_provider_instance_id, fallback_reason,
                    request_correlation_id, invocation_id, created_at
                ) VALUES (
                    ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL,
                    NULL, NULL, NULL, NULL, ?, ?, ?, NULL, NULL, ?
                )
                """,
                (
                    self.new_id(), task_id, step, int(sequence), latency_ms,
                    fallback_from_provider_instance_id, fallback_reason, utc_now(),
                ),
            )

    def add_consumed_content(self, task_id: str, count: int) -> None:
        if count <= 0:
            return
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_tasks SET consumed_content_count = consumed_content_count + ?, updated_at = ? WHERE id = ?",
                (count, utc_now(), task_id),
            )

    def add_crawl_submission(self, task_id: str, crawler_task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, waiting_crawl_task_id FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            if row["waiting_crawl_task_id"] is not None:
                raise ResearchTaskConflict("research task already waits for a crawl")
            connection.execute(
                "UPDATE research_tasks SET status = 'WaitingCrawl', current_step = 'submit_crawl', consumed_crawl_count = consumed_crawl_count + 1, waiting_crawl_task_id = ?, updated_at = ? WHERE id = ?",
                (crawler_task_id, utc_now(), task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="crawl_submitted",
                status="WaitingCrawl",
                reason="async_crawl_submitted",
                step="submit_crawl",
            )

    def mark_waiting_login(self, crawler_task_id: str) -> None:
        self._transition_by_crawler(
            crawler_task_id,
            from_status={"WaitingCrawl"},
            status="WaitingLogin",
            reason="crawler_waiting_for_login",
            step="waiting_login",
        )

    def mark_crawl_resumed(self, crawler_task_id: str) -> None:
        self._transition_by_crawler(
            crawler_task_id,
            from_status={"WaitingLogin"},
            status="WaitingCrawl",
            reason="crawler_login_ready",
            step="waiting_crawl",
        )

    def record_crawl_completion(
        self,
        crawler_task_id: str,
        *,
        succeeded: bool,
        new_content_count: int = 0,
        existing_content_count: int = 0,
        updated_content_count: int = 0,
        duplicate_evidence_count: int = 0,
        result_count: int | None = None,
        error: str | None = None,
    ) -> None:
        occurrence_content_ids: list[str] = []
        query_id: str | None = None
        task_id: str | None = None
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT t.id, t.status, t.context, c.actual_count,
                       c.research_task_id, c.platform, c.started_at, c.finished_at
                FROM research_tasks t
                JOIN crawler_tasks c ON c.id = t.waiting_crawl_task_id
                WHERE t.waiting_crawl_task_id = ?
                """,
                (crawler_task_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return
            task_id = str(row["id"])
            if str(row["status"]) == "Cancelled":
                connection.rollback()
                return
            # A platform-specific crawler failure is a coverage fact, not a
            # terminal research failure. The runtime must continue with the
            # next eligible platform and report the failed branch explicitly.
            status = "Researching"
            now = utc_now()
            context = _json(row["context"], {})
            if not isinstance(context, dict):
                context = {}
            # The completion is now durably observed. Clearing this marker
            # prevents the budget gate from treating the just-finished crawl
            # as another pending request, while allowing the next Researching
            # tick to inspect collected evidence and save findings.
            context["crawl_requested"] = False
            context["last_crawl_platform"] = str(row["platform"])
            if not succeeded:
                context["last_crawl_failure"] = error or "Crawler task failed"
            else:
                context.pop("last_crawl_failure", None)
            connection.execute(
                """
                UPDATE research_tasks SET status = ?, waiting_crawl_task_id = NULL,
                    consumed_content_count = consumed_content_count + ?,
                    context = ?,
                    failure_reason = CASE WHEN ? THEN NULL ELSE ? END,
                    current_step = ?, updated_at = ? WHERE id = ?
                """,
                (
                    status,
                    max(0, new_content_count),
                    _dump(context),
                    int(succeeded),
                    error or "Crawler task failed",
                    "research_round" if succeeded else "platform_failed",
                    now,
                    task_id,
                ),
            )
            query = connection.execute(
                "SELECT id FROM research_queries WHERE crawler_task_id = ?",
                (crawler_task_id,),
            ).fetchone()
            query_id = str(query["id"]) if query is not None else None
            if query_id is not None:
                if result_count is None:
                    result_count = int(row["actual_count"] or 0)
                connection.execute(
                        """
                        UPDATE research_queries
                        SET status = ?, executed_at = ?, result_count = ?,
                            new_content_count = ?, existing_content_count = ?,
                            updated_content_count = ?, duplicate_evidence_count = ?,
                            lifecycle_status = ?,
                            updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        "completed" if succeeded else "failed",
                        now,
                        max(0, result_count or 0),
                        max(0, new_content_count),
                        max(0, existing_content_count),
                        max(0, updated_content_count),
                        max(0, duplicate_evidence_count),
                        "completed" if succeeded else "failed",
                        now,
                        query_id,
                    ),
                )
                new_rate = max(0, new_content_count) / max(1, result_count or 0)
                duplicate_rate = max(0, duplicate_evidence_count) / max(1, result_count or 0)
                marginal_value = max(
                    0.0,
                    min(1.0, new_rate * 0.65 + (1.0 - duplicate_rate) * 0.35),
                )
                threshold_row = connection.execute(
                    "SELECT low_marginal_value_threshold, low_marginal_round_limit FROM research_coverage_plans WHERE research_task_id = ?",
                    (task_id,),
                ).fetchone()
                threshold = float(threshold_row[0]) if threshold_row is not None else 0.1
                previous_low_rounds = int(context.get("low_marginal_rounds") or 0)
                new_entity_count = int(context.get("last_new_entity_count") or 0)
                negative_found = bool(context.get("last_negative_evidence_found"))
                low_rounds = previous_low_rounds + 1 if marginal_value < threshold and new_entity_count == 0 and not negative_found else 0
                context["last_new_content_rate"] = new_rate
                context["last_duplicate_rate"] = duplicate_rate
                context["last_marginal_value_score"] = marginal_value
                context["low_marginal_rounds"] = low_rounds
                connection.execute(
                    "UPDATE research_tasks SET context = ?, updated_at = ? WHERE id = ?",
                    (_dump(context), now, task_id),
                )
                connection.execute(
                    """
                    INSERT INTO research_query_metrics (
                        id, research_query_id, new_content_rate,
                        new_entity_count, new_independent_evidence_count,
                        duplicate_rate, crawl_duration_ms,
                        collected_result_count, candidate_evidence_count,
                        adopted_evidence_count, not_adopted_count,
                        marginal_value_score, measured_at
                    ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 0, ?, ?)
                    ON CONFLICT(research_query_id) DO UPDATE SET
                        new_content_rate = excluded.new_content_rate,
                        new_entity_count = excluded.new_entity_count,
                        new_independent_evidence_count = excluded.new_independent_evidence_count,
                        duplicate_rate = excluded.duplicate_rate,
                        crawl_duration_ms = excluded.crawl_duration_ms,
                        collected_result_count = excluded.collected_result_count,
                        candidate_evidence_count = excluded.candidate_evidence_count,
                        marginal_value_score = excluded.marginal_value_score,
                        measured_at = excluded.measured_at
                    """,
                    (
                        self.new_id(),
                        query_id,
                        new_rate,
                        new_entity_count,
                        duplicate_rate,
                        _duration_millis(row["started_at"], row["finished_at"]),
                        max(0, result_count or 0),
                        max(0, result_count or 0),
                        marginal_value,
                        now,
                    ),
                )
            connection.execute(
                """
                UPDATE research_platform_coverage
                SET status = ?, actual_query_count = actual_query_count + 1,
                    result_count = result_count + ?, new_content_count = new_content_count + ?,
                    failure_reason = ?, updated_at = ?
                WHERE research_task_id = ? AND platform = ?
                """,
                (
                    "completed" if succeeded else "failed",
                    max(0, result_count if result_count is not None else int(row["actual_count"] or 0)),
                    max(0, new_content_count),
                    None if succeeded else (error or "Crawler task failed"),
                    now,
                    task_id,
                    str(row["platform"]),
                ),
            )
            if succeeded and task_id is not None:
                occurrence_content_ids = [
                    str(item["entity_id"])
                    for item in connection.execute(
                        """
                        SELECT entity_id FROM crawl_task_entities
                        WHERE task_id = ? AND entity_type = 'content'
                        """,
                        (crawler_task_id,),
                    ).fetchall()
                ]
                context["last_crawl_content_ids"] = list(
                    dict.fromkeys(occurrence_content_ids)
                )[:20]
                connection.execute(
                    "UPDATE research_tasks SET context = ?, updated_at = ? WHERE id = ?",
                    (_dump(context), now, task_id),
                )
                if duplicate_evidence_count == 0:
                    duplicate_evidence_count = sum(
                        1
                        for content_id in set(occurrence_content_ids)
                        if connection.execute(
                            """
                            SELECT 1 FROM evidence_occurrences
                            WHERE content_id = ?
                            UNION ALL
                            SELECT 1
                            FROM crawl_task_entities e
                            JOIN crawler_tasks c ON c.id = e.task_id
                            WHERE e.entity_type = 'content'
                              AND e.entity_id = ?
                              AND c.research_task_id IS NOT NULL
                              AND c.research_task_id != ?
                            LIMIT 1
                            """,
                            (content_id, content_id, task_id),
                        ).fetchone()
                        is not None
                    ) + max(0, len(occurrence_content_ids) - len(set(occurrence_content_ids)))
                if query_id is not None:
                    connection.execute(
                        "UPDATE research_queries SET duplicate_evidence_count = ?, updated_at = ? WHERE id = ?",
                        (duplicate_evidence_count, now, query_id),
                    )
            self._append_trace_connection(
                connection,
                task_id,
                event="crawl_completed" if succeeded else "crawl_failed",
                status=status,
                reason=error if not succeeded else "crawler_ingestion_committed",
                step="research_round" if succeeded else "crawl_failed",
            )
        if succeeded and task_id is not None:
            self.record_evidence_occurrences(
                task_id=task_id,
                content_ids=occurrence_content_ids,
                crawler_task_id=crawler_task_id,
                query_id=query_id,
            )
            for content_id in occurrence_content_ids:
                self.record_content_decision(
                    task_id=task_id,
                    content_id=content_id,
                    query_id=query_id,
                    decision="candidate",
                )

    def quality_summary(self, task_id: str) -> dict[str, int]:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(new_content_count), 0) AS new_content_count,
                       COALESCE(SUM(existing_content_count), 0) AS existing_content_count,
                       COALESCE(SUM(updated_content_count), 0) AS updated_content_count,
                       COALESCE(SUM(duplicate_evidence_count), 0) AS duplicate_evidence_count,
                       COALESCE(SUM(result_count), 0) AS result_count
                FROM research_queries WHERE research_task_id = ?
                """,
                (task_id,),
            ).fetchone()
            independent = connection.execute(
                """
                SELECT COUNT(DISTINCT fc.content_id)
                FROM finding_contents fc
                JOIN findings f ON f.id = fc.finding_id
                LEFT JOIN research_content_decisions cd
                  ON cd.research_task_id = f.research_task_id
                 AND cd.content_id = fc.content_id
                WHERE f.research_task_id = ?
                  AND COALESCE(cd.source_independence, 'unknown') != 'repost'
                """,
                (task_id,),
            ).fetchone()[0]
            discovery_count = connection.execute(
                """
                SELECT COALESCE(SUM(occurrence_count), 0)
                FROM evidence_occurrences
                WHERE research_task_id = ? AND finding_id IS NULL
                """,
                (task_id,),
            ).fetchone()[0]
            repost_count = connection.execute(
                """
                SELECT COUNT(*) FROM research_content_decisions
                WHERE research_task_id = ? AND is_repost = 1
                """,
                (task_id,),
            ).fetchone()[0]
            negative_count = connection.execute(
                """
                SELECT COUNT(*) FROM finding_contents fc
                JOIN findings f ON f.id = fc.finding_id
                WHERE f.research_task_id = ? AND fc.support_type = 'contradictory'
                """,
                (task_id,),
            ).fetchone()[0]
        summary = dict(row) if row is not None else {}
        summary["independent_evidence_count"] = int(independent or 0)
        summary["discovery_count"] = int(discovery_count or 0)
        summary["repost_count"] = int(repost_count or 0)
        summary["negative_evidence_count"] = int(negative_count or 0)
        return {key: int(value or 0) for key, value in summary.items()}

    def coverage_summary(self, task_id: str) -> dict[str, object]:
        detail = self.get_for_runtime(task_id, detail=True)
        if detail is None:
            raise ResearchTaskNotFound(task_id)
        coverage = detail.get("coverage")
        coverage = coverage if isinstance(coverage, dict) else {}
        platforms = detail.get("platform_coverage")
        platforms = platforms if isinstance(platforms, list) else []
        entities = detail.get("entity_coverage")
        entities = entities if isinstance(entities, list) else []
        quality = self.quality_summary(task_id)
        active_platforms = sum(
            1
            for item in platforms
            if isinstance(item, dict)
            and item.get("status") == "completed"
            and int(item.get("result_count") or 0) > 0
        )
        independent = int(quality.get("independent_evidence_count", 0))
        target_platforms = int(coverage.get("target_platform_count", 0))
        target_entities = int(coverage.get("target_entity_count", 0))
        target_negative = int(coverage.get("target_negative_evidence_count", 0))
        target_independent = int(coverage.get("target_independent_evidence_count", 0))
        target_new = int(coverage.get("target_new_content_count", 0))
        reached = {
            "platforms": active_platforms >= target_platforms,
            "entities": len(entities) >= target_entities,
            "negative_evidence": int(quality.get("negative_evidence_count", 0)) >= target_negative,
            "independent_evidence": independent >= target_independent,
            "new_content": int(quality.get("new_content_count", 0)) >= target_new,
            "entity_concentration": all(
                float(item.get("entity_coverage_ratio") or 0)
                <= float(coverage.get("max_single_entity_evidence_ratio", 0.6))
                for item in entities
            ),
        }
        return {
            "target_platform_count": target_platforms,
            "actual_platform_count": active_platforms,
            "target_entity_count": target_entities,
            "actual_entity_count": len(entities),
            "target_negative_evidence_count": target_negative,
            "actual_negative_evidence_count": int(quality.get("negative_evidence_count", 0)),
            "target_independent_evidence_count": target_independent,
            "actual_independent_evidence_count": independent,
            "target_new_content_count": target_new,
            "actual_new_content_count": int(quality.get("new_content_count", 0)),
            "max_single_entity_evidence_ratio": float(
                coverage.get("max_single_entity_evidence_ratio", 0.6)
            ),
            "reached": reached,
            "all_targets_reached": all(reached.values()),
        }

    def set_stop_reason(self, task_id: str, reason: str) -> None:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE research_tasks SET stop_reason = ?, updated_at = ? WHERE id = ?",
                (reason, now, task_id),
            )
            connection.execute(
                "UPDATE research_coverage_plans SET stop_reason = ?, updated_at = ? WHERE research_task_id = ?",
                (reason, now, task_id),
            )

    def _transition_by_crawler(
        self,
        crawler_task_id: str,
        *,
        from_status: set[str],
        status: str,
        reason: str,
        step: str,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, status FROM research_tasks WHERE waiting_crawl_task_id = ?",
                (crawler_task_id,),
            ).fetchone()
            if row is None or row["status"] not in from_status:
                connection.rollback()
                return
            connection.execute(
                "UPDATE research_tasks SET status = ?, current_step = ?, updated_at = ? WHERE id = ?",
                (status, step, utc_now(), row["id"]),
            )
            self._append_trace_connection(
                connection,
                str(row["id"]),
                event="state_transition",
                status=status,
                reason=reason,
                step=step,
            )

    def save_finding(
        self,
        *,
        task_id: str,
        round_number: int,
        kind: str,
        statement: str,
        derivation: str | None,
        content_ids: list[str],
        evidence_links: list[dict[str, str]] | None = None,
        counterevidence_status: str = "not_found",
        counterevidence_explanation: str = "未找到反证。",
    ) -> dict[str, object]:
        if kind == "fact" and not content_ids:
            raise ResearchTaskConflict("fact findings require content evidence")
        if not content_ids:
            raise ResearchTaskConflict("findings require content evidence")
        if kind == "inference" and not derivation:
            raise ResearchTaskConflict("inference findings require a derivation")
        if counterevidence_status not in {"found", "not_found", "unknown"}:
            raise ResearchTaskConflict("counterevidence status is invalid")
        if kind == "inference" and counterevidence_status == "unknown":
            raise ResearchTaskConflict(
                "inference findings require a counterevidence status"
            )
        if not counterevidence_explanation.strip():
            raise ResearchTaskConflict("counterevidence explanation is required")
        normalized_links = evidence_links or [
            {
                "content_id": content_id,
                "support_type": "direct",
                "support_strength": "medium",
                "support_explanation": "Evidence was supplied by the legacy finding API.",
            }
            for content_id in content_ids
        ]
        linked_ids = [str(item.get("content_id") or "") for item in normalized_links]
        if set(linked_ids) != set(content_ids) or len(linked_ids) != len(set(linked_ids)):
            raise ResearchTaskConflict("finding evidence metadata must cover each content once")
        allowed_support_types = {"direct", "contextual", "contradictory", "background"}
        allowed_support_strengths = {"strong", "medium", "weak"}
        if any(
            item.get("support_type") not in allowed_support_types
            or item.get("support_strength") not in allowed_support_strengths
            or not str(item.get("support_explanation") or "").strip()
            for item in normalized_links
        ):
            raise ResearchTaskConflict("finding evidence support metadata is invalid")
        if kind == "fact" and not any(
            item.get("support_type") == "direct" for item in normalized_links
        ):
            raise ResearchTaskConflict("fact findings require direct evidence")
        if kind == "inference" and counterevidence_status == "found" and not any(
            item.get("support_type") == "contradictory" for item in normalized_links
        ):
            raise ResearchTaskConflict(
                "found counterevidence requires a contradictory evidence link"
            )
        identifier = self.new_id()
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT 1 FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                raise ResearchTaskNotFound(task_id)
            placeholders = ",".join("?" for _ in content_ids)
            rows = connection.execute(
                f"SELECT id FROM library_contents WHERE id IN ({placeholders})",
                tuple(content_ids),
            ).fetchall()
            found = {str(row["id"]) for row in rows}
            if found != set(content_ids):
                raise ResearchTaskConflict("finding evidence contains unknown content")
            connection.execute(
                """
                INSERT INTO findings (
                    id, research_task_id, round_number, kind, statement,
                    derivation, counterevidence_status,
                    counterevidence_explanation, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    identifier,
                    task_id,
                    round_number,
                    kind,
                    statement,
                    derivation,
                    counterevidence_status,
                    counterevidence_explanation,
                    now,
                    now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO finding_contents (
                    finding_id, content_id, evidence_role, support_type,
                    support_strength, support_explanation
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        identifier,
                        str(item["content_id"]),
                        "derived_from" if kind == "inference" else "supports",
                        str(item["support_type"]),
                        str(item["support_strength"]),
                        str(item["support_explanation"]),
                    )
                    for item in normalized_links
                ],
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="finding_saved",
                status=None,
                reason="evidence_bound_finding",
                round_number=round_number,
                step="save_finding",
            )
        self.record_evidence_occurrences(
            task_id=task_id,
            content_ids=content_ids,
            finding_id=identifier,
            seen_at=now,
        )
        for content_id in content_ids:
            decision = self.record_content_decision(
                task_id=task_id,
                content_id=content_id,
                decision="adopted",
            )
            with connect_database(self.database_path) as connection:
                connection.execute(
                    """
                    UPDATE finding_contents
                    SET source_independence = ?, content_completeness = ?,
                        evidence_quality = ?
                    WHERE finding_id = ? AND content_id = ?
                    """,
                    (
                        decision["source_independence"],
                        decision["content_completeness"],
                        decision["evidence_quality"],
                        identifier,
                        content_id,
                    ),
                )
        self.record_finding_entity_coverage(task_id, content_ids)
        self.refresh_coverage_metrics(task_id)
        return {
            "id": identifier,
            "kind": kind,
            "statement": statement,
            "content_ids": content_ids,
            "counterevidence_status": counterevidence_status,
        }

    def dedupe_event(
        self,
        *,
        task_id: str,
        round_number: int,
        fingerprint: str,
        title: str,
        summary: str,
        content_ids: list[str],
    ) -> dict[str, object]:
        identifier = self.new_id()
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id FROM events WHERE research_task_id = ? AND fingerprint = ?",
                (task_id, fingerprint),
            ).fetchone()
            if existing is not None:
                identifier = str(existing["id"])
                connection.execute(
                    "UPDATE events SET title = ?, summary = ?, updated_at = ? WHERE id = ?",
                    (title, summary, now, identifier),
                )
            else:
                connection.execute(
                    "INSERT INTO events (id, research_task_id, round_number, fingerprint, title, summary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier, task_id, round_number, fingerprint, title, summary, now, now),
                )
            for content_id in content_ids:
                connection.execute(
                    "INSERT OR IGNORE INTO event_contents (event_id, content_id, evidence_role) VALUES (?, ?, 'member')",
                    (identifier, content_id),
                )
            self._append_trace_connection(
                connection,
                task_id,
                event="event_deduped",
                status=None,
                reason="fingerprint_and_cluster_saved",
                round_number=round_number,
                step="dedupe_check",
            )
        return {"id": identifier, "fingerprint": fingerprint, "content_ids": content_ids}

    def add_action(
        self,
        *,
        task_id: str,
        action: str,
        reason: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        identifier = self.new_id()
        item = {
            "id": identifier,
            "action": action,
            "reason": reason,
            "payload": payload,
            "status": "pending",
            "created_at": utc_now(),
            "decided_at": None,
        }
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT proposed_actions FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            actions = _json(row[0], [])
            if not isinstance(actions, list):
                actions = []
            actions.append(item)
            connection.execute(
                "UPDATE research_tasks SET proposed_actions = ?, updated_at = ? WHERE id = ?",
                (_dump(actions), utc_now(), task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="action_proposed",
                status=None,
                reason="owner_approval_required",
                step="propose_action",
            )
        return item

    def decide_action(self, task_id: str, action_id: str, status: str) -> dict[str, object]:
        if status not in {"approved", "rejected"}:
            raise ValueError("unsupported action decision")
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT proposed_actions FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            actions = _json(row[0], [])
            if not isinstance(actions, list):
                actions = []
            selected = None
            for item in actions:
                if isinstance(item, dict) and item.get("id") == action_id:
                    item["status"] = status
                    item["decided_at"] = utc_now()
                    selected = item
                    break
            if selected is None:
                raise ResearchTaskNotFound(action_id)
            connection.execute(
                "UPDATE research_tasks SET proposed_actions = ?, updated_at = ? WHERE id = ?",
                (_dump(actions), utc_now(), task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="action_decided",
                status=None,
                reason=f"owner_{status}",
                step="action_review",
            )
        return selected

    def control(self, task_id: str, action: str, reason: str | None = None) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, paused, waiting_crawl_task_id, context FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            current = str(row["status"])
            now = utc_now()
            rerun_context: dict[str, object] | None = None
            if action == "pause":
                if current in TERMINAL_STATUSES:
                    raise ResearchTaskConflict("terminal research task cannot be paused")
                connection.execute(
                    "UPDATE research_tasks SET paused = 1, updated_at = ? WHERE id = ?",
                    (now, task_id),
                )
                trace_status = current
            elif action == "resume":
                if current in TERMINAL_STATUSES:
                    raise ResearchTaskConflict("terminal research task cannot be resumed")
                connection.execute(
                    "UPDATE research_tasks SET paused = 0, updated_at = ? WHERE id = ?",
                    (now, task_id),
                )
                trace_status = current
            elif action == "cancel":
                if current in TERMINAL_STATUSES:
                    raise ResearchTaskConflict("terminal research task cannot be cancelled")
                connection.execute(
                    "UPDATE research_tasks SET status = 'Cancelled', paused = 0, finished_at = ?, failure_reason = ?, updated_at = ? WHERE id = ?",
                    (now, reason, now, task_id),
                )
                trace_status = "Cancelled"
            elif action == "rerun":
                if current != "AwaitingReview":
                    raise ResearchTaskConflict("only an awaiting-review task can rerun")
                staged_retry = self._stage_failed_crawler_query_for_rerun(
                    connection,
                    task_id,
                )
                if staged_retry is not None:
                    rerun_context = _json(row["context"], {})
                    rerun_context["retry_query_id"] = staged_retry["id"]
                    rerun_context["retry_platform"] = staged_retry["platform"]
                connection.execute(
                    """
                    UPDATE research_tasks
                    SET status = 'Researching', paused = 0,
                        current_round = current_round + 1,
                        current_step = 'research_round', result = NULL,
                        finished_at = NULL, failure_reason = ?,
                        context = COALESCE(?, context), updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        None,
                        _dump(rerun_context) if rerun_context is not None else None,
                        now,
                        task_id,
                    ),
                )
                trace_status = "Researching"
            else:
                raise ValueError("unsupported research task control")
            self._append_trace_connection(
                connection,
                task_id,
                event=f"control_{action}",
                status=trace_status,
                reason=reason or f"owner_{action}",
                step="control",
            )
        task = self.get_for_runtime(task_id)
        if task is None:
            raise ResearchTaskNotFound(task_id)
        return task

    def _stage_failed_crawler_query_for_rerun(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> dict[str, object] | None:
        """Clone one failed crawler query so an owner rerun can retry it.

        A login timeout is an operational failure, not evidence that the
        execution query is a duplicate.  Keep the failed row immutable for
        audit purposes and stage a new held row for the runtime to claim.  A
        login-related failure wins over a later generic platform failure so a
        rerun can expose a fresh QR when that is the missing user action.
        """
        row = connection.execute(
            """
            SELECT q.*, c.id AS failed_crawler_task_id, c.error_message AS crawler_error,
                   c.finished_at AS crawler_finished_at
            FROM research_queries q
            JOIN crawler_tasks c ON c.id = q.crawler_task_id
            WHERE q.research_task_id = ?
              AND q.record_type = 'execution_query'
              AND q.status = 'failed'
              AND c.status = 'failed'
            ORDER BY CASE
                WHEN lower(COALESCE(c.error_message, '')) LIKE '%login%'
                  OR lower(COALESCE(c.error_message, '')) LIKE '%登录%'
                  OR lower(COALESCE(c.error_message, '')) LIKE '%captcha%'
                  OR lower(COALESCE(c.error_message, '')) LIKE '%二维码%'
                THEN 0 ELSE 1 END,
                COALESCE(c.finished_at, q.updated_at) DESC,
                q.created_at DESC,
                q.id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None

        identifier = self.new_id()
        now = utc_now()
        generation_reason = (
            "所有者重跑：保留失败查询审计并重试失败的 "
            f"{row['platform']} crawler"
        )
        unexecuted_reason = "owner_rerun_after_crawler_failure"
        connection.execute(
            """
            INSERT INTO research_queries (
                id, research_task_id, intent_id, record_type, gate_status,
                decision, query_role, query, normalized_query, query_type,
                platform, source_type, source_content_id, source_finding_id,
                parent_query_id, generation_reason, relevance_score,
                specificity_score, novelty_score, noise_risk_score,
                expected_value_score, status, rejection_reason, crawler_task_id,
                executed_at, result_count, new_content_count,
                existing_content_count, updated_content_count,
                duplicate_evidence_count, created_at, updated_at,
                lifecycle_status, unexecuted_reason, entity_diversity_bonus,
                platform_diversity_bonus, negative_evidence_bonus,
                estimated_resource_use, expected_evidence_role
            ) VALUES (
                ?, ?, ?, 'execution_query', 'hold', 'hold', ?, ?, ?, ?,
                ?, 'owner_rerun', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', NULL,
                NULL, NULL, 0, 0, 0, 0, 0, ?, ?,
                'skipped_low_marginal_value', ?, ?, ?, ?, ?, ?
            )
            """,
            (
                identifier,
                row["research_task_id"],
                row["intent_id"],
                row["query_role"],
                row["query"],
                row["normalized_query"],
                row["query_type"],
                row["platform"],
                row["source_content_id"],
                row["source_finding_id"],
                row["id"],
                generation_reason,
                row["relevance_score"],
                row["specificity_score"],
                row["novelty_score"],
                row["noise_risk_score"],
                row["expected_value_score"],
                now,
                now,
                unexecuted_reason,
                row["entity_diversity_bonus"],
                row["platform_diversity_bonus"],
                row["negative_evidence_bonus"],
                row["estimated_resource_use"],
                row["expected_evidence_role"],
            ),
        )
        self._append_trace_connection(
            connection,
            task_id,
            event="query_retry_staged",
            status=None,
            reason=unexecuted_reason,
            step="control",
            tool_arguments={
                "failed_query_id": row["id"],
                "retry_query_id": identifier,
                "failed_crawler_task_id": row["failed_crawler_task_id"],
                "platform": row["platform"],
                "crawler_error": row["crawler_error"],
            },
        )
        return {"id": identifier, "platform": str(row["platform"])}

    def complete_review(self, task_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            if str(row["status"]) != "AwaitingReview":
                raise ResearchTaskConflict("only an awaiting-review task can be completed")
            now = utc_now()
            connection.execute(
                "UPDATE research_tasks SET status = 'Done', finished_at = ?, updated_at = ? WHERE id = ?",
                (now, now, task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="review_completed",
                status="Done",
                reason="owner_confirmed_result",
                step="done",
            )

    def reconcile_waiting_crawl(self) -> list[str]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT t.id AS research_id, t.waiting_crawl_task_id AS crawler_id,
                       c.status, c.error_message, c.actual_count
                FROM research_tasks t
                JOIN crawler_tasks c ON c.id = t.waiting_crawl_task_id
                WHERE t.status IN ('WaitingCrawl', 'WaitingLogin')
                """
            ).fetchall()
        return [str(row["research_id"]) for row in rows]

    def waiting_crawls(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT t.id AS research_id, t.waiting_crawl_task_id AS crawler_id,
                       c.status AS crawler_status, c.error_message,
                       c.actual_count, c.research_new_content_count,
                       c.research_existing_content_count,
                       c.research_updated_content_count
                FROM research_tasks t
                JOIN crawler_tasks c ON c.id = t.waiting_crawl_task_id
                WHERE t.status IN ('WaitingCrawl', 'WaitingLogin')
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def reconcile_orphan_crawls(self) -> list[str]:
        """Attach a crawler created just before an API process interruption."""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT c.id AS crawler_id, t.id AS research_id
                FROM crawler_tasks c
                JOIN research_tasks t ON t.id = c.research_task_id
                WHERE t.status = 'Researching'
                  AND t.waiting_crawl_task_id IS NULL
                  -- A completed crawler has already been reconciled by the
                  -- Worker.  Re-attaching it here would consume the same
                  -- crawl budget repeatedly on every runtime tick.  A
                  -- process can only leave an orphan in an active state
                  -- between crawler creation and the durable association.
                  AND c.status IN ('pending', 'running', 'waiting_login')
                ORDER BY c.created_at, c.id
                """
            ).fetchall()
        attached: list[str] = []
        for row in rows:
            try:
                self.add_crawl_submission(str(row["research_id"]), str(row["crawler_id"]))
            except ResearchTaskConflict:
                continue
            attached.append(str(row["crawler_id"]))
        return attached

    def _findings_connection(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[dict[str, object]]:
        rows = connection.execute(
            "SELECT * FROM findings WHERE research_task_id = ? ORDER BY created_at, id",
            (task_id,),
        ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            evidence_rows = connection.execute(
                """
                SELECT c.id AS content_id, c.platform, c.title, c.source_url,
                       c.author_name, c.published_at,
                       fc.support_type, fc.support_strength,
                       fc.support_explanation, fc.source_independence,
                       fc.content_completeness, fc.evidence_quality,
                       COALESCE(cd.is_repost, 0) AS is_repost,
                       (SELECT e.collected_at FROM crawl_task_entities e
                        WHERE e.entity_id = c.id AND e.entity_type = 'content'
                        ORDER BY e.collected_at DESC, e.task_id DESC LIMIT 1)
                         AS collected_at,
                       (SELECT e.task_id FROM crawl_task_entities e
                        WHERE e.entity_id = c.id AND e.entity_type = 'content'
                        ORDER BY e.collected_at DESC, e.task_id DESC LIMIT 1)
                         AS crawl_task_id
                FROM finding_contents fc
                JOIN library_contents c ON c.id = fc.content_id
                LEFT JOIN research_content_decisions cd
                  ON cd.research_task_id = ? AND cd.content_id = fc.content_id
                WHERE fc.finding_id = ?
                ORDER BY c.id
                """,
                (task_id, row["id"]),
            ).fetchall()
            evidence: list[dict[str, object]] = []
            for evidence_row in evidence_rows:
                evidence_item = dict(evidence_row)
                evidence_item["is_repost"] = bool(evidence_item.get("is_repost"))
                occurrences: list[dict[str, object]] = []
                for occurrence in connection.execute(
                        """
                        SELECT id, research_task_id, finding_id, content_id,
                               crawler_task_id, research_query_id,
                               first_seen_at, last_seen_at, occurrence_count,
                               source_query_ids, source_crawler_task_ids
                        FROM evidence_occurrences
                        WHERE research_task_id = ? AND content_id = ?
                        ORDER BY first_seen_at, id
                        """,
                        (task_id, evidence_item["content_id"]),
                    ).fetchall():
                    occurrence_item = dict(occurrence)
                    occurrence_item["source_query_ids"] = _json(
                        occurrence_item.get("source_query_ids"), []
                    )
                    occurrence_item["source_crawler_task_ids"] = _json(
                        occurrence_item.get("source_crawler_task_ids"), []
                    )
                    occurrences.append(occurrence_item)
                evidence_item["occurrences"] = occurrences
                evidence.append(evidence_item)
            item["evidence"] = evidence
            result.append(item)
        return result

    def _queries_connection(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[dict[str, object]]:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT q.*, m.new_content_rate, m.new_entity_count,
                       m.new_independent_evidence_count, m.duplicate_rate,
                       m.marginal_value_score
                FROM research_queries q
                LEFT JOIN research_query_metrics m ON m.research_query_id = q.id
                WHERE q.research_task_id = ?
                ORDER BY q.created_at, q.id
                """,
                (task_id,),
            ).fetchall()
        ]

    def _events_connection(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[dict[str, object]]:
        rows = connection.execute(
            "SELECT * FROM events WHERE research_task_id = ? ORDER BY created_at, id",
            (task_id,),
        ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            content_rows = connection.execute(
                "SELECT content_id FROM event_contents WHERE event_id = ? ORDER BY content_id",
                (row["id"],),
            ).fetchall()
            item["content_ids"] = [str(content["content_id"]) for content in content_rows]
            result.append(item)
        return result
