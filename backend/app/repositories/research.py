from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
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


def _decimal(value: object) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


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
    ) -> dict[str, object]:
        identifier = self.new_id()
        now = utc_now()
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
                    started_at, updated_at, finished_at
                ) VALUES (?, ?, 'research', ?, ?, 'Draft', '{}', '{}', NULL,
                    '[]', '[]', '{}', ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0,
                    0, NULL, 0, NULL, NULL, 0, NULL, ?, NULL, ?, NULL)
                """,
                (
                    identifier,
                    user_id,
                    objective,
                    _dump(platforms),
                    crawl_limit,
                    content_limit,
                    duration_seconds,
                    token_limit,
                    cost_limit,
                    cost_currency,
                    budget_cost_enabled,
                    now,
                    now,
                ),
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
            task["events"] = self._events_connection(connection, task_id)
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
                task["events"] = self._events_connection(connection, task_id)
        return task

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
            connection.execute(
                "UPDATE research_tasks SET plan = ?, route_snapshot = ?, current_round = ?, updated_at = ? WHERE id = ?",
                (_dump(plan), _dump(route_snapshot), round_number, utc_now(), task_id),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="plan_saved",
                status="Planning",
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
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT input_tokens, output_tokens, cached_tokens, estimated_cost FROM research_tasks WHERE id = ?",
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
                    estimated_cost = ?, updated_at = ? WHERE id = ?
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
        error: str | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, status FROM research_tasks WHERE waiting_crawl_task_id = ?",
                (crawler_task_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return
            task_id = str(row["id"])
            if str(row["status"]) == "Cancelled":
                connection.rollback()
                return
            status = "Researching" if succeeded else "Failed"
            now = utc_now()
            connection.execute(
                """
                UPDATE research_tasks SET status = ?, waiting_crawl_task_id = NULL,
                    consumed_content_count = consumed_content_count + ?,
                    failure_reason = ?, finished_at = CASE WHEN ? THEN finished_at ELSE ? END,
                    current_step = ?, updated_at = ? WHERE id = ?
                """,
                (
                    status,
                    max(0, new_content_count),
                    None if succeeded else (error or "Crawler task failed"),
                    int(succeeded),
                    now,
                    "research_round" if succeeded else "crawl_failed",
                    now,
                    task_id,
                ),
            )
            self._append_trace_connection(
                connection,
                task_id,
                event="crawl_completed" if succeeded else "crawl_failed",
                status=status,
                reason=error if not succeeded else "crawler_ingestion_committed",
                step="research_round" if succeeded else "crawl_failed",
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
    ) -> dict[str, object]:
        if kind == "fact" and not content_ids:
            raise ResearchTaskConflict("fact findings require content evidence")
        if not content_ids:
            raise ResearchTaskConflict("findings require content evidence")
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
                "INSERT INTO findings (id, research_task_id, round_number, kind, statement, derivation, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (identifier, task_id, round_number, kind, statement, derivation, now, now),
            )
            connection.executemany(
                "INSERT INTO finding_contents (finding_id, content_id, evidence_role) VALUES (?, ?, ?)",
                [(identifier, content_id, "derived_from" if kind == "inference" else "supports") for content_id in content_ids],
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
        return {"id": identifier, "kind": kind, "statement": statement, "content_ids": content_ids}

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
                "SELECT status, paused, waiting_crawl_task_id FROM research_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ResearchTaskNotFound(task_id)
            current = str(row["status"])
            now = utc_now()
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
                connection.execute(
                    "UPDATE research_tasks SET status = 'Researching', paused = 0, current_round = current_round + 1, current_step = 'research_round', result = NULL, finished_at = NULL, failure_reason = NULL, updated_at = ? WHERE id = ?",
                    (now, task_id),
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
                       c.actual_count
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
                WHERE fc.finding_id = ?
                ORDER BY c.id
                """,
                (row["id"],),
            ).fetchall()
            item["evidence"] = [dict(evidence) for evidence in evidence_rows]
            result.append(item)
        return result

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
