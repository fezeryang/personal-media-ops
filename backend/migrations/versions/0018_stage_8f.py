"""Add Stage 8F opportunity, validation, action, and outcome records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_stage_8f"
down_revision: str | Sequence[str] | None = "0017_stage_8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SIGNAL_TYPES = (
    "pain_point", "unmet_need", "workflow_friction", "repeated_complaint",
    "behavior_shift", "new_tool_category", "product_gap", "feature_request",
    "switching_signal", "pricing_friction", "complexity_friction", "trust_issue",
    "content_gap", "knowledge_gap", "emerging_interest",
)
OPPORTUNITY_TYPES = (
    "product_opportunity", "business_opportunity", "content_opportunity", "research_opportunity",
)
OPPORTUNITY_STATUSES = (
    "weak_signal", "evidence_building", "candidate", "review_ready", "validation_ready",
    "accepted", "rejected", "deferred", "validating", "validated", "invalidated",
    "converted_to_action", "archived",
)
READINESS = ("insufficient_evidence", "needs_more_evidence", "review_ready", "validation_ready", "validated")


def _enum(column: str, values: Sequence[str], name: str) -> sa.CheckConstraint:
    choices = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({choices})", name=name)


def _non_empty(value: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length(trim({value})) > 0", name=name)


def upgrade() -> None:
    op.create_table(
        "opportunity_signals",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Text()),
        sa.Column("content_id", sa.Text()),
        sa.Column("finding_id", sa.Text()),
        sa.Column("discovery_candidate_id", sa.Text()),
        sa.Column("monitoring_change_id", sa.Text()),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_platform", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("entity_key", sa.Text()),
        sa.Column("event_key", sa.Text()),
        sa.Column("observed_at", sa.Text()),
        sa.Column("aggregation_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["library_contents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["discovery_candidate_id"], ["research_discovery_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["monitoring_change_id"], ["monitoring_changes.id"], ondelete="SET NULL"),
        _enum("signal_type", SIGNAL_TYPES, "ck_opportunity_signals_type"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_opportunity_signals_status"),
        _non_empty("title", "ck_opportunity_signals_title"),
        _non_empty("summary", "ck_opportunity_signals_summary"),
        _non_empty("source_type", "ck_opportunity_signals_source_type"),
        _non_empty("source_id", "ck_opportunity_signals_source_id"),
        _non_empty("aggregation_key", "ck_opportunity_signals_aggregation_key"),
    )
    op.create_index("idx_opportunity_signals_owner_status", "opportunity_signals", ["owner_id", "status", "updated_at"])
    op.create_index("idx_opportunity_signals_aggregation", "opportunity_signals", ["owner_id", "aggregation_key", "created_at"])

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("opportunity_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("why_attention", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("next_step", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("readiness", sa.Text(), nullable=False, server_default="insufficient_evidence"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("score_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("explanation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("unknowns_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("content_details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("related_research_task_id", sa.Text()),
        sa.Column("related_monitoring_mission_id", sa.Text()),
        sa.Column("related_monitoring_change_id", sa.Text()),
        sa.Column("related_discovery_candidate_id", sa.Text()),
        sa.Column("research_space_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_research_task_id"], ["research_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_monitoring_mission_id"], ["monitoring_missions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_monitoring_change_id"], ["monitoring_changes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_discovery_candidate_id"], ["research_discovery_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["research_space_id"], ["research_spaces.id"], ondelete="SET NULL"),
        _enum("opportunity_type", OPPORTUNITY_TYPES, "ck_opportunities_type"),
        _enum("status", OPPORTUNITY_STATUSES, "ck_opportunities_status"),
        _enum("readiness", READINESS, "ck_opportunities_readiness"),
        sa.CheckConstraint("version >= 1", name="ck_opportunities_version"),
        _non_empty("title", "ck_opportunities_title"),
        _non_empty("description", "ck_opportunities_description"),
        _non_empty("target_user", "ck_opportunities_target_user"),
        _non_empty("problem", "ck_opportunities_problem"),
        _non_empty("why_attention", "ck_opportunities_attention"),
        _non_empty("why_now", "ck_opportunities_now"),
        _non_empty("next_step", "ck_opportunities_next_step"),
    )
    op.create_index("idx_opportunities_owner_status", "opportunities", ["owner_id", "status", "readiness", "updated_at"])

    op.create_table(
        "opportunity_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("readiness_before", sa.Text()),
        sa.Column("readiness_after", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("opportunity_id", "version", name="uq_opportunity_versions_version"),
        sa.CheckConstraint("version >= 1", name="ck_opportunity_versions_version"),
    )
    op.create_index("idx_opportunity_versions_opportunity", "opportunity_versions", ["opportunity_id", "version"])

    op.create_table(
        "opportunity_sources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("signal_id", sa.Text()),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Text()),
        sa.Column("content_id", sa.Text()),
        sa.Column("finding_id", sa.Text()),
        sa.Column("source_role", sa.Text(), nullable=False),
        sa.Column("evidence_kind", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("support_explanation", sa.Text(), nullable=False),
        sa.Column("source_platform", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_title", sa.Text()),
        sa.Column("independent_group", sa.Text()),
        sa.Column("is_repost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["opportunity_signals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_id"], ["library_contents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="SET NULL"),
        sa.CheckConstraint("source_role IN ('core', 'supporting', 'counterevidence', 'background')", name="ck_opportunity_sources_role"),
        sa.CheckConstraint("evidence_kind IN ('direct', 'inference', 'estimate', 'unknown')", name="ck_opportunity_sources_kind"),
        sa.CheckConstraint("is_repost IN (0, 1)", name="ck_opportunity_sources_repost"),
        sa.UniqueConstraint("opportunity_id", "source_type", "source_id", "source_role", name="uq_opportunity_sources_source"),
    )
    op.create_index("idx_opportunity_sources_opportunity_role", "opportunity_sources", ["opportunity_id", "source_role", "created_at"])

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scores_json", sa.Text(), nullable=False),
        sa.Column("explanation_json", sa.Text(), nullable=False),
        sa.Column("readiness", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        _enum("readiness", READINESS, "ck_opportunity_scores_readiness"),
        sa.UniqueConstraint("opportunity_id", "version", name="uq_opportunity_scores_version"),
    )

    op.create_table(
        "opportunity_feedback",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("feedback_type", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("undone_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.CheckConstraint("feedback_type IN ('valuable', 'irrelevant', 'evidence_insufficient', 'already_known', 'defer', 'reject', 'continue_research', 'create_validation_plan', 'add_to_space', 'lower_priority')", name="ck_opportunity_feedback_type"),
    )
    op.create_index("idx_opportunity_feedback_opportunity", "opportunity_feedback", ["opportunity_id", "created_at"])

    op.create_table(
        "validation_plans",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("opportunity_hypothesis", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("problem_hypothesis", sa.Text(), nullable=False),
        sa.Column("value_hypothesis", sa.Text(), nullable=False),
        sa.Column("critical_assumptions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("unknowns_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("validation_questions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("evidence_needed_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cheapest_next_test", sa.Text(), nullable=False),
        sa.Column("success_criteria_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("failure_criteria_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("estimated_effort", sa.Text(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("next_decision", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('draft', 'ready', 'in_progress', 'completed', 'abandoned')", name="ck_validation_plans_status"),
        sa.CheckConstraint("source_version >= 1", name="ck_validation_plans_source_version"),
    )
    op.create_index("idx_validation_plans_owner_status", "validation_plans", ["owner_id", "status", "updated_at"])

    op.create_table(
        "validation_results",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("what_happened", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("user_notes", sa.Text()),
        sa.Column("next_step", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["validation_plans.id"], ondelete="CASCADE"),
        sa.CheckConstraint("outcome IN ('supported', 'partially_supported', 'not_supported', 'inconclusive')", name="ck_validation_results_outcome"),
    )
    op.create_index("idx_validation_results_plan", "validation_results", ["plan_id", "created_at"])

    op.create_table(
        "opportunity_actions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("opportunity_id", sa.Text()),
        sa.Column("validation_plan_id", sa.Text()),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("user_notes", sa.Text()),
        sa.Column("started_at", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validation_plan_id"], ["validation_plans.id"], ondelete="SET NULL"),
        sa.CheckConstraint("action_type IN ('research', 'validate', 'prototype', 'interview', 'compare', 'write', 'review', 'monitor', 'manual_other')", name="ck_opportunity_actions_type"),
        sa.CheckConstraint("status IN ('proposed', 'approved', 'in_progress', 'completed', 'abandoned')", name="ck_opportunity_actions_status"),
        _non_empty("title", "ck_opportunity_actions_title"),
    )
    op.create_index("idx_opportunity_actions_owner_status", "opportunity_actions", ["owner_id", "status", "updated_at"])

    op.create_table(
        "action_outcomes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("action_id", sa.Text(), nullable=False),
        sa.Column("what_happened", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("lesson", sa.Text(), nullable=False),
        sa.Column("next_step", sa.Text(), nullable=False),
        sa.Column("published_url", sa.Text()),
        sa.Column("manual_views", sa.Integer()),
        sa.Column("manual_engagement", sa.Integer()),
        sa.Column("user_observation", sa.Text()),
        sa.Column("memory_update_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_id"], ["opportunity_actions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_action_outcomes_action", "action_outcomes", ["action_id", "created_at"])

    with op.batch_alter_table("research_memory_items", recreate="always") as batch_op:
        batch_op.alter_column("research_task_id", existing_type=sa.Text(), nullable=True)
        batch_op.add_column(sa.Column("source_opportunity_id", sa.Text()))
        batch_op.add_column(sa.Column("source_action_id", sa.Text()))
        batch_op.add_column(sa.Column("source_outcome_id", sa.Text()))
        batch_op.create_foreign_key("fk_research_memory_opportunity", "opportunities", ["source_opportunity_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key("fk_research_memory_action", "opportunity_actions", ["source_action_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key("fk_research_memory_outcome", "action_outcomes", ["source_outcome_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_research_memory_items_opportunity_sources", "research_memory_items", ["source_opportunity_id", "source_action_id", "source_outcome_id", "updated_at"])

    with op.batch_alter_table("research_space_items", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_research_space_items_type", type_="check")
        batch_op.create_check_constraint(
            "ck_research_space_items_type",
            "item_type IN ('research_task', 'discovery_candidate', 'evidence', 'entity', 'event', 'finding', 'unresolved_question', 'memory', 'opportunity', 'validation_plan', 'action', 'outcome')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "opportunity_signals", "opportunities", "opportunity_versions", "opportunity_sources",
        "opportunity_scores", "opportunity_feedback", "validation_plans", "validation_results",
        "opportunity_actions", "action_outcomes",
    ):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("cannot downgrade Stage 8F while opportunity data exists")
    op.drop_index("idx_research_space_items_space_position", table_name="research_space_items")
    with op.batch_alter_table("research_space_items", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_research_space_items_type", type_="check")
        batch_op.create_check_constraint(
            "ck_research_space_items_type",
            "item_type IN ('research_task', 'discovery_candidate', 'evidence', 'entity', 'event', 'finding', 'unresolved_question', 'memory')",
        )
    op.create_index("idx_research_space_items_space_position", "research_space_items", ["space_id", "position", "created_at"])
    op.drop_index("idx_research_memory_items_opportunity_sources", table_name="research_memory_items")
    with op.batch_alter_table("research_memory_items", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_research_memory_opportunity", type_="foreignkey")
        batch_op.drop_constraint("fk_research_memory_action", type_="foreignkey")
        batch_op.drop_constraint("fk_research_memory_outcome", type_="foreignkey")
        batch_op.drop_column("source_outcome_id")
        batch_op.drop_column("source_action_id")
        batch_op.drop_column("source_opportunity_id")
        batch_op.alter_column("research_task_id", existing_type=sa.Text(), nullable=False)
    for table in (
        "action_outcomes", "opportunity_actions", "validation_results", "validation_plans",
        "opportunity_feedback", "opportunity_scores", "opportunity_sources", "opportunity_versions",
        "opportunities", "opportunity_signals",
    ):
        op.drop_table(table)
