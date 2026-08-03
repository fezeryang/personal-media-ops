from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from pathlib import Path

from app.db import connect_database
from app.repositories.research import utc_now


class DiscoveryNotFound(KeyError):
    pass


class DiscoveryConflict(RuntimeError):
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


def _clamp(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _bool(value: object) -> bool:
    return bool(int(value or 0))


class DiscoveryRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _candidate_from_row(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["score_explanation"] = _json(item.pop("score_explanation_json", "{}"), {})
        item.pop("owner_id", None)
        item.pop("run_id", None)
        return item

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["is_repost"] = _bool(item.get("is_repost"))
        return item

    @staticmethod
    def _score_from_row(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["components"] = _json(item.pop("components_json", "{}"), {})
        item["explanation"] = _json(item.pop("explanation_json", "{}"), {})
        return item

    def create_run(self, *, task_id: str, depth: int = 1) -> dict[str, object]:
        if depth not in (0, 1):
            raise DiscoveryConflict("discovery depth must be 0 or 1")
        now = utc_now()
        identifier = self.new_id()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_discovery_runs (
                    id, research_task_id, depth, started_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (identifier, task_id, depth, now, now),
            )
            row = connection.execute(
                "SELECT * FROM research_discovery_runs WHERE id = ?",
                (identifier,),
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(identifier)
        return dict(row)

    def latest_completed_run(self, task_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM research_discovery_runs
                WHERE research_task_id = ? AND status IN ('completed', 'partial')
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (task_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        seed_count: int,
        candidate_count: int,
        platform_count: int,
        stop_reason: str | None = None,
    ) -> dict[str, object]:
        if status not in {"completed", "partial", "failed"}:
            raise DiscoveryConflict("invalid discovery run status")
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE research_discovery_runs
                SET status = ?, seed_count = ?, candidate_count = ?,
                    platform_count = ?, stop_reason = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    max(0, seed_count),
                    max(0, candidate_count),
                    max(0, platform_count),
                    stop_reason,
                    now,
                    run_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_discovery_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(run_id)
        return dict(row)

    def get_content(self, content_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, platform, source_content_id, content_type, title,
                       description, source_url, author_source_id, author_name,
                       published_at, source_keyword, is_favorite, raw_payload
                FROM library_contents WHERE id = ?
                """,
                (content_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def find_related_contents(
        self,
        term: str,
        *,
        limit: int = 20,
        platforms: Iterable[str] | None = None,
    ) -> list[dict[str, object]]:
        normalized = term.strip()
        if not normalized:
            return []
        # The LIKE pattern is still a bound value; the limit is clamped before
        # interpolation because SQLite does not accept a parameter there in all
        # supported builds.
        bounded_limit = max(1, min(limit, 100))
        pattern = f"%{normalized[:120]}%"
        platform_values = tuple(
            dict.fromkeys(
                str(value).strip() for value in (platforms or ()) if str(value).strip()
            )
        )
        platform_clause = ""
        values: list[object] = [pattern, pattern]
        if platforms is not None and not platform_values:
            platform_clause = " AND 1 = 0"
        elif platform_values:
            placeholders = ", ".join("?" for _ in platform_values)
            platform_clause = f" AND platform IN ({placeholders})"
            values.extend(platform_values)
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, platform, source_content_id, content_type, title,
                       description, source_url, author_source_id, author_name,
                       published_at, source_keyword, is_favorite, raw_payload
                FROM library_contents
                WHERE (
                    lower(COALESCE(title, '')) LIKE lower(?)
                    OR lower(COALESCE(description, '')) LIKE lower(?)
                )
                   {platform_clause}
                ORDER BY COALESCE(published_at, last_collected_at) DESC, id DESC
                LIMIT {bounded_limit}
                """,
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_favorite_contents(self, *, limit: int = 24) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, platform, source_content_id, content_type, title,
                       description, source_url, author_source_id, author_name,
                       published_at, source_keyword, is_favorite, raw_payload
                FROM library_contents
                WHERE is_favorite = 1
                ORDER BY updated_at DESC, id DESC
                LIMIT {bounded_limit}
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_accepted_candidates(
        self,
        *,
        owner_id: str,
        exclude_task_id: str | None = None,
        limit: int = 24,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        clauses = ["owner_id = ?", "state = 'accepted'"]
        values: list[object] = [owner_id]
        if exclude_task_id:
            clauses.append("research_task_id != ?")
            values.append(exclude_task_id)
        values.append(bounded_limit)
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM research_discovery_candidates
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def list_space_entity_candidates(
        self,
        *,
        owner_id: str,
        limit: int = 24,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT c.*, item.space_id AS focus_space_id
                FROM research_space_items item
                JOIN research_spaces space ON space.id = item.space_id
                JOIN research_entity_candidates c ON c.id = item.item_id
                JOIN research_tasks task ON task.id = c.research_task_id
                WHERE item.item_type = 'entity'
                  AND space.owner_id = ?
                  AND space.status = 'active'
                  AND task.user_id = ?
                ORDER BY item.updated_at DESC, item.id DESC
                LIMIT {bounded_limit}
                """,
                (owner_id, owner_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_confirmed_events(
        self,
        *,
        owner_id: str,
        exclude_task_id: str | None = None,
        limit: int = 24,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        clauses = ["task.user_id = ?", "event.status = 'accepted'"]
        values: list[object] = [owner_id]
        if exclude_task_id:
            clauses.append("event.research_task_id != ?")
            values.append(exclude_task_id)
        values.append(bounded_limit)
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT event.*, task.user_id AS owner_id
                FROM research_event_candidates event
                JOIN research_tasks task ON task.id = event.research_task_id
                WHERE {' AND '.join(clauses)}
                ORDER BY event.updated_at DESC, event.id DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def create_seed(
        self,
        *,
        task_id: str,
        run_id: str,
        seed_type: str,
        source_content_id: str | None,
        source_finding_id: str | None = None,
        source_entity_candidate_id: str | None = None,
        source_event_candidate_id: str | None = None,
        source_candidate_id: str | None = None,
        relation_to_intent: str,
        novelty: float,
        confidence: float,
        information_utility: str,
        depth: int = 0,
    ) -> dict[str, object]:
        now = utc_now()
        identifier = self.new_id()
        with connect_database(self.database_path) as connection:
            existing = connection.execute(
                """
                SELECT id FROM research_discovery_seeds
                WHERE research_task_id = ? AND seed_type = ?
                  AND COALESCE(source_content_id, '') = COALESCE(?, '')
                  AND COALESCE(source_entity_candidate_id, '') = COALESCE(?, '')
                  AND COALESCE(source_event_candidate_id, '') = COALESCE(?, '')
                  AND COALESCE(source_candidate_id, '') = COALESCE(?, '')
                ORDER BY created_at DESC LIMIT 1
                """,
                (
                    task_id,
                    seed_type,
                    source_content_id,
                    source_entity_candidate_id,
                    source_event_candidate_id,
                    source_candidate_id,
                ),
            ).fetchone()
            if existing is not None:
                row = connection.execute(
                    "SELECT * FROM research_discovery_seeds WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                if row is not None:
                    return dict(row)
            connection.execute(
                """
                INSERT INTO research_discovery_seeds (
                    id, research_task_id, run_id, seed_type,
                    source_content_id, source_finding_id,
                    source_entity_candidate_id, source_event_candidate_id,
                    source_candidate_id, relation_to_intent, novelty, confidence,
                    information_utility, depth, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    task_id,
                    run_id,
                    seed_type,
                    source_content_id,
                    source_finding_id,
                    source_entity_candidate_id,
                    source_event_candidate_id,
                    source_candidate_id,
                    relation_to_intent[:500],
                    _clamp(novelty),
                    _clamp(confidence),
                    information_utility[:100],
                    depth,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_discovery_seeds WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(identifier)
        return dict(row)

    def list_seeds(self, task_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 200))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM research_discovery_seeds
                WHERE research_task_id = ? ORDER BY created_at, id LIMIT {bounded_limit}
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_candidate(
        self,
        *,
        owner_id: str,
        task_id: str,
        run_id: str,
        candidate_type: str,
        title: str,
        summary: str,
        normalized_key: str,
        parent_candidate_id: str | None,
        source_seed_id: str | None,
        source_content_id: str | None,
        source_platform: str | None,
        scores: dict[str, float],
        score_explanation: dict[str, object],
        counts: dict[str, int],
        depth: int,
        state: str,
        suggested_next_action: str | None,
        experimental_status: str | None,
    ) -> dict[str, object]:
        now = utc_now()
        score_values = {
            key: _clamp(scores.get(key))
            for key in (
                "relevance_score",
                "novelty_score",
                "evidence_strength_score",
                "source_independence_score",
                "cross_platform_score",
                "counterevidence_score",
                "actionability_score",
                "feedback_score",
                "noise_risk_score",
                "marketing_risk_score",
                "saturation_score",
                "resource_cost_score",
                "final_score",
            )
        }
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT id, state FROM research_discovery_candidates
                WHERE owner_id = ? AND candidate_type = ? AND normalized_key = ?
                """,
                (owner_id, candidate_type, normalized_key),
            ).fetchone()
            identifier = str(existing["id"]) if existing is not None else self.new_id()
            previous_state = str(existing["state"]) if existing is not None else None
            protected_states = {"accepted", "converted_to_research", "added_to_space"}
            effective_state = (
                previous_state
                if previous_state in protected_states
                else state
            )
            values: dict[str, object] = {
                "id": identifier,
                "owner_id": owner_id,
                "research_task_id": task_id,
                "run_id": run_id,
                "candidate_type": candidate_type,
                "title": title[:300],
                "summary": summary[:2_000],
                "normalized_key": normalized_key[:300],
                "parent_candidate_id": parent_candidate_id,
                "source_seed_id": source_seed_id,
                "source_content_id": source_content_id,
                "source_platform": source_platform,
                **score_values,
                "score_explanation_json": _dump(score_explanation),
                "content_count": max(0, int(counts.get("content_count", 0))),
                "independent_source_count": max(0, int(counts.get("independent_source_count", 0))),
                "platform_count": max(0, int(counts.get("platform_count", 0))),
                "suspected_repost_count": max(0, int(counts.get("suspected_repost_count", 0))),
                "depth": depth,
                "state": effective_state,
                "suggested_next_action": suggested_next_action,
                "experimental_status": experimental_status,
                "created_at": now,
                "updated_at": now,
            }
            if existing is None:
                columns = ", ".join(values)
                placeholders = ", ".join(f":{key}" for key in values)
                connection.execute(
                    f"INSERT INTO research_discovery_candidates ({columns}) VALUES ({placeholders})",
                    values,
                )
            else:
                update_values = dict(values)
                update_values.pop("id")
                update_values.pop("owner_id")
                update_values.pop("created_at")
                assignments = ", ".join(
                    f"{key} = :{key}" for key in update_values
                )
                update_values["id"] = identifier
                connection.execute(
                    f"UPDATE research_discovery_candidates SET {assignments} WHERE id = :id",
                    update_values,
                )
            row = connection.execute(
                "SELECT * FROM research_discovery_candidates WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None:
                raise DiscoveryNotFound(identifier)
            if previous_state != effective_state:
                connection.execute(
                    """
                    INSERT INTO research_discovery_candidate_events (
                        id, candidate_id, previous_state, next_state,
                        reason, actor_type, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'system', ?)
                    """,
                    (
                        self.new_id(),
                        identifier,
                        previous_state,
                        effective_state,
                        "候选生成或重新评分",
                        now,
                    ),
                )
            connection.execute(
                """
                INSERT INTO research_discovery_candidate_scores (
                    id, candidate_id, scoring_version, final_score,
                    components_json, explanation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.new_id(),
                    identifier,
                    "8d-1-v1",
                    score_values["final_score"],
                    _dump(score_values),
                    _dump(score_explanation),
                    now,
                ),
            )
        return self._candidate_from_row(row)

    def add_candidate_source(
        self,
        *,
        candidate_id: str,
        seed_id: str | None,
        task_id: str,
        content: dict[str, object] | None,
        source_kind: str,
        is_repost: bool,
        repost_of_content_id: str | None,
        similarity_score: float | None,
        independent_group: str | None,
    ) -> dict[str, object]:
        content_id = str(content.get("id")) if isinstance(content, dict) and content.get("id") else None
        now = utc_now()
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id FROM research_discovery_candidate_sources
                WHERE candidate_id = ? AND source_kind = ?
                  AND ((content_id = ? AND ? IS NOT NULL) OR (content_id IS NULL AND ? IS NULL))
                LIMIT 1
                """,
                (candidate_id, source_kind, content_id, content_id, content_id),
            ).fetchone()
            identifier = str(rows["id"]) if rows is not None else self.new_id()
            values = (
                identifier,
                candidate_id,
                seed_id,
                task_id,
                content_id,
                str(content.get("platform")) if isinstance(content, dict) and content.get("platform") else None,
                source_kind,
                str(content.get("title") or "")[:300] if isinstance(content, dict) else None,
                str(content.get("author_name") or "")[:200] if isinstance(content, dict) else None,
                str(content.get("source_url") or "")[:1_000] if isinstance(content, dict) and content.get("source_url") else None,
                int(is_repost),
                repost_of_content_id,
                None if similarity_score is None else _clamp(similarity_score),
                independent_group,
                now,
            )
            if rows is None:
                connection.execute(
                    """
                    INSERT INTO research_discovery_candidate_sources (
                        id, candidate_id, seed_id, research_task_id, content_id,
                        platform, source_kind, source_title, source_author,
                        source_url, is_repost, repost_of_content_id,
                        similarity_score, independent_group, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            else:
                connection.execute(
                    """
                    UPDATE research_discovery_candidate_sources
                    SET seed_id = COALESCE(?, seed_id), is_repost = ?,
                        repost_of_content_id = ?, similarity_score = ?,
                        independent_group = ?
                    WHERE id = ?
                    """,
                    (seed_id, int(is_repost), repost_of_content_id, values[12], independent_group, identifier),
                )
            row = connection.execute(
                "SELECT * FROM research_discovery_candidate_sources WHERE id = ?",
                (identifier,),
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(candidate_id)
        return self._source_from_row(row)

    def list_candidates(
        self,
        *,
        owner_id: str,
        state: str | None = None,
        research_task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        bounded_offset = max(0, offset)
        clauses = ["owner_id = ?"]
        params: list[object] = [owner_id]
        if state:
            clauses.append("state = ?")
            params.append(state)
        else:
            clauses.append("state NOT IN ('ignored', 'dismissed_duplicate', 'expired')")
        if research_task_id:
            clauses.append("research_task_id = ?")
            params.append(research_task_id)
        params.extend([bounded_limit, bounded_offset])
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM research_discovery_candidates
                WHERE {' AND '.join(clauses)}
                ORDER BY CASE state WHEN 'queued' THEN 0 WHEN 'scored' THEN 1 ELSE 2 END,
                         final_score DESC, updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def get_candidate(
        self,
        *,
        owner_id: str,
        candidate_id: str,
        detail: bool = True,
    ) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM research_discovery_candidates
                WHERE id = ? AND owner_id = ?
                """,
                (candidate_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            candidate = self._candidate_from_row(row)
            if not detail:
                return candidate
            candidate["sources"] = [
                self._source_from_row(source)
                for source in connection.execute(
                    """
                    SELECT * FROM research_discovery_candidate_sources
                    WHERE candidate_id = ? ORDER BY created_at, id
                    """,
                    (candidate_id,),
                ).fetchall()
            ]
            candidate["scores"] = [
                self._score_from_row(score)
                for score in connection.execute(
                    """
                    SELECT * FROM research_discovery_candidate_scores
                    WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT 20
                    """,
                    (candidate_id,),
                ).fetchall()
            ]
            candidate["feedback"] = [
                dict(feedback)
                for feedback in connection.execute(
                    """
                    SELECT id, candidate_id, target_type, target_key,
                           feedback_type, scope, scope_key, weight, reason,
                           follow_up_task_id, undone_at, created_at
                    FROM research_discovery_feedback
                    WHERE owner_id = ? AND candidate_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (owner_id, candidate_id),
                ).fetchall()
            ]
            candidate["lifecycle"] = [
                dict(event)
                for event in connection.execute(
                    """
                    SELECT id, previous_state, next_state, feedback_type,
                           reason, actor_type, created_at
                    FROM research_discovery_candidate_events
                    WHERE candidate_id = ? ORDER BY created_at, id
                    """,
                    (candidate_id,),
                ).fetchall()
            ]
        return candidate

    def list_task_candidates(self, task_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM research_discovery_candidates
                WHERE research_task_id = ? ORDER BY final_score DESC, updated_at DESC
                LIMIT ?
                """,
                (task_id, max(1, min(limit, 200))),
            ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def set_candidate_state(
        self,
        *,
        owner_id: str,
        candidate_id: str,
        state: str,
        reason: str | None,
        feedback_type: str | None = None,
        actor_type: str = "owner",
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM research_discovery_candidates WHERE id = ? AND owner_id = ?",
                (candidate_id, owner_id),
            ).fetchone()
            if row is None:
                raise DiscoveryNotFound(candidate_id)
            previous = str(row["state"])
            if previous != state:
                connection.execute(
                    "UPDATE research_discovery_candidates SET state = ?, updated_at = ? WHERE id = ?",
                    (state, now, candidate_id),
                )
                connection.execute(
                    """
                    INSERT INTO research_discovery_candidate_events (
                        id, candidate_id, previous_state, next_state,
                        feedback_type, reason, actor_type, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.new_id(),
                        candidate_id,
                        previous,
                        state,
                        feedback_type,
                        reason,
                        actor_type,
                        now,
                    ),
                )
            saved = connection.execute(
                "SELECT * FROM research_discovery_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        if saved is None:
            raise DiscoveryNotFound(candidate_id)
        return self._candidate_from_row(saved)

    def record_feedback(
        self,
        *,
        owner_id: str,
        candidate_id: str,
        feedback_type: str,
        scope: str,
        scope_key: str | None,
        weight: float,
        reason: str | None,
        follow_up_task_id: str | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = connection.execute(
                """
                SELECT id, candidate_type, normalized_key, source_platform
                FROM research_discovery_candidates
                WHERE id = ? AND owner_id = ?
                """,
                (candidate_id, owner_id),
            ).fetchone()
            if candidate is None:
                raise DiscoveryNotFound(candidate_id)
            identifier = self.new_id()
            connection.execute(
                """
                INSERT INTO research_discovery_feedback (
                    id, owner_id, candidate_id, target_type, target_key,
                    feedback_type, scope, scope_key, weight, reason,
                    follow_up_task_id, created_at
                ) VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    owner_id,
                    candidate_id,
                    str(candidate["normalized_key"]),
                    feedback_type,
                    scope,
                    scope_key,
                    max(-1.0, min(1.0, weight)),
                    reason,
                    follow_up_task_id,
                    now,
                ),
            )
            rule_scope = scope
            rule_key = scope_key
            adjustment = max(-1.0, min(1.0, weight * self._feedback_adjustment(feedback_type)))
            connection.execute(
                """
                INSERT INTO research_discovery_preference_rules (
                    id, owner_id, feedback_type, scope, scope_key,
                    adjustment, rationale, source_feedback_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.new_id(),
                    owner_id,
                    feedback_type,
                    rule_scope,
                    rule_key,
                    adjustment,
                    reason or f"owner feedback: {feedback_type}",
                    identifier,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT id, candidate_id, target_type, target_key, feedback_type,
                       scope, scope_key, weight, reason, follow_up_task_id,
                       undone_at, created_at
                FROM research_discovery_feedback WHERE id = ?
                """,
                (identifier,),
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(identifier)
        return dict(row)

    @staticmethod
    def _feedback_adjustment(feedback_type: str) -> float:
        return {
            "valuable": 0.5,
            "irrelevant": -0.8,
            "already_known": -0.45,
            "duplicate": -1.0,
            "follow": 0.35,
            "mute_topic": -1.0,
            "deprioritize_similar": -0.6,
            "needs_more_evidence": -0.1,
            "converted_to_research": 0.25,
            "added_to_space": 0.3,
        }.get(feedback_type, 0.0)

    def undo_feedback(self, *, owner_id: str, feedback_id: str) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE research_discovery_feedback SET undone_at = ?
                WHERE id = ? AND owner_id = ? AND undone_at IS NULL
                """,
                (now, feedback_id, owner_id),
            )
            if updated.rowcount == 1:
                connection.execute(
                    """
                    UPDATE research_discovery_preference_rules
                    SET active = 0, updated_at = ?
                    WHERE owner_id = ? AND source_feedback_id = ?
                    """,
                    (now, owner_id, feedback_id),
                )
            row = connection.execute(
                """
                SELECT id, candidate_id, target_type, target_key, feedback_type,
                       scope, scope_key, weight, reason, follow_up_task_id,
                       undone_at, created_at
                FROM research_discovery_feedback
                WHERE id = ? AND owner_id = ?
                """,
                (feedback_id, owner_id),
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(feedback_id)
        if updated.rowcount != 1 and row["undone_at"] is None:
            raise DiscoveryConflict("feedback cannot be revoked")
        return dict(row)

    def list_preferences(self, *, owner_id: str) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, feedback_type, scope, scope_key, adjustment,
                       rationale, source_feedback_id, active, created_at, updated_at
                FROM research_discovery_preference_rules
                WHERE owner_id = ? AND active = 1
                ORDER BY updated_at DESC, id DESC
                """,
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def active_feedback_adjustment(
        self,
        *,
        owner_id: str,
        candidate_type: str,
        platform: str | None,
        topic_key: str | None,
        intent_id: str | None,
        candidate_id: str | None = None,
    ) -> tuple[float, list[dict[str, object]]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT feedback_type, scope, scope_key, adjustment, rationale
                FROM research_discovery_preference_rules
                WHERE owner_id = ? AND active = 1
                ORDER BY created_at DESC, id DESC
                """,
                (owner_id,),
            ).fetchall()
            space_ids = {
                str(row["space_id"])
                for row in connection.execute(
                    """
                    SELECT space_id FROM research_space_items
                    WHERE item_type = 'discovery_candidate' AND item_id = ?
                    """,
                    (candidate_id,),
                ).fetchall()
            } if candidate_id else set()
        applicable: list[dict[str, object]] = []
        total = 0.0
        for row in rows:
            scope = str(row["scope"])
            key = row["scope_key"]
            matches = (
                scope == "global"
                or (scope == "platform" and key == platform)
                or (scope == "topic" and key == topic_key)
                or (scope == "research_intent" and key == intent_id)
                or (scope == "research_space" and key in space_ids)
            )
            if matches:
                item = dict(row)
                applicable.append(item)
                total += float(row["adjustment"] or 0)
        return max(-1.0, min(1.0, total)), applicable

    def rescore_candidate(
        self,
        *,
        owner_id: str,
        candidate_id: str,
        scores: dict[str, float],
        explanation: dict[str, object],
        state: str | None = None,
    ) -> dict[str, object]:
        score_values = {
            key: _clamp(scores.get(key))
            for key in (
                "relevance_score",
                "novelty_score",
                "evidence_strength_score",
                "source_independence_score",
                "cross_platform_score",
                "counterevidence_score",
                "actionability_score",
                "feedback_score",
                "noise_risk_score",
                "marketing_risk_score",
                "saturation_score",
                "resource_cost_score",
                "final_score",
            )
        }
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM research_discovery_candidates WHERE id = ? AND owner_id = ?",
                (candidate_id, owner_id),
            ).fetchone()
            if row is None:
                raise DiscoveryNotFound(candidate_id)
            previous_state = str(row["state"])
            effective_state = state or previous_state
            if previous_state in {"accepted", "converted_to_research", "added_to_space"}:
                effective_state = previous_state
            assignments = ", ".join(f"{key} = ?" for key in score_values)
            connection.execute(
                f"UPDATE research_discovery_candidates SET {assignments}, score_explanation_json = ?, state = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                [*score_values.values(), _dump(explanation), effective_state, now, candidate_id, owner_id],
            )
            connection.execute(
                """
                INSERT INTO research_discovery_candidate_scores (
                    id, candidate_id, scoring_version, final_score,
                    components_json, explanation_json, created_at
                ) VALUES (?, ?, '8d-1-v1', ?, ?, ?, ?)
                """,
                (
                    self.new_id(),
                    candidate_id,
                    score_values["final_score"],
                    _dump(score_values),
                    _dump(explanation),
                    now,
                ),
            )
            if previous_state != effective_state:
                connection.execute(
                    """
                    INSERT INTO research_discovery_candidate_events (
                        id, candidate_id, previous_state, next_state,
                        reason, actor_type, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'system', ?)
                    """,
                    (self.new_id(), candidate_id, previous_state, effective_state, "反馈后重新排序", now),
                )
            saved = connection.execute(
                "SELECT * FROM research_discovery_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        if saved is None:
            raise DiscoveryNotFound(candidate_id)
        return self._candidate_from_row(saved)

    def list_task_discoveries(self, task_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        return self.list_candidates(owner_id=self.task_owner(task_id), research_task_id=task_id, limit=limit)

    def task_owner(self, task_id: str) -> str:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id FROM research_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(task_id)
        return str(row["user_id"])

    def get_feedback(self, *, owner_id: str, feedback_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, candidate_id, target_type, target_key, feedback_type,
                       scope, scope_key, weight, reason, follow_up_task_id,
                       undone_at, created_at
                FROM research_discovery_feedback WHERE id = ? AND owner_id = ?
                """,
                (feedback_id, owner_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_space(
        self,
        *,
        owner_id: str,
        name: str,
        description: str | None,
    ) -> dict[str, object]:
        now = utc_now()
        identifier = self.new_id()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO research_spaces (
                    id, owner_id, name, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (identifier, owner_id, name, description, now, now),
            )
        result = self.get_space(owner_id=owner_id, space_id=identifier)
        if result is None:
            raise DiscoveryNotFound(identifier)
        return result

    def list_spaces(self, *, owner_id: str) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.name, s.description, s.status, COUNT(i.id) AS item_count,
                       s.created_at, s.updated_at
                FROM research_spaces s
                LEFT JOIN research_space_items i ON i.space_id = s.id
                WHERE s.owner_id = ?
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.id DESC
                """,
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _space_item_value(
        self,
        connection: sqlite3.Connection,
        item_type: str,
        item_id: str,
    ) -> dict[str, object]:
        queries: dict[str, tuple[str, tuple[object, ...]]] = {
            "research_task": (
                "SELECT id, objective, status, current_round, updated_at FROM research_tasks WHERE id = ?",
                (item_id,),
            ),
            "discovery_candidate": (
                "SELECT id, candidate_type, title, summary, final_score, state, updated_at FROM research_discovery_candidates WHERE id = ?",
                (item_id,),
            ),
            "evidence": (
                "SELECT id, platform, title, description, source_url, updated_at FROM library_contents WHERE id = ?",
                (item_id,),
            ),
            "entity": (
                "SELECT id, entity_type, normalized_name, relevance_to_intent, confidence, status, updated_at FROM research_entity_candidates WHERE id = ?",
                (item_id,),
            ),
            "event": (
                "SELECT id, event_type, title, summary, confidence, status, updated_at FROM research_event_candidates WHERE id = ?",
                (item_id,),
            ),
            "finding": (
                "SELECT id, research_task_id, kind, statement, counterevidence_status, updated_at FROM findings WHERE id = ?",
                (item_id,),
            ),
            "unresolved_question": (
                "SELECT id, research_task_id, unknown, priority, status, evidence_count, updated_at FROM research_unknowns WHERE id = ?",
                (item_id,),
            ),
            "memory": (
                "SELECT id, research_task_id, memory_type, memory_key, confidence, is_current, updated_at FROM research_memory_items WHERE id = ?",
                (item_id,),
            ),
        }
        query = queries.get(item_type)
        if query is None:
            return {}
        row = connection.execute(*query).fetchone()
        return dict(row) if row is not None else {}

    def get_space(self, *, owner_id: str, space_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT s.id, s.name, s.description, s.status,
                       COUNT(i.id) AS item_count, s.created_at, s.updated_at
                FROM research_spaces s
                LEFT JOIN research_space_items i ON i.space_id = s.id
                WHERE s.id = ? AND s.owner_id = ?
                GROUP BY s.id
                """,
                (space_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["items"] = []
            for item in connection.execute(
                """
                SELECT id, space_id, item_type, item_id, position, note,
                       source_candidate_id, created_at, updated_at
                FROM research_space_items WHERE space_id = ?
                ORDER BY position, created_at, id
                """,
                (space_id,),
            ).fetchall():
                value = dict(item)
                value["item"] = self._space_item_value(
                    connection, str(value["item_type"]), str(value["item_id"])
                )
                result["items"].append(value)
        return result

    def _assert_item_owner(
        self,
        connection: sqlite3.Connection,
        owner_id: str,
        item_type: str,
        item_id: str,
    ) -> dict[str, object]:
        if item_type == "discovery_candidate":
            row = connection.execute(
                "SELECT id FROM research_discovery_candidates WHERE id = ? AND owner_id = ?",
                (item_id, owner_id),
            ).fetchone()
        elif item_type == "research_task":
            row = connection.execute(
                "SELECT id FROM research_tasks WHERE id = ? AND user_id = ?",
                (item_id, owner_id),
            ).fetchone()
        elif item_type == "evidence":
            row = connection.execute("SELECT id FROM library_contents WHERE id = ?", (item_id,)).fetchone()
        elif item_type == "entity":
            row = connection.execute(
                """
                SELECT c.id FROM research_entity_candidates c
                JOIN research_tasks t ON t.id = c.research_task_id
                WHERE c.id = ? AND t.user_id = ?
                """,
                (item_id, owner_id),
            ).fetchone()
        elif item_type == "event":
            row = connection.execute(
                """
                SELECT c.id FROM research_event_candidates c
                JOIN research_tasks t ON t.id = c.research_task_id
                WHERE c.id = ? AND t.user_id = ?
                """,
                (item_id, owner_id),
            ).fetchone()
        elif item_type in {"finding", "unresolved_question", "memory"}:
            table = {
                "finding": "findings",
                "unresolved_question": "research_unknowns",
                "memory": "research_memory_items",
            }[item_type]
            row = connection.execute(
                f"""
                SELECT value.id FROM {table} value
                JOIN research_tasks t ON t.id = value.research_task_id
                WHERE value.id = ? AND t.user_id = ?
                """,
                (item_id, owner_id),
            ).fetchone()
        else:
            row = None
        if row is None:
            raise DiscoveryNotFound(f"{item_type}:{item_id}")
        return dict(row)

    def add_space_item(
        self,
        *,
        owner_id: str,
        space_id: str,
        item_type: str,
        item_id: str,
        position: int,
        note: str | None,
        source_candidate_id: str | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            space = connection.execute(
                "SELECT id FROM research_spaces WHERE id = ? AND owner_id = ? AND status = 'active'",
                (space_id, owner_id),
            ).fetchone()
            if space is None:
                raise DiscoveryNotFound(space_id)
            self._assert_item_owner(connection, owner_id, item_type, item_id)
            if source_candidate_id is not None:
                self._assert_item_owner(connection, owner_id, "discovery_candidate", source_candidate_id)
            existing = connection.execute(
                """
                SELECT id FROM research_space_items
                WHERE space_id = ? AND item_type = ? AND item_id = ?
                """,
                (space_id, item_type, item_id),
            ).fetchone()
            identifier = str(existing["id"]) if existing is not None else self.new_id()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO research_space_items (
                        id, space_id, item_type, item_id, position, note,
                        source_candidate_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, space_id, item_type, item_id, position, note, source_candidate_id, now, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE research_space_items
                    SET position = ?, note = ?, source_candidate_id = COALESCE(?, source_candidate_id), updated_at = ?
                    WHERE id = ?
                    """,
                    (position, note, source_candidate_id, now, identifier),
                )
            connection.execute(
                "UPDATE research_spaces SET updated_at = ? WHERE id = ?", (now, space_id)
            )
            if item_type == "discovery_candidate":
                candidate = connection.execute(
                    "SELECT state FROM research_discovery_candidates WHERE id = ? AND owner_id = ?",
                    (item_id, owner_id),
                ).fetchone()
                previous_state = str(candidate["state"]) if candidate is not None else None
                connection.execute(
                    """
                    UPDATE research_discovery_candidates SET state = 'added_to_space', updated_at = ?
                    WHERE id = ? AND owner_id = ? AND state NOT IN ('converted_to_research', 'accepted')
                    """,
                    (now, item_id, owner_id),
                )
                if previous_state is not None and previous_state not in {
                    "converted_to_research",
                    "accepted",
                    "added_to_space",
                }:
                    connection.execute(
                        """
                        INSERT INTO research_discovery_candidate_events (
                            id, candidate_id, previous_state, next_state,
                            reason, actor_type, created_at
                        ) VALUES (?, ?, ?, 'added_to_space', ?, 'owner', ?)
                        """,
                        (
                            self.new_id(),
                            item_id,
                            previous_state,
                            f"加入研究空间 {space_id}",
                            now,
                        ),
                    )
            row = connection.execute(
                """
                SELECT id, space_id, item_type, item_id, position, note,
                       source_candidate_id, created_at, updated_at
                FROM research_space_items WHERE id = ?
                """,
                (identifier,),
            ).fetchone()
        if row is None:
            raise DiscoveryNotFound(identifier)
        result = dict(row)
        result["item"] = self._space_item_value_for_item(item_type, item_id)
        return result

    def _space_item_value_for_item(self, item_type: str, item_id: str) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            return self._space_item_value(connection, item_type, item_id)
