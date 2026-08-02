"""Persist Phase 8C coverage, runtime, evidence, and billing metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_cross_platform_research_completion"
down_revision: str | Sequence[str] | None = "0012_research_quality_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BILLING_MODES = (
    "subscription_fixed",
    "pay_as_you_go",
    "prepaid_balance",
    "quota_bundle",
    "relay",
    "unknown",
)
QUERY_STATUSES = (
    "generated",
    "rejected_generic",
    "rejected_duplicate",
    "rejected_low_relevance",
    "rejected_low_value",
    "approved_pending",
    "executing",
    "completed",
    "skipped_budget",
    "skipped_saturation",
    "skipped_low_marginal_value",
    "superseded",
    "failed",
    "cancelled",
    # These aliases remain readable for rows created before this migration.
    "candidate",
    "approved",
    "rejected",
    "running",
)


def _in_check(column: str, values: Sequence[str]) -> str:
    encoded = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({encoded})"


def upgrade() -> None:
    op.create_table(
        "ai_billing_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("vendor", sa.Text(), nullable=False),
        sa.Column("billing_mode", sa.Text(), nullable=False),
        sa.Column("package_name", sa.Text()),
        sa.Column("purchase_amount", sa.Numeric(24, 12)),
        sa.Column("currency", sa.Text()),
        sa.Column("starts_at", sa.Text()),
        sa.Column("ends_at", sa.Text()),
        sa.Column("quota_description", sa.Text()),
        sa.Column("token_quota", sa.Integer()),
        sa.Column("call_limit", sa.Integer()),
        sa.Column("concurrency_limit", sa.Integer()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("name", name="uq_ai_billing_profiles_name"),
        sa.CheckConstraint(
            _in_check("billing_mode", BILLING_MODES),
            name="ck_ai_billing_profiles_mode",
        ),
        sa.CheckConstraint(
            "purchase_amount IS NULL OR purchase_amount >= 0",
            name="ck_ai_billing_profiles_amount",
        ),
        sa.CheckConstraint(
            "token_quota IS NULL OR token_quota >= 0",
            name="ck_ai_billing_profiles_tokens",
        ),
        sa.CheckConstraint(
            "call_limit IS NULL OR call_limit >= 0",
            name="ck_ai_billing_profiles_calls",
        ),
        sa.CheckConstraint(
            "concurrency_limit IS NULL OR concurrency_limit BETWEEN 1 AND 20",
            name="ck_ai_billing_profiles_concurrency",
        ),
    )

    with op.batch_alter_table("ai_providers", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("vendor", sa.Text(), nullable=False, server_default="unknown")
        )
        batch_op.add_column(sa.Column("instance_label", sa.Text()))
        batch_op.add_column(
            sa.Column(
                "billing_mode",
                sa.Text(),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(sa.Column("billing_profile_id", sa.Text()))
        batch_op.add_column(
            sa.Column("relay_metadata", sa.Text(), nullable=False, server_default="{}")
        )
        batch_op.add_column(
            sa.Column(
                "tool_capability_status",
                sa.Text(),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(sa.Column("tool_capability_tested_at", sa.Text()))
        batch_op.create_foreign_key(
            "fk_ai_providers_billing_profile",
            "ai_billing_profiles",
            ["billing_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_ai_providers_billing_mode",
            _in_check("billing_mode", BILLING_MODES),
        )
        batch_op.create_check_constraint(
            "ck_ai_providers_tool_status",
            "tool_capability_status IN ('unknown', 'tested', 'unsupported')",
        )

    op.create_index(
        "idx_ai_providers_vendor_billing",
        "ai_providers",
        ["vendor", "billing_mode"],
    )

    with op.batch_alter_table("ai_models", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("cache_write_price_per_million", sa.Numeric(24, 12)))
        batch_op.add_column(sa.Column("price_source", sa.Text()))
        batch_op.create_check_constraint(
            "ck_ai_models_cache_write_price",
            "cache_write_price_per_million IS NULL OR cache_write_price_per_million >= 0",
        )

    op.create_table(
        "ai_provider_price_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_record_id", sa.Text()),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("input_price_per_million", sa.Numeric(24, 12)),
        sa.Column("output_price_per_million", sa.Numeric(24, 12)),
        sa.Column("cached_input_price_per_million", sa.Numeric(24, 12)),
        sa.Column("cache_write_price_per_million", sa.Numeric(24, 12)),
        sa.Column("currency", sa.Text()),
        sa.Column("effective_at", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_ai_provider_prices_provider",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_record_id"],
            ["ai_models.id"],
            name="fk_ai_provider_prices_model",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "model_id",
            "effective_at",
            name="uq_ai_provider_prices_version",
        ),
        sa.CheckConstraint(
            "input_price_per_million IS NULL OR input_price_per_million >= 0",
            name="ck_ai_provider_prices_input",
        ),
        sa.CheckConstraint(
            "output_price_per_million IS NULL OR output_price_per_million >= 0",
            name="ck_ai_provider_prices_output",
        ),
        sa.CheckConstraint(
            "cached_input_price_per_million IS NULL OR cached_input_price_per_million >= 0",
            name="ck_ai_provider_prices_cached_input",
        ),
        sa.CheckConstraint(
            "cache_write_price_per_million IS NULL OR cache_write_price_per_million >= 0",
            name="ck_ai_provider_prices_cache_write",
        ),
    )
    op.create_index(
        "idx_ai_provider_prices_lookup",
        "ai_provider_price_versions",
        ["provider_id", "model_id", "effective_at"],
    )

    with op.batch_alter_table("ai_model_invocations", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("vendor", sa.Text()))
        batch_op.add_column(sa.Column("provider_instance_id", sa.Text()))
        batch_op.add_column(sa.Column("billing_profile_id", sa.Text()))
        batch_op.add_column(sa.Column("billing_mode", sa.Text()))
        batch_op.add_column(sa.Column("price_source", sa.Text()))
        batch_op.add_column(sa.Column("cache_write_tokens", sa.Integer()))
        batch_op.add_column(sa.Column("estimated_cost_kind", sa.Text()))
        batch_op.create_foreign_key(
            "fk_ai_invocations_billing_profile",
            "ai_billing_profiles",
            ["billing_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_ai_invocations_billing_mode",
            f"billing_mode IS NULL OR {_in_check('billing_mode', BILLING_MODES)}",
        )
        batch_op.create_check_constraint(
            "ck_ai_invocations_cache_write_tokens",
            "cache_write_tokens IS NULL OR cache_write_tokens >= 0",
        )

    # Existing provider rows are not assigned a price.  Known names are
    # classified for reporting only; all unknown/custom instances stay
    # unknown and therefore cannot accidentally claim a zero cost.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE ai_providers SET vendor = 'DeepSeek', billing_mode = 'pay_as_you_go' "
            "WHERE lower(name) LIKE '%deepseek%'"
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO ai_billing_profiles (
                id, name, vendor, billing_mode, package_name,
                concurrency_limit, created_at, updated_at
            ) VALUES
                ('billing-minimax-subscription', 'MiniMax 年度套餐', 'MiniMax',
                 'subscription_fixed', '年度套餐', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('billing-glm-subscription', 'GLM 年度套餐', 'GLM',
                 'subscription_fixed', '年度套餐', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE ai_providers
            SET billing_profile_id = 'billing-minimax-subscription'
            WHERE vendor = 'MiniMax' AND billing_mode = 'subscription_fixed'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE ai_providers
            SET billing_profile_id = 'billing-glm-subscription'
            WHERE vendor = 'GLM' AND billing_mode = 'subscription_fixed'
            """
        )
    )
    connection.execute(
        sa.text(
            "UPDATE ai_providers SET vendor = 'GLM', billing_mode = 'subscription_fixed' "
            "WHERE lower(name) LIKE '%glm%'"
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE ai_providers
            SET vendor = 'MiniMax', billing_mode = 'subscription_fixed'
            WHERE id IN (
                SELECT DISTINCT provider_id FROM ai_models
                WHERE lower(model_id) LIKE '%minimax%'
            )
            """
        )
    )
    connection.execute(
        sa.text(
            "UPDATE ai_providers SET billing_profile_id = 'billing-minimax-subscription' "
            "WHERE vendor = 'MiniMax' AND billing_mode = 'subscription_fixed'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE ai_providers SET billing_profile_id = 'billing-glm-subscription' "
            "WHERE vendor = 'GLM' AND billing_mode = 'subscription_fixed'"
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE ai_model_invocations
            SET vendor = (SELECT vendor FROM ai_providers p WHERE p.id = ai_model_invocations.provider_id),
                provider_instance_id = provider_id,
                billing_profile_id = (SELECT billing_profile_id FROM ai_providers p WHERE p.id = ai_model_invocations.provider_id),
                billing_mode = (SELECT billing_mode FROM ai_providers p WHERE p.id = ai_model_invocations.provider_id),
                estimated_cost_kind = CASE
                    WHEN (SELECT billing_mode FROM ai_providers p WHERE p.id = ai_model_invocations.provider_id) = 'subscription_fixed'
                        THEN 'not_applicable'
                    WHEN estimated_cost IS NULL THEN 'unavailable'
                    ELSE 'estimated'
                END
            """
        )
    )

    op.create_table(
        "research_coverage_plans",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("target_platform_count", sa.Integer(), nullable=False),
        sa.Column("target_entity_count", sa.Integer(), nullable=False),
        sa.Column("target_negative_evidence_count", sa.Integer(), nullable=False),
        sa.Column("max_single_entity_evidence_ratio", sa.Float(), nullable=False),
        sa.Column("target_independent_evidence_count", sa.Integer(), nullable=False),
        sa.Column("target_new_content_count", sa.Integer(), nullable=False),
        sa.Column("low_marginal_value_threshold", sa.Float(), nullable=False),
        sa.Column("low_marginal_round_limit", sa.Integer(), nullable=False),
        sa.Column("stop_reason", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_coverage_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_task_id", name="uq_research_coverage_task"),
        sa.CheckConstraint("target_platform_count >= 0", name="ck_coverage_platforms"),
        sa.CheckConstraint("target_entity_count >= 0", name="ck_coverage_entities"),
        sa.CheckConstraint(
            "target_negative_evidence_count >= 0",
            name="ck_coverage_negative",
        ),
        sa.CheckConstraint(
            "max_single_entity_evidence_ratio BETWEEN 0 AND 1",
            name="ck_coverage_ratio",
        ),
        sa.CheckConstraint(
            "target_independent_evidence_count >= 0",
            name="ck_coverage_independent",
        ),
        sa.CheckConstraint("target_new_content_count >= 0", name="ck_coverage_new_content"),
        sa.CheckConstraint(
            "low_marginal_value_threshold BETWEEN 0 AND 1",
            name="ck_coverage_marginal_threshold",
        ),
        sa.CheckConstraint(
            "low_marginal_round_limit BETWEEN 1 AND 10",
            name="ck_coverage_marginal_rounds",
        ),
    )
    op.create_index(
        "idx_research_coverage_task_updated",
        "research_coverage_plans",
        ["research_task_id", "updated_at"],
    )

    op.create_table(
        "research_platform_coverage",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("planned_query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("independent_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_platform_coverage_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "research_task_id",
            "platform",
            name="uq_research_platform_coverage_task_platform",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'executing', 'completed', 'skipped', 'failed', 'deferred')",
            name="ck_research_platform_coverage_status",
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_research_platform_coverage_order"),
    )
    op.create_index(
        "idx_research_platform_coverage_task_order",
        "research_platform_coverage",
        ["research_task_id", "order_index"],
    )

    op.create_table(
        "research_entity_coverage",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_new_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_platform_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platforms_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("entity_coverage_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("saturated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_entity_coverage_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "research_task_id",
            "canonical_name",
            name="uq_research_entity_coverage_task_name",
        ),
        sa.CheckConstraint("entity_coverage_ratio BETWEEN 0 AND 1", name="ck_entity_coverage_ratio"),
        sa.CheckConstraint("saturated IN (0, 1)", name="ck_entity_coverage_saturated"),
    )
    op.create_index(
        "idx_research_entity_coverage_task_ratio",
        "research_entity_coverage",
        ["research_task_id", "entity_coverage_ratio"],
    )

    op.create_table(
        "research_query_metrics",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_query_id", sa.Text(), nullable=False),
        sa.Column("new_content_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_independent_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model_token_cost", sa.Numeric(24, 12)),
        sa.Column("payg_cost", sa.Numeric(24, 12)),
        sa.Column("crawl_duration_ms", sa.Integer()),
        sa.Column("collected_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adopted_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_adopted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("marginal_value_score", sa.Float()),
        sa.Column("measured_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_query_id"],
            ["research_queries.id"],
            name="fk_research_query_metrics_query",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_query_id", name="uq_research_query_metrics_query"),
        sa.CheckConstraint("new_content_rate BETWEEN 0 AND 1", name="ck_query_metrics_new_rate"),
        sa.CheckConstraint("duplicate_rate BETWEEN 0 AND 1", name="ck_query_metrics_duplicate_rate"),
        sa.CheckConstraint(
            "marginal_value_score IS NULL OR marginal_value_score BETWEEN 0 AND 1",
            name="ck_query_metrics_marginal",
        ),
    )
    op.create_index(
        "idx_research_query_metrics_measured",
        "research_query_metrics",
        ["research_query_id", "measured_at"],
    )

    op.create_table(
        "research_content_decisions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("research_query_id", sa.Text()),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("not_adopted_reason", sa.Text()),
        sa.Column("source_independence", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("content_completeness", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("evidence_quality", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("is_repost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repost_of_content_id", sa.Text()),
        sa.Column("similarity_score", sa.Float()),
        sa.Column("normalized_title_hash", sa.Text()),
        sa.Column("body_summary_hash", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_content_decisions_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_research_content_decisions_content",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["research_query_id"],
            ["research_queries.id"],
            name="fk_research_content_decisions_query",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "research_task_id",
            "content_id",
            name="uq_research_content_decisions_task_content",
        ),
        sa.CheckConstraint(
            "decision IN ('collected', 'candidate', 'adopted', 'not_adopted')",
            name="ck_research_content_decisions_decision",
        ),
        sa.CheckConstraint(
            "source_independence IN ('independent', 'repost', 'unknown')",
            name="ck_research_content_decisions_independence",
        ),
        sa.CheckConstraint(
            "content_completeness IN ('complete', 'partial', 'missing', 'unknown')",
            name="ck_research_content_decisions_completeness",
        ),
        sa.CheckConstraint(
            "evidence_quality IN ('high', 'medium', 'low', 'unknown')",
            name="ck_research_content_decisions_quality",
        ),
        sa.CheckConstraint("is_repost IN (0, 1)", name="ck_research_content_decisions_repost"),
        sa.CheckConstraint(
            "similarity_score IS NULL OR similarity_score BETWEEN 0 AND 1",
            name="ck_research_content_decisions_similarity",
        ),
    )
    op.create_index(
        "idx_research_content_decisions_task_decision",
        "research_content_decisions",
        ["research_task_id", "decision"],
    )

    op.create_table(
        "research_budget_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(24, 12)),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("provider_instance_id", sa.Text()),
        sa.Column("vendor", sa.Text()),
        sa.Column("billing_mode", sa.Text()),
        sa.Column("currency", sa.Text()),
        sa.Column("estimated_cost", sa.Numeric(24, 12)),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_budget_events_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "billing_mode IS NULL OR " + _in_check("billing_mode", BILLING_MODES),
            name="ck_research_budget_events_mode",
        ),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_research_budget_events_amount"),
        sa.CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_research_budget_events_cost",
        ),
    )
    op.create_index(
        "idx_research_budget_events_task_created",
        "research_budget_events",
        ["research_task_id", "created_at"],
    )

    op.create_table(
        "research_step_usage",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("provider_instance_id", sa.Text()),
        sa.Column("vendor", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("billing_mode", sa.Text()),
        sa.Column("estimated_cost", sa.Numeric(24, 12)),
        sa.Column("currency", sa.Text()),
        sa.Column("price_source", sa.Text()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cached_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("fallback_from_provider_instance_id", sa.Text()),
        sa.Column("fallback_reason", sa.Text()),
        sa.Column("request_correlation_id", sa.Text()),
        sa.Column("invocation_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_step_usage_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "billing_mode IS NULL OR " + _in_check("billing_mode", BILLING_MODES),
            name="ck_research_step_usage_mode",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_research_step_usage_sequence"),
        sa.CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="ck_research_step_usage_input"),
        sa.CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="ck_research_step_usage_output"),
        sa.CheckConstraint("cached_tokens IS NULL OR cached_tokens >= 0", name="ck_research_step_usage_cached"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_research_step_usage_latency"),
    )
    op.create_index(
        "idx_research_step_usage_task_step",
        "research_step_usage",
        ["research_task_id", "step", "sequence"],
    )

    op.create_table(
        "runtime_checkpoints",
        sa.Column("research_task_id", sa.Text(), primary_key=True),
        sa.Column("checkpoint_key", sa.Text(), nullable=False),
        sa.Column("last_completed_step", sa.Text()),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_runtime_checkpoints_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version >= 1", name="ck_runtime_checkpoints_version"),
    )

    with op.batch_alter_table("research_tasks", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("budget_max_total_tokens", sa.Integer(), server_default="50000")
        )
        batch_op.add_column(
            sa.Column("budget_max_crawl_tasks", sa.Integer(), server_default="2")
        )
        batch_op.add_column(
            sa.Column("budget_max_new_contents", sa.Integer(), server_default="100")
        )
        batch_op.add_column(
            sa.Column("budget_max_runtime_seconds", sa.Integer(), server_default="3600")
        )
        batch_op.add_column(sa.Column("budget_max_payg_amount", sa.Numeric(24, 12)))
        batch_op.add_column(sa.Column("budget_currency", sa.Text()))
        batch_op.add_column(sa.Column("budget_max_input_tokens", sa.Integer()))
        batch_op.add_column(sa.Column("budget_max_output_tokens", sa.Integer()))
        batch_op.add_column(
            sa.Column("budget_max_model_calls", sa.Integer(), server_default="100")
        )
        batch_op.add_column(
            sa.Column("consumed_model_call_count", sa.Integer(), server_default="0")
        )
        batch_op.add_column(
            sa.Column("route_policy", sa.Text(), server_default="balanced")
        )
        batch_op.add_column(sa.Column("stop_reason", sa.Text()))
        batch_op.add_column(sa.Column("last_checkpoint_at", sa.Text()))
        batch_op.create_check_constraint(
            "ck_research_tasks_total_token_budget",
            "budget_max_total_tokens >= 1",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_crawl_task_budget",
            "budget_max_crawl_tasks >= 0",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_new_content_budget",
            "budget_max_new_contents >= 0",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_runtime_budget",
            "budget_max_runtime_seconds >= 1",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_payg_budget",
            "budget_max_payg_amount IS NULL OR budget_max_payg_amount >= 0",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_input_budget",
            "budget_max_input_tokens IS NULL OR budget_max_input_tokens >= 1",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_output_budget",
            "budget_max_output_tokens IS NULL OR budget_max_output_tokens >= 1",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_model_call_budget",
            "budget_max_model_calls IS NULL OR budget_max_model_calls >= 1",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_model_calls",
            "consumed_model_call_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_research_tasks_route_policy",
            "route_policy IN ('prefer_subscription', 'prefer_payg', 'balanced', 'quality_first', 'manual')",
        )

    with op.batch_alter_table("research_queries", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("lifecycle_status", sa.Text(), server_default="generated"))
        batch_op.add_column(sa.Column("unexecuted_reason", sa.Text()))
        batch_op.add_column(sa.Column("expected_evidence_role", sa.Text()))
        batch_op.add_column(sa.Column("entity_diversity_bonus", sa.Float(), server_default="0"))
        batch_op.add_column(sa.Column("platform_diversity_bonus", sa.Float(), server_default="0"))
        batch_op.add_column(sa.Column("negative_evidence_bonus", sa.Float(), server_default="0"))
        batch_op.add_column(sa.Column("estimated_resource_use", sa.Float(), server_default="0"))
        batch_op.drop_constraint("ck_research_queries_status", type_="check")
        batch_op.create_check_constraint(
            "ck_research_queries_status",
            _in_check("status", QUERY_STATUSES),
        )
        batch_op.create_check_constraint(
            "ck_research_queries_lifecycle_status",
            _in_check("lifecycle_status", QUERY_STATUSES),
        )
        batch_op.create_check_constraint(
            "ck_research_queries_priority_bonuses",
            "entity_diversity_bonus BETWEEN 0 AND 1 "
            "AND platform_diversity_bonus BETWEEN 0 AND 1 "
            "AND negative_evidence_bonus BETWEEN 0 AND 1 "
            "AND estimated_resource_use >= 0",
        )
        batch_op.create_check_constraint(
            "ck_research_queries_evidence_role",
            "expected_evidence_role IS NULL OR expected_evidence_role IN ('direct', 'contextual', 'contradictory', 'background')",
        )
    # Preserve the 8C-1 lifecycle history instead of leaving every existing
    # completed/rejected query at the new column's generated default.
    op.execute("UPDATE research_queries SET lifecycle_status = status")

    with op.batch_alter_table("evidence_occurrences", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("source_query_ids", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("source_crawler_task_ids", sa.Text(), nullable=False, server_default="[]")
        )
    op.execute(
        "UPDATE evidence_occurrences SET source_query_ids = json_array(research_query_id) "
        "WHERE research_query_id IS NOT NULL"
    )
    op.execute(
        "UPDATE evidence_occurrences SET source_crawler_task_ids = json_array(crawler_task_id) "
        "WHERE crawler_task_id IS NOT NULL"
    )

    with op.batch_alter_table("finding_contents", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("source_independence", sa.Text(), nullable=False, server_default="unknown")
        )
        batch_op.add_column(
            sa.Column("content_completeness", sa.Text(), nullable=False, server_default="unknown")
        )
        batch_op.add_column(
            sa.Column("evidence_quality", sa.Text(), nullable=False, server_default="unknown")
        )
        batch_op.create_check_constraint(
            "ck_finding_contents_independence",
            "source_independence IN ('independent', 'repost', 'unknown')",
        )
        batch_op.create_check_constraint(
            "ck_finding_contents_completeness",
            "content_completeness IN ('complete', 'partial', 'missing', 'unknown')",
        )
        batch_op.create_check_constraint(
            "ck_finding_contents_quality",
            "evidence_quality IN ('high', 'medium', 'low', 'unknown')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    configured_ai = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM ai_providers) "
            "OR EXISTS(SELECT 1 FROM ai_model_invocations)"
        )
    ).scalar()
    if configured_ai:
        # Preserve the established 0010 safety boundary when a user asks
        # Alembic to travel past the AI gateway migration.
        raise RuntimeError(
            "refusing to discard configured AI providers or invocation history"
        )
    remaining_platform_rows = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM crawler_tasks "
            "WHERE platform IN ('zhihu', 'wb', 'tieba', 'ks')"
        )
    ).scalar_one()
    if remaining_platform_rows:
        # Preserve the established 0003 safety boundary.  This check runs
        # before the new Phase 8C guard because Alembic may continue to an
        # older revision in the same downgrade command.
        raise RuntimeError(
            "cannot downgrade while crawler_tasks contains remaining-platform rows"
        )
    non_bilibili = connection.execute(
        sa.text("SELECT COUNT(*) FROM crawler_tasks WHERE platform != 'bili'")
    ).scalar_one()
    if non_bilibili:
        raise RuntimeError(
            "cannot downgrade while crawler_tasks contains non-Bilibili rows"
        )
    populated = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM research_coverage_plans) "
            "OR EXISTS(SELECT 1 FROM research_platform_coverage) "
            "OR EXISTS(SELECT 1 FROM research_entity_coverage) "
            "OR EXISTS(SELECT 1 FROM research_query_metrics) "
            "OR EXISTS(SELECT 1 FROM research_content_decisions) "
            "OR EXISTS(SELECT 1 FROM research_budget_events) "
            "OR EXISTS(SELECT 1 FROM research_step_usage) "
            "OR EXISTS(SELECT 1 FROM runtime_checkpoints) "
            "OR EXISTS(SELECT 1 FROM ai_billing_profiles) "
            "OR EXISTS(SELECT 1 FROM ai_provider_price_versions)"
        )
    ).scalar()
    if populated:
        raise RuntimeError(
            "refusing to discard Phase 8C coverage, runtime, or billing history"
        )

    with op.batch_alter_table("finding_contents", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_finding_contents_quality", type_="check")
        batch_op.drop_constraint("ck_finding_contents_completeness", type_="check")
        batch_op.drop_constraint("ck_finding_contents_independence", type_="check")
        batch_op.drop_column("evidence_quality")
        batch_op.drop_column("content_completeness")
        batch_op.drop_column("source_independence")

    with op.batch_alter_table("research_tasks", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_research_tasks_payg_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_runtime_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_new_content_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_crawl_task_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_total_token_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_route_policy", type_="check")
        batch_op.drop_constraint("ck_research_tasks_model_calls", type_="check")
        batch_op.drop_constraint("ck_research_tasks_model_call_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_output_budget", type_="check")
        batch_op.drop_constraint("ck_research_tasks_input_budget", type_="check")
        batch_op.drop_column("last_checkpoint_at")
        batch_op.drop_column("stop_reason")
        batch_op.drop_column("route_policy")
        batch_op.drop_column("consumed_model_call_count")
        batch_op.drop_column("budget_max_model_calls")
        batch_op.drop_column("budget_max_output_tokens")
        batch_op.drop_column("budget_max_input_tokens")
        batch_op.drop_column("budget_currency")
        batch_op.drop_column("budget_max_payg_amount")
        batch_op.drop_column("budget_max_runtime_seconds")
        batch_op.drop_column("budget_max_new_contents")
        batch_op.drop_column("budget_max_crawl_tasks")
        batch_op.drop_column("budget_max_total_tokens")

    with op.batch_alter_table("research_queries", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_research_queries_priority_bonuses", type_="check")
        batch_op.drop_constraint("ck_research_queries_evidence_role", type_="check")
        batch_op.drop_constraint("ck_research_queries_lifecycle_status", type_="check")
        batch_op.drop_constraint("ck_research_queries_status", type_="check")
        batch_op.drop_column("estimated_resource_use")
        batch_op.drop_column("negative_evidence_bonus")
        batch_op.drop_column("platform_diversity_bonus")
        batch_op.drop_column("entity_diversity_bonus")
        batch_op.drop_column("expected_evidence_role")
        batch_op.drop_column("unexecuted_reason")
        batch_op.drop_column("lifecycle_status")
        batch_op.create_check_constraint(
            "ck_research_queries_status",
            _in_check(
                "status",
                ("candidate", "approved", "rejected", "running", "completed", "failed"),
            ),
        )

    with op.batch_alter_table("evidence_occurrences", recreate="always") as batch_op:
        batch_op.drop_column("source_crawler_task_ids")
        batch_op.drop_column("source_query_ids")

    op.drop_table("runtime_checkpoints")
    op.drop_index("idx_research_step_usage_task_step", table_name="research_step_usage")
    op.drop_table("research_step_usage")
    op.drop_index(
        "idx_research_budget_events_task_created",
        table_name="research_budget_events",
    )
    op.drop_table("research_budget_events")
    op.drop_index(
        "idx_research_content_decisions_task_decision",
        table_name="research_content_decisions",
    )
    op.drop_table("research_content_decisions")
    op.drop_index("idx_research_query_metrics_measured", table_name="research_query_metrics")
    op.drop_table("research_query_metrics")
    op.drop_index(
        "idx_research_entity_coverage_task_ratio",
        table_name="research_entity_coverage",
    )
    op.drop_table("research_entity_coverage")
    op.drop_index(
        "idx_research_platform_coverage_task_order",
        table_name="research_platform_coverage",
    )
    op.drop_table("research_platform_coverage")
    op.drop_index(
        "idx_research_coverage_task_updated",
        table_name="research_coverage_plans",
    )
    op.drop_table("research_coverage_plans")

    with op.batch_alter_table("ai_model_invocations", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_ai_invocations_cache_write_tokens", type_="check")
        batch_op.drop_constraint("ck_ai_invocations_billing_mode", type_="check")
        batch_op.drop_constraint("fk_ai_invocations_billing_profile", type_="foreignkey")
        batch_op.drop_column("estimated_cost_kind")
        batch_op.drop_column("cache_write_tokens")
        batch_op.drop_column("price_source")
        batch_op.drop_column("billing_mode")
        batch_op.drop_column("billing_profile_id")
        batch_op.drop_column("provider_instance_id")
        batch_op.drop_column("vendor")

    op.drop_index("idx_ai_provider_prices_lookup", table_name="ai_provider_price_versions")
    op.drop_table("ai_provider_price_versions")

    with op.batch_alter_table("ai_models", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_ai_models_cache_write_price", type_="check")
        batch_op.drop_column("price_source")
        batch_op.drop_column("cache_write_price_per_million")

    op.drop_index("idx_ai_providers_vendor_billing", table_name="ai_providers")
    with op.batch_alter_table("ai_providers", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_ai_providers_tool_status", type_="check")
        batch_op.drop_constraint("ck_ai_providers_billing_mode", type_="check")
        batch_op.drop_constraint("fk_ai_providers_billing_profile", type_="foreignkey")
        batch_op.drop_column("tool_capability_tested_at")
        batch_op.drop_column("tool_capability_status")
        batch_op.drop_column("relay_metadata")
        batch_op.drop_column("billing_profile_id")
        batch_op.drop_column("billing_mode")
        batch_op.drop_column("instance_label")
        batch_op.drop_column("vendor")

    op.drop_table("ai_billing_profiles")
