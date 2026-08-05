"""Add Stage 8E AI governance, monitoring missions, changes, and notifications."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_stage_8e"
down_revision: str | Sequence[str] | None = "0016_research_spaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _non_empty(value: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length(trim({value})) > 0", name=name)


def upgrade() -> None:
    for column in (
        sa.Column("parent_goal", sa.Text()),
        sa.Column("parent_unknown", sa.Text()),
        sa.Column("scope_distance", sa.Float()),
    ):
        op.add_column("research_queries", column)

    for column in (
        sa.Column("prompt_key", sa.Text()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column("context_version", sa.Text()),
        sa.Column("tool_contract_version", sa.Text()),
    ):
        op.add_column("ai_model_invocations", column)

    op.create_table(
        "prompt_definitions",
        sa.Column("prompt_key", sa.Text(), primary_key=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("active_version", sa.Text(), nullable=False),
        sa.Column("candidate_version", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        _non_empty("role", "ck_prompt_definitions_role"),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("model_family", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("task_template", sa.Text(), nullable=False),
        sa.Column("input_schema_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("output_schema_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("temperature", sa.Float()),
        sa.Column("max_tokens", sa.Integer()),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_key"], ["prompt_definitions.prompt_key"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('draft', 'candidate', 'active', 'deprecated', 'rollback')", name="ck_prompt_versions_status"),
        sa.UniqueConstraint("prompt_key", "version", name="uq_prompt_versions_key_version"),
    )
    op.create_index("idx_prompt_versions_key_status", "prompt_versions", ["prompt_key", "status", "created_at"])

    op.create_table(
        "ai_eval_cases",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("expected_intent", sa.Text(), nullable=False),
        sa.Column("key_unknowns_json", sa.Text(), nullable=False),
        sa.Column("required_evidence_types_json", sa.Text(), nullable=False),
        sa.Column("forbidden_scope_drift_json", sa.Text(), nullable=False),
        sa.Column("minimum_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_completion_allowed", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("minimum_sources >= 0", name="ck_ai_eval_cases_sources"),
        sa.CheckConstraint("partial_completion_allowed IN (0, 1)", name="ck_ai_eval_cases_partial"),
    )
    op.create_table(
        "ai_eval_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("context_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("recorded_task_id", sa.Text()),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_ai_eval_runs_status"),
    )
    op.create_table(
        "ai_eval_results",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("model_calls", sa.Integer()),
        sa.Column("runtime_ms", sa.Integer()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["ai_eval_cases.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('passed', 'failed', 'partial', 'not_instrumented')", name="ck_ai_eval_results_status"),
        sa.UniqueConstraint("run_id", "case_id", name="uq_ai_eval_results_case"),
    )
    op.create_index("idx_ai_eval_results_run", "ai_eval_results", ["run_id", "created_at"])

    op.create_table(
        "monitoring_missions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("mission_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("schedule_type", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("schedule_config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("next_run_at", sa.Text()),
        sa.Column("last_run_at", sa.Text()),
        sa.Column("last_run_status", sa.Text()),
        sa.Column("importance_rule", sa.Text()),
        sa.Column("ignored_content_rule", sa.Text()),
        sa.Column("platforms_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("budget_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("understanding_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused', 'running', 'waiting_platform', 'waiting_login', 'completed_run', 'degraded', 'failed', 'archived')", name="ck_monitoring_missions_status"),
        sa.CheckConstraint("schedule_type IN ('manual', 'daily', 'weekly', 'custom')", name="ck_monitoring_missions_schedule"),
        sa.CheckConstraint("mission_type IN ('topic', 'entity', 'creator', 'event', 'research_question', 'query')", name="ck_monitoring_missions_type"),
        _non_empty("goal", "ck_monitoring_missions_goal"),
    )
    op.create_index("idx_monitoring_missions_owner_status_next", "monitoring_missions", ["owner_id", "status", "next_run_at"])

    op.create_table(
        "monitoring_targets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_value", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("mission_id", "target_type", "normalized_key", name="uq_monitoring_targets_key"),
        _non_empty("target_value", "ck_monitoring_targets_value"),
    )

    op.create_table(
        "monitoring_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("research_task_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.Column("baseline_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notification_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resource_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("backoff_until", sa.Text()),
        sa.Column("claimed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('queued', 'running', 'waiting_platform', 'waiting_login', 'completed', 'no_meaningful_change', 'degraded', 'failed', 'cancelled')", name="ck_monitoring_runs_status"),
        sa.CheckConstraint("baseline_created IN (0, 1)", name="ck_monitoring_runs_baseline"),
    )
    op.create_index("idx_monitoring_runs_mission_created", "monitoring_runs", ["mission_id", "created_at"])

    op.create_table(
        "monitoring_run_queries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["monitoring_runs.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "monitoring_baselines",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["monitoring_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("mission_id", "version", name="uq_monitoring_baselines_version"),
    )
    op.create_index("idx_monitoring_baselines_mission_version", "monitoring_baselines", ["mission_id", "version"])

    op.create_table(
        "monitoring_changes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.Text()),
        sa.Column("latest_seen_at", sa.Text()),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("novelty_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_strength_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_independence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cross_platform_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actionability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("persistence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("noise_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attention_level", sa.Text(), nullable=False, server_default="normal_record"),
        sa.Column("state", sa.Text(), nullable=False, server_default="new"),
        sa.Column("explanation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("cooldown_until", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["monitoring_runs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("change_type IN ('new_entity', 'new_event', 'new_feature', 'new_claim', 'new_user_pain_point', 'new_negative_evidence', 'new_positive_evidence', 'updated_fact', 'contradicted_finding', 'reconfirmed_finding', 'source_disappeared', 'no_meaningful_change')", name="ck_monitoring_changes_type"),
        sa.CheckConstraint("attention_level IN ('immediate_attention', 'daily_digest', 'normal_record', 'silent_memory', 'ignored')", name="ck_monitoring_changes_attention"),
        sa.CheckConstraint("state IN ('new', 'read', 'deferred', 'ignored', 'merged')", name="ck_monitoring_changes_state"),
        sa.UniqueConstraint("mission_id", "fingerprint", name="uq_monitoring_changes_fingerprint"),
        *[sa.CheckConstraint(f"{column} BETWEEN 0 AND 1", name=f"ck_monitoring_changes_{column}") for column in ("relevance_score", "novelty_score", "evidence_strength_score", "source_independence_score", "cross_platform_score", "actionability_score", "persistence_score", "noise_risk_score")],
    )
    op.create_index("idx_monitoring_changes_owner_attention", "monitoring_changes", ["mission_id", "attention_level", "state", "updated_at"])

    op.create_table(
        "monitoring_change_sources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("change_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text()),
        sa.Column("platform", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_title", sa.Text()),
        sa.Column("source_author", sa.Text()),
        sa.Column("published_at", sa.Text()),
        sa.Column("is_repost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("independent_group", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["change_id"], ["monitoring_changes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["library_contents.id"], ondelete="SET NULL"),
        sa.CheckConstraint("is_repost IN (0, 1)", name="ck_monitoring_change_sources_repost"),
        sa.UniqueConstraint("change_id", "content_id", name="uq_monitoring_change_sources_content"),
    )

    op.create_table(
        "monitoring_memory_updates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("change_id", sa.Text(), nullable=False),
        sa.Column("memory_key", sa.Text(), nullable=False),
        sa.Column("old_value_json", sa.Text()),
        sa.Column("new_value_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("changed_at", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default="recorded"),
        sa.Column("confirmed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_id"], ["monitoring_changes.id"], ondelete="CASCADE"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_monitoring_memory_confidence"),
        sa.CheckConstraint("confirmation_status IN ('recorded', 'needs_user_confirmation', 'confirmed', 'rejected', 'undone')", name="ck_monitoring_memory_confirmation"),
    )

    op.create_table(
        "monitoring_notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("change_id", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="unread"),
        sa.Column("read_at", sa.Text()),
        sa.Column("deferred_until", sa.Text()),
        sa.Column("ignored_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["monitoring_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_id"], ["monitoring_changes.id"], ondelete="CASCADE"),
        sa.CheckConstraint("level IN ('immediate_attention', 'daily_digest', 'normal_record', 'silent_memory', 'ignored')", name="ck_monitoring_notifications_level"),
        sa.CheckConstraint("status IN ('unread', 'read', 'deferred', 'ignored')", name="ck_monitoring_notifications_status"),
        sa.UniqueConstraint("owner_id", "change_id", name="uq_monitoring_notifications_change"),
    )
    op.create_index("idx_monitoring_notifications_owner_status", "monitoring_notifications", ["owner_id", "status", "created_at"])


def downgrade() -> None:
    connection = op.get_bind()
    protected_tables = (
        "monitoring_notifications",
        "monitoring_memory_updates",
        "monitoring_change_sources",
        "monitoring_changes",
        "monitoring_baselines",
        "monitoring_run_queries",
        "monitoring_runs",
        "monitoring_targets",
        "monitoring_missions",
        "ai_eval_results",
        "ai_eval_runs",
        "ai_eval_cases",
        "prompt_versions",
        "prompt_definitions",
    )
    if any(connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in protected_tables):
        raise RuntimeError("refusing to downgrade Stage 8E while data exists")
    for index, table in (
        ("idx_monitoring_notifications_owner_status", "monitoring_notifications"),
        ("idx_monitoring_changes_owner_attention", "monitoring_changes"),
        ("idx_monitoring_baselines_mission_version", "monitoring_baselines"),
        ("idx_monitoring_runs_mission_created", "monitoring_runs"),
        ("idx_prompt_versions_key_status", "prompt_versions"),
        ("idx_ai_eval_results_run", "ai_eval_results"),
        ("idx_monitoring_missions_owner_status_next", "monitoring_missions"),
    ):
        op.drop_index(index, table_name=table)
    for table in protected_tables:
        op.drop_table(table)
    for column in ("tool_contract_version", "context_version", "prompt_version", "prompt_key"):
        op.drop_column("ai_model_invocations", column)
    for column in ("scope_distance", "parent_unknown", "parent_goal"):
        op.drop_column("research_queries", column)
