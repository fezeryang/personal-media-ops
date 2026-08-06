from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.db import connect_database
from app.security.provider_secrets import EncryptedProviderSecret
from app.services.ai.evals import (
    FIXED_EVAL_DATASET,
    RECORDED_EVAL_RESPONSE,
    evaluate_recorded_response,
    result_status_for_metrics,
)
from app.services.ai.prompt_registry import candidate_prompt_specs, default_prompt_specs

ROUTE_ROLES = (
    "default",
    "fast",
    "deep",
    "tool_calling",
    "final_report",
    "fallback",
)
PROVIDER_BOOL_FIELDS = {"enabled"}
MODEL_BOOL_FIELDS = {
    "enabled",
    "supports_streaming",
    "supports_tools",
    "supports_thinking",
    "supports_vision",
    "supports_files",
    "supports_structured_output",
}
MODEL_PRICE_FIELDS = {
    "input_price_per_million",
    "output_price_per_million",
    "cached_input_price_per_million",
    "estimated_cost",
    "cache_write_price_per_million",
}
KNOWN_VENDORS = {
    "minimax": ("MiniMax", "subscription_fixed"),
    "deepseek": ("DeepSeek", "pay_as_you_go"),
    "glm": ("GLM", "subscription_fixed"),
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _public_provider(row: sqlite3.Row) -> dict[str, object]:
    result = dict(row)
    result["enabled"] = bool(result["enabled"])
    result["credentials_configured"] = bool(result["credentials_configured"])
    return result


def _model(row: sqlite3.Row) -> dict[str, object]:
    result = dict(row)
    for field in MODEL_BOOL_FIELDS:
        if field in result:
            result[field] = None if result[field] is None else bool(result[field])
    for field in MODEL_PRICE_FIELDS:
        if field in result and result[field] is not None:
            result[field] = _decimal_string(result[field])
    return result


def _decimal_string(value: object) -> str:
    decimal = Decimal(str(value))
    return format(decimal, "f")


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


class AIRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def ensure_governance_defaults(self) -> None:
        """Seed only deterministic registry metadata after migration has passed."""

        now = _utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for spec in default_prompt_specs():
                self._ensure_prompt_version(
                    connection,
                    spec=spec,
                    status="active",
                    now=now,
                )
            for spec in candidate_prompt_specs():
                prompt_key = str(spec["prompt_key"])
                self._ensure_prompt_version(
                    connection,
                    spec=spec,
                    status="candidate",
                    now=now,
                )
                candidate = connection.execute(
                    "SELECT status FROM prompt_versions WHERE prompt_key = ? AND version = ?",
                    (prompt_key, str(spec["version"])),
                ).fetchone()
                definition = connection.execute(
                    "SELECT candidate_version FROM prompt_definitions WHERE prompt_key = ?",
                    (prompt_key,),
                ).fetchone()
                if (
                    candidate is not None
                    and str(candidate["status"]) == "candidate"
                    and definition is not None
                    and definition["candidate_version"] is None
                ):
                    connection.execute(
                        "UPDATE prompt_definitions SET candidate_version = ?, updated_at = ? WHERE prompt_key = ?",
                        (str(spec["version"]), now, prompt_key),
                    )
            for case in FIXED_EVAL_DATASET:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO ai_eval_cases (
                        id, slug, task, expected_intent, key_unknowns_json,
                        required_evidence_types_json, forbidden_scope_drift_json,
                        minimum_sources, partial_completion_allowed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"eval:{case['slug']}",
                        case["slug"],
                        case["task"],
                        case["expected_intent"],
                        json.dumps(case["key_unknowns"], ensure_ascii=False),
                        json.dumps(case["required_evidence_types"], ensure_ascii=False),
                        json.dumps(case["forbidden_scope_drift"], ensure_ascii=False),
                        case["minimum_sources"],
                        int(bool(case["partial_completion_allowed"])),
                        now,
                    ),
                )
            connection.commit()

    @staticmethod
    def _ensure_prompt_version(
        connection: sqlite3.Connection,
        *,
        spec: dict[str, object],
        status: str,
        now: str,
    ) -> None:
        prompt_key = str(spec["prompt_key"])
        version = str(spec["version"])
        connection.execute(
            """
            INSERT OR IGNORE INTO prompt_definitions
                (prompt_key, role, active_version, candidate_version, created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (prompt_key, str(spec["role"]), "v1", now, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO prompt_versions (
                id, prompt_key, version, status, model_family, system_prompt,
                task_template, input_schema_json, output_schema_json,
                temperature, max_tokens, change_reason, activated_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{prompt_key}:{version}",
                prompt_key,
                version,
                status,
                str(spec["model_family"]),
                str(spec["system_prompt"]),
                str(spec["task_template"]),
                json.dumps(spec["input_schema"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(spec["output_schema"], ensure_ascii=False, separators=(",", ":")),
                spec["temperature"],
                spec["max_tokens"],
                str(spec["change_reason"]),
                now if status == "active" else None,
                now,
                now,
            ),
        )

    def list_prompt_definitions(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            definitions = connection.execute(
                """
                SELECT definition.*, active.activated_at AS active_activated_at
                FROM prompt_definitions definition
                LEFT JOIN prompt_versions active
                  ON active.prompt_key = definition.prompt_key
                 AND active.version = definition.active_version
                ORDER BY definition.prompt_key
                """
            ).fetchall()
            result: list[dict[str, object]] = []
            for definition in definitions:
                item = dict(definition)
                item["activated_at"] = item.pop("active_activated_at", None)
                versions = connection.execute(
                    """
                    SELECT prompt_key, ? AS role, version, status, model_family,
                           temperature, max_tokens, change_reason, activated_at,
                           created_at, updated_at
                    FROM prompt_versions
                    WHERE prompt_key = ?
                    ORDER BY created_at DESC, version DESC
                    """,
                    (item["role"], item["prompt_key"]),
                ).fetchall()
                item["versions"] = [dict(version) for version in versions]
                item["recent_eval"] = self._recent_prompt_eval(
                    connection,
                    str(item["prompt_key"]),
                )
                result.append(item)
            return result

    @staticmethod
    def _recent_prompt_eval(
        connection: sqlite3.Connection,
        prompt_key: str,
    ) -> dict[str, object] | None:
        row = connection.execute(
            """
            SELECT run.prompt_key, run.prompt_version, run.status,
                   run.completed_at, COUNT(result.id) AS case_count,
                   SUM(CASE WHEN result.status = 'passed' THEN 1 ELSE 0 END) AS passed_count
            FROM ai_eval_runs run
            LEFT JOIN ai_eval_results result ON result.run_id = run.id
            WHERE run.prompt_key = ?
            GROUP BY run.id
            ORDER BY run.created_at DESC LIMIT 1
            """,
            (prompt_key,),
        ).fetchone()
        return dict(row) if row is not None else None

    def activate_prompt(self, *, prompt_key: str, version: str) -> dict[str, object]:
        now = _utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            definition = connection.execute(
                "SELECT * FROM prompt_definitions WHERE prompt_key = ?",
                (prompt_key,),
            ).fetchone()
            candidate = connection.execute(
                "SELECT * FROM prompt_versions WHERE prompt_key = ? AND version = ?",
                (prompt_key, version),
            ).fetchone()
            if definition is None or candidate is None:
                connection.rollback()
                raise KeyError("prompt version not found")
            if str(candidate["status"]) not in {"candidate", "active"}:
                connection.rollback()
                raise ValueError("only candidate prompt versions can be activated")
            current = str(definition["active_version"])
            if current != version:
                connection.execute(
                    "UPDATE prompt_versions SET status = 'rollback', updated_at = ? WHERE prompt_key = ? AND version = ?",
                    (now, prompt_key, current),
                )
            connection.execute(
                "UPDATE prompt_versions SET status = 'active', activated_at = ?, updated_at = ? WHERE prompt_key = ? AND version = ?",
                (now, now, prompt_key, version),
            )
            connection.execute(
                "UPDATE prompt_definitions SET active_version = ?, candidate_version = NULL, updated_at = ? WHERE prompt_key = ?",
                (version, now, prompt_key),
            )
            connection.commit()
        item = next((item for item in self.list_prompt_definitions() if item["prompt_key"] == prompt_key), None)
        if item is None:
            raise KeyError("prompt definition not found")
        return item

    def rollback_prompt(self, *, prompt_key: str) -> dict[str, object]:
        now = _utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            definition = connection.execute(
                "SELECT * FROM prompt_definitions WHERE prompt_key = ?",
                (prompt_key,),
            ).fetchone()
            previous = connection.execute(
                """
                SELECT * FROM prompt_versions
                WHERE prompt_key = ? AND version != ? AND status = 'rollback'
                ORDER BY updated_at DESC, created_at DESC LIMIT 1
                """,
                (prompt_key, definition["active_version"] if definition else ""),
            ).fetchone()
            if definition is None or previous is None:
                connection.rollback()
                raise ValueError("no rollback prompt version is available")
            connection.execute(
                "UPDATE prompt_versions SET status = 'candidate', updated_at = ? WHERE prompt_key = ? AND version = ?",
                (now, prompt_key, definition["active_version"]),
            )
            connection.execute(
                "UPDATE prompt_versions SET status = 'active', activated_at = ?, updated_at = ? WHERE prompt_key = ? AND version = ?",
                (now, now, prompt_key, previous["version"]),
            )
            connection.execute(
                "UPDATE prompt_definitions SET active_version = ?, candidate_version = ?, updated_at = ? WHERE prompt_key = ?",
                (previous["version"], definition["active_version"], now, prompt_key),
            )
            connection.commit()
        item = next((item for item in self.list_prompt_definitions() if item["prompt_key"] == prompt_key), None)
        if item is None:
            raise KeyError("prompt definition not found")
        return item

    def list_eval_cases(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM ai_eval_cases ORDER BY id"
            ).fetchall()
            result: list[dict[str, object]] = []
            for row in rows:
                latest = connection.execute(
                    """
                    SELECT result.status, result.metrics_json, result.created_at,
                           run.prompt_key, run.prompt_version, run.context_version
                    FROM ai_eval_results result
                    JOIN ai_eval_runs run ON run.id = result.run_id
                    WHERE result.case_id = ?
                    ORDER BY result.created_at DESC, result.id DESC LIMIT 1
                    """,
                    (row["id"],),
                ).fetchone()
                last_result = None
                if latest is not None:
                    last_result = {
                        "status": latest["status"],
                        "metrics": _json_object(latest["metrics_json"]),
                        "created_at": latest["created_at"],
                        "prompt_key": latest["prompt_key"],
                        "prompt_version": latest["prompt_version"],
                        "context_version": latest["context_version"],
                    }
                result.append(
                    {
                    "id": row["id"],
                    "slug": row["slug"],
                    "task": row["task"],
                    "expected_intent": row["expected_intent"],
                    "key_unknowns": json.loads(row["key_unknowns_json"]),
                    "required_evidence_types": json.loads(row["required_evidence_types_json"]),
                    "forbidden_scope_drift": json.loads(row["forbidden_scope_drift_json"]),
                    "minimum_sources": int(row["minimum_sources"]),
                    "partial_completion_allowed": bool(row["partial_completion_allowed"]),
                    "last_result": last_result,
                    }
                )
            return result

    def replay_recorded_task(
        self,
        *,
        prompt_key: str,
        prompt_version: str,
        recorded_task_id: str | None,
        recorded_response: dict[str, object],
        context_version: str = "ctx-v1",
    ) -> dict[str, object]:
        """Evaluate a recorded task without fetching platforms or mutating it."""
        now = _utc_now()
        run_id = str(uuid.uuid4())
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            prompt = connection.execute(
                "SELECT status FROM prompt_versions WHERE prompt_key = ? AND version = ?",
                (prompt_key, prompt_version),
            ).fetchone()
            if prompt is None:
                connection.rollback()
                raise KeyError("prompt version not found")
            if str(prompt["status"]) not in {"active", "candidate"}:
                connection.rollback()
                raise ValueError("recorded replay requires an active or candidate prompt version")
            cases = connection.execute("SELECT * FROM ai_eval_cases ORDER BY id").fetchall()
            connection.execute(
                """
                INSERT INTO ai_eval_runs
                    (id, prompt_key, prompt_version, context_version, status,
                     recorded_task_id, started_at, created_at)
                VALUES (?, ?, ?, ?, 'running', ?, ?, ?)
                """,
                (run_id, prompt_key, prompt_version, context_version, recorded_task_id, now, now),
            )
            statuses: list[str] = []
            for case in cases:
                response = recorded_response.get(str(case["slug"]), {})
                response = response if isinstance(response, dict) else {}
                metrics = evaluate_recorded_response(
                    {
                        "slug": case["slug"],
                        "expected_intent": case["expected_intent"],
                    },
                    response,
                )
                values = [value for key, value in metrics.items() if key != "case_slug"]
                result_status = (
                    "not_instrumented"
                    if not values or all(value == "not_instrumented" for value in values)
                    else result_status_for_metrics(metrics)
                )
                statuses.append(result_status)
                connection.execute(
                    """
                    INSERT INTO ai_eval_results
                        (id, run_id, case_id, status, metrics_json,
                         input_tokens, output_tokens, model_calls, runtime_ms, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        case["id"],
                        result_status,
                        json.dumps(metrics, ensure_ascii=False, separators=(",", ":")),
                        response.get("input_tokens") if isinstance(response.get("input_tokens"), int) else None,
                        response.get("output_tokens") if isinstance(response.get("output_tokens"), int) else None,
                        response.get("model_call_count") if isinstance(response.get("model_call_count"), int) else None,
                        response.get("runtime_ms") if isinstance(response.get("runtime_ms"), int) else None,
                        now,
                    ),
                )
            connection.execute(
                "UPDATE ai_eval_runs SET status = 'completed', completed_at = ? WHERE id = ?",
                (_utc_now(), run_id),
            )
            connection.commit()
        return {
            "run_id": run_id,
            "prompt_key": prompt_key,
            "prompt_version": prompt_version,
            "context_version": context_version,
            "recorded_task_id": recorded_task_id,
            "case_count": len(statuses),
            "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        }

    def replay_recorded_fixture(self, *, prompt_key: str, prompt_version: str) -> dict[str, object]:
        return self.replay_recorded_task(
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            recorded_task_id="stage-8e-recorded-fixture",
            recorded_response=RECORDED_EVAL_RESPONSE,
        )

    @staticmethod
    def _provider_select() -> str:
        return """
            SELECT p.*,
                   EXISTS(
                       SELECT 1 FROM ai_provider_secrets s
                       WHERE s.provider_id = p.id
                   ) AS credentials_configured,
                   (
                       SELECT COUNT(*) FROM ai_models m
                       WHERE m.provider_id = p.id
                   ) AS model_count,
                   (
                       SELECT h.status FROM ai_provider_health_checks h
                       WHERE h.provider_id = p.id
                       ORDER BY h.checked_at DESC LIMIT 1
                   ) AS last_health_status,
                   (
                       SELECT h.latency_ms FROM ai_provider_health_checks h
                       WHERE h.provider_id = p.id
                       ORDER BY h.checked_at DESC LIMIT 1
                   ) AS last_health_latency_ms,
                   (
                       SELECT h.checked_at FROM ai_provider_health_checks h
                       WHERE h.provider_id = p.id
                       ORDER BY h.checked_at DESC LIMIT 1
                   ) AS last_health_checked_at
            FROM ai_providers p
        """

    def list_providers(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                self._provider_select() + " ORDER BY p.created_at, p.id"
            ).fetchall()
        return [_public_provider(row) for row in rows]

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                self._provider_select() + " WHERE p.id = ?",
                (provider_id,),
            ).fetchone()
        return _public_provider(row) if row is not None else None

    def create_provider(
        self,
        *,
        name: str,
        provider_type: str,
        protocol: str,
        base_url: str,
        enabled: bool,
        timeout_seconds: float,
        max_retries: int,
        concurrency_limit: int,
        secret: EncryptedProviderSecret | None = None,
        provider_id: str | None = None,
        vendor: str | None = None,
        instance_label: str | None = None,
        billing_mode: str | None = None,
        billing_profile_id: str | None = None,
        relay_metadata: str = "{}",
        tool_capability_status: str = "unknown",
    ) -> dict[str, object]:
        identifier = provider_id or str(uuid.uuid4())
        now = _utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO ai_providers (
                    id, name, provider_type, protocol, base_url, enabled,
                    timeout_seconds, max_retries, concurrency_limit,
                    vendor, instance_label, billing_mode, billing_profile_id,
                    relay_metadata, tool_capability_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    name,
                    provider_type,
                    protocol,
                    base_url,
                    int(enabled),
                    timeout_seconds,
                    max_retries,
                    concurrency_limit,
                    vendor or KNOWN_VENDORS.get(provider_type, ("unknown", "unknown"))[0],
                    instance_label or name,
                    billing_mode or KNOWN_VENDORS.get(provider_type, ("unknown", "unknown"))[1],
                    billing_profile_id,
                    relay_metadata,
                    tool_capability_status,
                    now,
                    now,
                ),
            )
            if secret is not None:
                self._write_secret(connection, identifier, secret, now)
        result = self.get_provider(identifier)
        assert result is not None
        return result

    @staticmethod
    def _write_secret(
        connection: sqlite3.Connection,
        provider_id: str,
        secret: EncryptedProviderSecret,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO ai_provider_secrets (
                provider_id, encrypted_api_key, nonce, key_version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                encrypted_api_key = excluded.encrypted_api_key,
                nonce = excluded.nonce,
                key_version = excluded.key_version,
                updated_at = excluded.updated_at
            """,
            (
                provider_id,
                secret.ciphertext,
                secret.nonce,
                secret.key_version,
                now,
                now,
            ),
        )

    def set_provider_secret(
        self,
        provider_id: str,
        secret: EncryptedProviderSecret,
    ) -> None:
        with connect_database(self.database_path) as connection:
            if connection.execute(
                "SELECT 1 FROM ai_providers WHERE id = ?", (provider_id,)
            ).fetchone() is None:
                raise KeyError("Provider not found")
            self._write_secret(connection, provider_id, secret, _utc_now())

    def clear_provider_secret(self, provider_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "DELETE FROM ai_provider_secrets WHERE provider_id = ?",
                (provider_id,),
            )

    def list_billing_profiles(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM ai_billing_profiles ORDER BY vendor, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_billing_profile(self, **values: object) -> dict[str, object]:
        identifier = str(uuid.uuid4())
        now = _utc_now()
        fields = [
            "name", "vendor", "billing_mode", "package_name",
            "purchase_amount", "currency", "starts_at", "ends_at",
            "quota_description", "token_quota", "call_limit",
            "concurrency_limit",
        ]
        with connect_database(self.database_path) as connection:
            connection.execute(
                f"INSERT INTO ai_billing_profiles (id, {', '.join(fields)}, created_at, updated_at) "
                f"VALUES ({', '.join('?' for _ in range(len(fields) + 3))})",
                (
                    identifier,
                    *(values.get(field) for field in fields),
                    now,
                    now,
                ),
            )
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM ai_billing_profiles WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise RuntimeError("billing profile could not be read")
        return dict(row)

    def list_provider_price_versions(
        self,
        *,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, object]]:
        query = "SELECT * FROM ai_provider_price_versions WHERE 1 = 1"
        values: list[object] = []
        if provider_id is not None:
            query += " AND provider_id = ?"
            values.append(provider_id)
        if model_id is not None:
            query += " AND model_id = ?"
            values.append(model_id)
        query += " ORDER BY effective_at DESC, id DESC"
        with connect_database(self.database_path) as connection:
            return [dict(row) for row in connection.execute(query, values).fetchall()]

    def create_provider_price_version(self, **values: object) -> dict[str, object]:
        identifier = str(uuid.uuid4())
        now = _utc_now()
        fields = [
            "provider_id", "model_record_id", "model_id",
            "input_price_per_million", "output_price_per_million",
            "cached_input_price_per_million", "cache_write_price_per_million",
            "currency", "effective_at", "source",
        ]
        with connect_database(self.database_path) as connection:
            connection.execute(
                f"INSERT INTO ai_provider_price_versions (id, {', '.join(fields)}, created_at) "
                f"VALUES ({', '.join('?' for _ in range(len(fields) + 2))})",
                (identifier, *(values.get(field) for field in fields), now),
            )
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM ai_provider_price_versions WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise RuntimeError("provider price version could not be read")
        return dict(row)

    def get_provider_secret(self, provider_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT encrypted_api_key, nonce, key_version
                FROM ai_provider_secrets WHERE provider_id = ?
                """,
                (provider_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_provider(self, provider_id: str, **changes: object) -> dict[str, object]:
        allowed = {
            "name",
            "provider_type",
            "protocol",
            "base_url",
            "enabled",
            "timeout_seconds",
            "max_retries",
            "concurrency_limit",
            "vendor",
            "instance_label",
            "billing_mode",
            "billing_profile_id",
            "relay_metadata",
            "tool_capability_status",
            "tool_capability_tested_at",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"Unsupported provider fields: {sorted(invalid)}")
        if not changes:
            provider = self.get_provider(provider_id)
            if provider is None:
                raise KeyError("Provider not found")
            return provider
        values = [int(value) if key in PROVIDER_BOOL_FIELDS else value for key, value in changes.items()]
        assignments = [f"{key} = ?" for key in changes]
        assignments.append("updated_at = ?")
        values.extend([_utc_now(), provider_id])
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if "enabled" in changes and not bool(changes["enabled"]):
                routed_roles = connection.execute(
                    """
                    SELECT r.role
                    FROM ai_model_routes r
                    JOIN ai_models m ON m.id = r.model_id
                    WHERE m.provider_id = ? AND r.model_id IS NOT NULL
                    ORDER BY r.role
                    """,
                    (provider_id,),
                ).fetchall()
                if routed_roles:
                    roles = ", ".join(str(row["role"]) for row in routed_roles)
                    raise RuntimeError(
                        f"Provider is assigned to route(s): {roles}; update routes before disabling"
                    )
            cursor = connection.execute(
                f"UPDATE ai_providers SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise KeyError("Provider not found")
        result = self.get_provider(provider_id)
        assert result is not None
        return result

    def delete_provider(self, provider_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM ai_providers WHERE id = ?", (provider_id,)
            ).fetchone() is None:
                raise KeyError("Provider not found")
            referenced = connection.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM ai_model_routes r
                    JOIN ai_models m ON m.id = r.model_id
                    WHERE m.provider_id = ?
                ) OR EXISTS(
                    SELECT 1 FROM ai_model_invocations
                    WHERE provider_id = ? OR fallback_from_provider_id = ?
                )
                """,
                (provider_id, provider_id, provider_id),
            ).fetchone()[0]
            if referenced:
                raise RuntimeError("Provider is referenced by routes or invocation history")
            connection.execute("DELETE FROM ai_providers WHERE id = ?", (provider_id,))

    def list_models(self, provider_id: str | None = None) -> list[dict[str, object]]:
        query = """
            SELECT m.*, p.name AS provider_name, p.protocol,
                   p.enabled AS provider_enabled
            FROM ai_models m
            JOIN ai_providers p ON p.id = m.provider_id
        """
        values: tuple[object, ...] = ()
        if provider_id is not None:
            query += " WHERE m.provider_id = ?"
            values = (provider_id,)
        query += " ORDER BY p.created_at, m.created_at, m.id"
        with connect_database(self.database_path) as connection:
            rows = connection.execute(query, values).fetchall()
        result = [_model(row) for row in rows]
        for item in result:
            item["provider_enabled"] = bool(item["provider_enabled"])
        return result

    def get_model(self, model_record_id: str) -> dict[str, object] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT m.*, p.name AS provider_name, p.protocol,
                       p.enabled AS provider_enabled
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.id = ?
                """,
                (model_record_id,),
            ).fetchone()
        if row is None:
            return None
        result = _model(row)
        result["provider_enabled"] = bool(result["provider_enabled"])
        return result

    def effective_pricing_model(
        self,
        model: dict[str, object],
        provider_id: str,
    ) -> dict[str, object]:
        """Overlay the latest provider-instance price without guessing a price.

        Model defaults remain useful for legacy records, while a versioned
        provider price is authoritative for an explicitly configured instance.
        Missing values stay missing so cost accounting remains ``unknown``.
        """
        model_id = str(model.get("model_id") or "")
        record_id = str(model.get("id") or "")
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT input_price_per_million, output_price_per_million,
                       cached_input_price_per_million, cache_write_price_per_million,
                       currency, effective_at, source
                FROM ai_provider_price_versions
                WHERE provider_id = ?
                  AND (model_record_id = ? OR (model_record_id IS NULL AND model_id = ?))
                ORDER BY CASE WHEN model_record_id = ? THEN 0 ELSE 1 END,
                         effective_at DESC, id DESC
                LIMIT 1
                """,
                (provider_id, record_id, model_id, record_id),
            ).fetchone()
        if row is None:
            return model
        enriched = dict(model)
        mapping = {
            "input_price_per_million": "input_price_per_million",
            "output_price_per_million": "output_price_per_million",
            "cached_input_price_per_million": "cached_input_price_per_million",
            "cache_write_price_per_million": "cache_write_price_per_million",
            "currency": "price_currency",
            "effective_at": "price_effective_at",
            "source": "price_source",
        }
        for source, target in mapping.items():
            if row[source] is not None:
                enriched[target] = _decimal_string(row[source]) if source.endswith("price_per_million") else row[source]
        return enriched

    def create_model(self, **values: object) -> dict[str, object]:
        identifier = str(uuid.uuid4())
        now = _utc_now()
        fields = [
            "provider_id",
            "model_id",
            "display_name",
            "enabled",
            "context_window",
            "max_output_tokens",
            "supports_streaming",
            "supports_tools",
            "supports_thinking",
            "supports_vision",
            "supports_files",
            "supports_structured_output",
            "capabilities_source",
            "input_price_per_million",
            "output_price_per_million",
            "cached_input_price_per_million",
            "cache_write_price_per_million",
            "price_source",
            "price_currency",
            "price_effective_at",
        ]
        required_fields = set(fields) - {"cache_write_price_per_million", "price_source"}
        missing = required_fields - set(values)
        if missing:
            raise ValueError(f"Missing model fields: {sorted(missing)}")
        encoded = [self._encode_model_value(field, values.get(field)) for field in fields]
        with connect_database(self.database_path) as connection:
            connection.execute(
                f"""
                INSERT INTO ai_models (
                    id, {', '.join(fields)}, created_at, updated_at
                ) VALUES ({', '.join('?' for _ in range(len(fields) + 3))})
                """,
                (identifier, *encoded, now, now),
            )
        result = self.get_model(identifier)
        assert result is not None
        return result

    @staticmethod
    def _encode_model_value(field: str, value: object) -> object:
        if field in MODEL_BOOL_FIELDS:
            return None if value is None else int(bool(value))
        if field in MODEL_PRICE_FIELDS:
            return None if value is None else str(value)
        return value

    def update_model(self, model_record_id: str, **changes: object) -> dict[str, object]:
        allowed = {
            "display_name",
            "enabled",
            "context_window",
            "max_output_tokens",
            "supports_streaming",
            "supports_tools",
            "supports_thinking",
            "supports_vision",
            "supports_files",
            "supports_structured_output",
            "capabilities_source",
            "last_health_status",
            "last_health_checked_at",
            "input_price_per_million",
            "output_price_per_million",
            "cached_input_price_per_million",
            "cache_write_price_per_million",
            "price_source",
            "price_currency",
            "price_effective_at",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"Unsupported model fields: {sorted(invalid)}")
        if not changes:
            model = self.get_model(model_record_id)
            if model is None:
                raise KeyError("Model not found")
            return model
        values = [self._encode_model_value(key, value) for key, value in changes.items()]
        assignments = [f"{key} = ?" for key in changes]
        assignments.append("updated_at = ?")
        values.extend([_utc_now(), model_record_id])
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if "enabled" in changes and not bool(changes["enabled"]):
                routed_roles = connection.execute(
                    """
                    SELECT role FROM ai_model_routes
                    WHERE model_id = ?
                    ORDER BY role
                    """,
                    (model_record_id,),
                ).fetchall()
                if routed_roles:
                    roles = ", ".join(str(row["role"]) for row in routed_roles)
                    raise RuntimeError(
                        f"Model is assigned to route(s): {roles}; update routes before disabling"
                    )
            cursor = connection.execute(
                f"UPDATE ai_models SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise KeyError("Model not found")
        result = self.get_model(model_record_id)
        assert result is not None
        return result

    def delete_model(self, model_record_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            referenced = connection.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM ai_model_routes WHERE model_id = ?
                ) OR EXISTS(
                    SELECT 1 FROM ai_model_invocations WHERE model_record_id = ?
                )
                """,
                (model_record_id, model_record_id),
            ).fetchone()[0]
            if referenced:
                raise RuntimeError("Model is referenced by routes or invocation history")
            cursor = connection.execute(
                "DELETE FROM ai_models WHERE id = ?", (model_record_id,)
            )
            if cursor.rowcount != 1:
                raise KeyError("Model not found")

    def list_routes(self) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT r.role, r.model_id AS model_record_id, r.updated_at,
                       m.model_id, m.display_name, m.enabled,
                       p.id AS provider_id, p.name AS provider_name,
                       p.vendor, p.billing_mode,
                       p.enabled AS provider_enabled
                FROM ai_model_routes r
                LEFT JOIN ai_models m ON m.id = r.model_id
                LEFT JOIN ai_providers p ON p.id = m.provider_id
                ORDER BY CASE r.role
                    WHEN 'default' THEN 1 WHEN 'fast' THEN 2
                    WHEN 'deep' THEN 3 WHEN 'tool_calling' THEN 4
                    WHEN 'final_report' THEN 5 ELSE 6 END
                """
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["model_enabled"] = (
                None if item.pop("enabled") is None else bool(row["enabled"])
            )
            item["provider_enabled"] = (
                None
                if item["provider_enabled"] is None
                else bool(item["provider_enabled"])
            )
            result.append(item)
        return result

    def replace_routes(self, routes: dict[str, str | None]) -> list[dict[str, object]]:
        invalid = set(routes) - set(ROUTE_ROLES)
        if invalid:
            raise ValueError(f"Unsupported route roles: {sorted(invalid)}")
        now = _utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for role, model_record_id in routes.items():
                if model_record_id is not None:
                    row = connection.execute(
                        """
                        SELECT m.enabled, p.enabled
                        FROM ai_models m
                        JOIN ai_providers p ON p.id = m.provider_id
                        WHERE m.id = ?
                        """,
                        (model_record_id,),
                    ).fetchone()
                    if row is None:
                        raise KeyError("Model not found")
                    if not bool(row[0]) or not bool(row[1]):
                        raise RuntimeError("Disabled provider or model cannot be routed")
                connection.execute(
                    """
                    UPDATE ai_model_routes
                    SET model_id = ?, updated_at = ? WHERE role = ?
                    """,
                    (model_record_id, now, role),
                )
        return self.list_routes()

    def get_route_target(self, role: str) -> tuple[dict[str, object], dict[str, object]]:
        if role not in ROUTE_ROLES:
            raise ValueError("Unsupported model route role")
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT model_id FROM ai_model_routes WHERE role = ?", (role,)
            ).fetchone()
        if row is None or row[0] is None:
            raise RuntimeError(f"Model route '{role}' is not configured")
        return self.get_model_target(str(row[0]))

    def get_model_target(
        self, model_record_id: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        model = self.get_model(model_record_id)
        if model is None:
            raise KeyError("Model not found")
        provider = self.get_provider(str(model["provider_id"]))
        if provider is None:
            raise KeyError("Provider not found")
        if not bool(provider["enabled"]):
            raise RuntimeError("Provider is disabled")
        if not bool(model["enabled"]):
            raise RuntimeError("Model is disabled")
        return provider, model

    def record_health(
        self,
        *,
        provider_id: str,
        model_id: str | None,
        check_kind: str,
        status: str,
        checked_at: str,
        latency_ms: int | None,
        error_code: str | None,
        error_summary: str | None,
    ) -> dict[str, object]:
        identifier = str(uuid.uuid4())
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO ai_provider_health_checks (
                    id, provider_id, model_id, check_kind, status, checked_at,
                    latency_ms, error_code, error_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    provider_id,
                    model_id,
                    check_kind,
                    status,
                    checked_at,
                    latency_ms,
                    error_code,
                    error_summary,
                ),
            )
        return {
            "id": identifier,
            "provider_id": provider_id,
            "model_id": model_id,
            "check_kind": check_kind,
            "status": status,
            "checked_at": checked_at,
            "latency_ms": latency_ms,
            "error_code": error_code,
            "error_summary": error_summary,
        }

    def list_health(self, limit: int = 100) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT h.*, p.name AS provider_name
                FROM ai_provider_health_checks h
                JOIN ai_providers p ON p.id = h.provider_id
                ORDER BY h.checked_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def start_invocation(
        self,
        *,
        provider_id: str,
        model_record_id: str,
        model_id: str,
        route_role: str | None,
        request_correlation_id: str,
        attempt_number: int,
        is_fallback: bool,
        research_task_id: str | None = None,
        fallback_from_provider_id: str | None = None,
        fallback_from_model_id: str | None = None,
        fallback_reason: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
        context_version: str | None = None,
        tool_contract_version: str | None = None,
    ) -> str:
        identifier = str(uuid.uuid4())
        with connect_database(self.database_path) as connection:
            provider_row = connection.execute(
                "SELECT vendor, billing_profile_id, billing_mode FROM ai_providers WHERE id = ?",
                (provider_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO ai_model_invocations (
                    id, provider_id, model_record_id, model_id, route_role,
                    status, started_at, request_correlation_id, attempt_number,
                    is_fallback, research_task_id, fallback_from_provider_id,
                    fallback_from_model_id, fallback_reason, vendor,
                    provider_instance_id, billing_profile_id, billing_mode,
                    estimated_cost_kind, prompt_key, prompt_version,
                    context_version, tool_contract_version
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    provider_id,
                    model_record_id,
                    model_id,
                    route_role,
                    _utc_now(),
                    request_correlation_id,
                    attempt_number,
                    int(is_fallback),
                    research_task_id,
                    fallback_from_provider_id,
                    fallback_from_model_id,
                    fallback_reason,
                    provider_row["vendor"] if provider_row is not None else None,
                    provider_id,
                    provider_row["billing_profile_id"] if provider_row is not None else None,
                    provider_row["billing_mode"] if provider_row is not None else None,
                    (
                        "not_applicable"
                        if provider_row is not None and provider_row["billing_mode"] == "subscription_fixed"
                        else "unavailable"
                        if provider_row is None or provider_row["billing_mode"] in {"unknown", None}
                        else "estimated"
                    ),
                    prompt_key,
                    prompt_version,
                    context_version,
                    tool_contract_version,
                ),
            )
        return identifier

    def finish_invocation(
        self,
        invocation_id: str,
        *,
        status: str,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cached_tokens: int | None = None,
        cache_write_tokens: int | None = None,
        estimated_cost: Decimal | None = None,
        price_currency: str | None = None,
        pricing_effective_at: str | None = None,
        price_source: str | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE ai_model_invocations SET
                    status = ?, finished_at = ?, latency_ms = ?,
                    input_tokens = ?, output_tokens = ?, cached_tokens = ?,
                    cache_write_tokens = ?,
                    estimated_cost = ?, price_currency = ?,
                    pricing_effective_at = ?, price_source = ?,
                    estimated_cost_kind = CASE
                        WHEN billing_mode = 'subscription_fixed' THEN 'not_applicable'
                        WHEN ? IS NULL THEN 'unavailable'
                        ELSE 'estimated'
                    END,
                    error_code = ?, error_summary = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    status,
                    _utc_now(),
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    cached_tokens,
                    cache_write_tokens,
                    str(estimated_cost) if estimated_cost is not None else None,
                    price_currency,
                    pricing_effective_at,
                    price_source,
                    str(estimated_cost) if estimated_cost is not None else None,
                    error_code,
                    error_summary,
                    invocation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Invocation was not running")

    def invocation_cost(
        self,
        *,
        request_correlation_id: str,
        research_task_id: str,
    ) -> Decimal | None:
        """Return the chargeable cost for one gateway request correlation.

        A fallback may create more than one invocation. Summing the recorded
        attempts preserves the actual amount spent while keeping a missing
        price as ``None`` rather than manufacturing a zero.
        """
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT SUM(estimated_cost) AS total_cost
                FROM ai_model_invocations
                WHERE request_correlation_id = ?
                  AND research_task_id = ?
                  AND estimated_cost IS NOT NULL
                """,
                (request_correlation_id, research_task_id),
            ).fetchone()
        if row is None or row["total_cost"] is None:
            return None
        return Decimal(str(row["total_cost"]))

    def invocation_billing(
        self,
        *,
        request_correlation_id: str,
        research_task_id: str,
    ) -> dict[str, object]:
        """Return the durable billing labels for one logical gateway call."""
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT SUM(estimated_cost) AS estimated_cost,
                       MAX(CASE WHEN status = 'succeeded' THEN price_currency END)
                           AS currency,
                       MAX(CASE WHEN status = 'succeeded' THEN price_source END)
                           AS price_source
                FROM ai_model_invocations
                WHERE request_correlation_id = ? AND research_task_id = ?
                """,
                (request_correlation_id, research_task_id),
            ).fetchone()
        if row is None:
            return {"estimated_cost": None, "currency": None, "price_source": None}
        return {
            "estimated_cost": _decimal_string(row["estimated_cost"])
            if row["estimated_cost"] is not None
            else None,
            "currency": row["currency"],
            "price_source": row["price_source"],
        }

    def list_invocations(self, limit: int = 100) -> list[dict[str, object]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT i.*, p.name AS provider_name, m.display_name
                FROM ai_model_invocations i
                JOIN ai_providers p ON p.id = i.provider_id
                JOIN ai_models m ON m.id = i.model_record_id
                ORDER BY i.started_at DESC, i.attempt_number DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["is_fallback"] = bool(item["is_fallback"])
            if item["estimated_cost"] is not None:
                item["estimated_cost"] = _decimal_string(item["estimated_cost"])
        return result

    def usage_summary(self) -> dict[str, object]:
        with connect_database(self.database_path) as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS invocation_count,
                    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END)
                        AS success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
                        AS failure_count,
                    AVG(CASE WHEN status != 'running' THEN latency_ms END)
                        AS average_latency_ms,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                    SUM(CASE
                        WHEN status = 'succeeded'
                         AND estimated_cost IS NULL
                         AND COALESCE(billing_mode, 'unknown') != 'subscription_fixed'
                        THEN 1 ELSE 0 END
                    ) AS uncosted_invocation_count,
                    SUM(CASE WHEN estimated_cost IS NOT NULL THEN 1 ELSE 0 END)
                        AS costed_invocation_count,
                    COUNT(DISTINCT CASE
                        WHEN estimated_cost IS NOT NULL THEN price_currency END
                    ) AS cost_currency_count,
                    SUM(estimated_cost) AS estimated_cost,
                    MIN(CASE
                        WHEN estimated_cost IS NOT NULL THEN price_currency END
                    ) AS price_currency
                FROM ai_model_invocations
                """
            ).fetchone()
            provider_rows = connection.execute(
                """
                SELECT p.id AS key, p.name AS label,
                       COUNT(*) AS invocation_count,
                       SUM(CASE WHEN i.status = 'succeeded' THEN 1 ELSE 0 END)
                           AS success_count,
                       AVG(i.latency_ms) AS average_latency_ms,
                       COALESCE(SUM(i.input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(i.output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(i.cached_tokens), 0) AS cached_tokens
                FROM ai_model_invocations i
                JOIN ai_providers p ON p.id = i.provider_id
                GROUP BY p.id, p.name ORDER BY invocation_count DESC, p.name
                """
            ).fetchall()
            model_rows = connection.execute(
                """
                SELECT i.model_id AS key, m.display_name AS label,
                       COUNT(*) AS invocation_count,
                       SUM(CASE WHEN i.status = 'succeeded' THEN 1 ELSE 0 END)
                           AS success_count,
                       AVG(i.latency_ms) AS average_latency_ms,
                       COALESCE(SUM(i.input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(i.output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(i.cached_tokens), 0) AS cached_tokens
                FROM ai_model_invocations i
                JOIN ai_models m ON m.id = i.model_record_id
                GROUP BY i.model_id, m.display_name
                ORDER BY invocation_count DESC, m.display_name
                """
            ).fetchall()
            role_rows = connection.execute(
                """
                SELECT COALESCE(route_role, 'direct') AS key,
                       COALESCE(route_role, 'direct') AS label,
                       COUNT(*) AS invocation_count,
                       SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END)
                           AS success_count,
                       AVG(latency_ms) AS average_latency_ms,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                FROM ai_model_invocations
                GROUP BY COALESCE(route_role, 'direct')
                ORDER BY invocation_count DESC, key
                """
            ).fetchall()
            cost_rows = connection.execute(
                """
                SELECT price_currency, SUM(estimated_cost) AS estimated_cost
                FROM ai_model_invocations
                WHERE estimated_cost IS NOT NULL
                GROUP BY price_currency ORDER BY price_currency
                """
            ).fetchall()
        total = dict(totals)
        invocation_count = int(total["invocation_count"])
        success_count = int(total["success_count"] or 0)
        uncosted = int(total["uncosted_invocation_count"] or 0)
        currency_count = int(total.pop("cost_currency_count") or 0)
        estimated = total["estimated_cost"]
        total["success_rate"] = (
            success_count / invocation_count if invocation_count else None
        )
        total["average_latency_ms"] = (
            round(float(total["average_latency_ms"]), 2)
            if total["average_latency_ms"] is not None
            else None
        )
        total["estimated_cost"] = (
            _decimal_string(estimated)
            if estimated is not None and uncosted == 0 and currency_count == 1
            else None
        )
        if total["estimated_cost"] is None:
            total["price_currency"] = None
        return {
            "totals": total,
            "by_provider": [_usage_group(row) for row in provider_rows],
            "by_model": [_usage_group(row) for row in model_rows],
            "by_role": [_usage_group(row) for row in role_rows],
            "cost_by_currency": [
                {
                    "currency": row["price_currency"],
                    "estimated_cost": _decimal_string(row["estimated_cost"]),
                }
                for row in cost_rows
            ],
            "recent_invocations": self.list_invocations(limit=50),
        }


def _usage_group(row: sqlite3.Row) -> dict[str, object]:
    result = dict(row)
    count = int(result["invocation_count"])
    successes = int(result["success_count"] or 0)
    result["success_rate"] = successes / count if count else None
    result["average_latency_ms"] = (
        round(float(result["average_latency_ms"]), 2)
        if result["average_latency_ms"] is not None
        else None
    )
    return result
