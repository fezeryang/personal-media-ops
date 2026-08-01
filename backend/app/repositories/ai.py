from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.db import connect_database
from app.security.provider_secrets import EncryptedProviderSecret

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


class AIRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

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
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "price_currency",
            "price_effective_at",
        ]
        missing = set(fields) - set(values)
        if missing:
            raise ValueError(f"Missing model fields: {sorted(missing)}")
        encoded = [self._encode_model_value(field, values[field]) for field in fields]
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
    ) -> str:
        identifier = str(uuid.uuid4())
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO ai_model_invocations (
                    id, provider_id, model_record_id, model_id, route_role,
                    status, started_at, request_correlation_id, attempt_number,
                    is_fallback, research_task_id, fallback_from_provider_id,
                    fallback_from_model_id, fallback_reason
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)
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
        estimated_cost: Decimal | None = None,
        price_currency: str | None = None,
        pricing_effective_at: str | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        with connect_database(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE ai_model_invocations SET
                    status = ?, finished_at = ?, latency_ms = ?,
                    input_tokens = ?, output_tokens = ?, cached_tokens = ?,
                    estimated_cost = ?, price_currency = ?,
                    pricing_effective_at = ?, error_code = ?, error_summary = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    status,
                    _utc_now(),
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    cached_tokens,
                    str(estimated_cost) if estimated_cost is not None else None,
                    price_currency,
                    pricing_effective_at,
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
                        WHEN status = 'succeeded' AND estimated_cost IS NULL
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
