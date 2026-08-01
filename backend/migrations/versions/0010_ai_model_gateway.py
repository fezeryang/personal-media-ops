"""Add encrypted AI providers, models, routes, health, and invocations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_ai_model_gateway"
down_revision: str | Sequence[str] | None = "0009_metrics_and_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOCOL_CHECK = "protocol IN ('anthropic_compatible', 'openai_compatible')"
HEALTH_CHECK = (
    "status IN ('healthy', 'degraded', 'unreachable', "
    "'authentication_failed', 'model_not_found', 'rate_limited', "
    "'protocol_error', 'disabled')"
)
ROUTE_CHECK = (
    "role IN ('default', 'fast', 'deep', 'tool_calling', "
    "'final_report', 'fallback')"
)
ROLES = ("default", "fast", "deep", "tool_calling", "final_report", "fallback")


def _optional_bool(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column} IS NULL OR {column} IN (0, 1)",
        name=name,
    )


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column("protocol", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("name", name="uq_ai_providers_name"),
        sa.CheckConstraint(PROTOCOL_CHECK, name="ck_ai_providers_protocol"),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_providers_enabled"),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 600",
            name="ck_ai_providers_timeout",
        ),
        sa.CheckConstraint(
            "max_retries BETWEEN 0 AND 5",
            name="ck_ai_providers_retries",
        ),
        sa.CheckConstraint(
            "concurrency_limit BETWEEN 1 AND 20",
            name="ck_ai_providers_concurrency",
        ),
    )
    op.create_index("idx_ai_providers_enabled", "ai_providers", ["enabled"])

    op.create_table(
        "ai_provider_secrets",
        sa.Column("provider_id", sa.Text(), primary_key=True),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_ai_provider_secrets_provider",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("key_version >= 1", name="ck_ai_provider_secrets_version"),
        sa.CheckConstraint("length(nonce) = 12", name="ck_ai_provider_secrets_nonce"),
        sa.CheckConstraint(
            "length(encrypted_api_key) >= 17",
            name="ck_ai_provider_secrets_ciphertext",
        ),
    )

    op.create_table(
        "ai_models",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_window", sa.Integer()),
        sa.Column("max_output_tokens", sa.Integer()),
        sa.Column("supports_streaming", sa.Integer()),
        sa.Column("supports_tools", sa.Integer()),
        sa.Column("supports_thinking", sa.Integer()),
        sa.Column("supports_vision", sa.Integer()),
        sa.Column("supports_files", sa.Integer()),
        sa.Column("supports_structured_output", sa.Integer()),
        sa.Column("capabilities_source", sa.Text(), nullable=False),
        sa.Column("last_health_status", sa.Text()),
        sa.Column("last_health_checked_at", sa.Text()),
        sa.Column("input_price_per_million", sa.Numeric(24, 12)),
        sa.Column("output_price_per_million", sa.Numeric(24, 12)),
        sa.Column("cached_input_price_per_million", sa.Numeric(24, 12)),
        sa.Column("price_currency", sa.Text()),
        sa.Column("price_effective_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_ai_models_provider",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "model_id",
            name="uq_ai_models_provider_model",
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_models_enabled"),
        sa.CheckConstraint(
            "context_window IS NULL OR context_window > 0",
            name="ck_ai_models_context_window",
        ),
        sa.CheckConstraint(
            "max_output_tokens IS NULL OR max_output_tokens > 0",
            name="ck_ai_models_max_output",
        ),
        _optional_bool("supports_streaming", "ck_ai_models_streaming"),
        _optional_bool("supports_tools", "ck_ai_models_tools"),
        _optional_bool("supports_thinking", "ck_ai_models_thinking"),
        _optional_bool("supports_vision", "ck_ai_models_vision"),
        _optional_bool("supports_files", "ck_ai_models_files"),
        _optional_bool(
            "supports_structured_output",
            "ck_ai_models_structured_output",
        ),
        sa.CheckConstraint(
            "capabilities_source IN ('unknown', 'provider', 'user', 'tested')",
            name="ck_ai_models_capabilities_source",
        ),
        sa.CheckConstraint(
            "last_health_status IS NULL OR " + HEALTH_CHECK.replace("status", "last_health_status"),
            name="ck_ai_models_health",
        ),
        sa.CheckConstraint(
            "input_price_per_million IS NULL OR input_price_per_million >= 0",
            name="ck_ai_models_input_price",
        ),
        sa.CheckConstraint(
            "output_price_per_million IS NULL OR output_price_per_million >= 0",
            name="ck_ai_models_output_price",
        ),
        sa.CheckConstraint(
            "cached_input_price_per_million IS NULL "
            "OR cached_input_price_per_million >= 0",
            name="ck_ai_models_cached_price",
        ),
        sa.CheckConstraint(
            "(input_price_per_million IS NULL "
            "AND output_price_per_million IS NULL "
            "AND cached_input_price_per_million IS NULL) "
            "OR (price_currency IS NOT NULL AND price_effective_at IS NOT NULL)",
            name="ck_ai_models_price_metadata",
        ),
    )
    op.create_index(
        "idx_ai_models_provider_enabled",
        "ai_models",
        ["provider_id", "enabled"],
    )

    op.create_table(
        "ai_model_routes",
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("model_id", sa.Text()),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ai_models.id"],
            name="fk_ai_model_routes_model",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(ROUTE_CHECK, name="ck_ai_model_routes_role"),
    )
    op.create_index("idx_ai_model_routes_model", "ai_model_routes", ["model_id"])
    route_table = sa.table(
        "ai_model_routes",
        sa.column("role", sa.Text()),
        sa.column("model_id", sa.Text()),
        sa.column("updated_at", sa.Text()),
    )
    op.bulk_insert(
        route_table,
        [
            {"role": role, "model_id": None, "updated_at": "1970-01-01T00:00:00Z"}
            for role in ROLES
        ],
    )

    op.create_table(
        "ai_provider_health_checks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text()),
        sa.Column("check_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_summary", sa.Text()),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_ai_provider_health_provider",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(HEALTH_CHECK, name="ck_ai_provider_health_status"),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_provider_health_latency",
        ),
    )
    op.create_index(
        "idx_ai_provider_health_provider_checked",
        "ai_provider_health_checks",
        ["provider_id", "checked_at"],
    )

    op.create_table(
        "ai_model_invocations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_record_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("route_role", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cached_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(24, 12)),
        sa.Column("price_currency", sa.Text()),
        sa.Column("pricing_effective_at", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("request_correlation_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("is_fallback", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_from_provider_id", sa.Text()),
        sa.Column("fallback_from_model_id", sa.Text()),
        sa.Column("fallback_reason", sa.Text()),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_ai_model_invocations_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_record_id"],
            ["ai_models.id"],
            name="fk_ai_model_invocations_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fallback_from_provider_id"],
            ["ai_providers.id"],
            name="fk_ai_model_invocations_fallback_provider",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "route_role IS NULL OR " + ROUTE_CHECK.replace("role", "route_role"),
            name="ck_ai_model_invocations_role",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_ai_model_invocations_status",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_model_invocations_latency",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_model_invocations_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_model_invocations_output_tokens",
        ),
        sa.CheckConstraint(
            "cached_tokens IS NULL OR cached_tokens >= 0",
            name="ck_ai_model_invocations_cached_tokens",
        ),
        sa.CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_ai_model_invocations_cost",
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_ai_invocations_attempt"),
        sa.CheckConstraint("is_fallback IN (0, 1)", name="ck_ai_invocations_fallback"),
    )
    op.create_index(
        "idx_ai_invocations_started",
        "ai_model_invocations",
        ["started_at"],
    )
    op.create_index(
        "idx_ai_invocations_provider_model",
        "ai_model_invocations",
        ["provider_id", "model_id"],
    )
    op.create_index(
        "idx_ai_invocations_route_started",
        "ai_model_invocations",
        ["route_role", "started_at"],
    )
    op.create_index(
        "idx_ai_invocations_correlation",
        "ai_model_invocations",
        ["request_correlation_id", "attempt_number"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    configured = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM ai_providers) "
            "OR EXISTS(SELECT 1 FROM ai_model_invocations)"
        )
    ).scalar()
    if configured:
        raise RuntimeError(
            "refusing to discard configured AI providers or invocation history"
        )
    op.drop_index("idx_ai_invocations_correlation", table_name="ai_model_invocations")
    op.drop_index("idx_ai_invocations_route_started", table_name="ai_model_invocations")
    op.drop_index("idx_ai_invocations_provider_model", table_name="ai_model_invocations")
    op.drop_index("idx_ai_invocations_started", table_name="ai_model_invocations")
    op.drop_table("ai_model_invocations")
    op.drop_index(
        "idx_ai_provider_health_provider_checked",
        table_name="ai_provider_health_checks",
    )
    op.drop_table("ai_provider_health_checks")
    op.drop_index("idx_ai_model_routes_model", table_name="ai_model_routes")
    op.drop_table("ai_model_routes")
    op.drop_index("idx_ai_models_provider_enabled", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_table("ai_provider_secrets")
    op.drop_index("idx_ai_providers_enabled", table_name="ai_providers")
    op.drop_table("ai_providers")
