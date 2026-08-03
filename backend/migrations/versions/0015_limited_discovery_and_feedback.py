"""Persist bounded discovery runs, candidates, sources, scores, and feedback."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_limited_discovery_and_feedback"
down_revision: str | Sequence[str] | None = "0014_research_intent_and_information_utility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANDIDATE_TYPES = (
    "entity",
    "creator",
    "topic",
    "event",
    "query",
    "pain_point",
    "need",
    "product_opportunity_signal",
    "content_opportunity_signal",
)
CANDIDATE_STATES = (
    "generated",
    "scored",
    "queued",
    "accepted",
    "ignored",
    "deferred",
    "converted_to_research",
    "added_to_space",
    "dismissed_duplicate",
    "expired",
)
FEEDBACK_TYPES = (
    "valuable",
    "irrelevant",
    "already_known",
    "duplicate",
    "follow",
    "mute_topic",
    "deprioritize_similar",
    "needs_more_evidence",
    "converted_to_research",
    "added_to_space",
)
FEEDBACK_SCOPES = ("global", "platform", "research_intent", "research_space", "topic")


def _check(column: str, values: Sequence[str]) -> str:
    encoded = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({encoded})"


def _score_check(column: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} BETWEEN 0 AND 1", name=f"ck_discovery_{column}")


def upgrade() -> None:
    op.create_table(
        "research_discovery_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("run_kind", sa.Text(), nullable=False, server_default="bounded"),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("seed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stop_reason", sa.Text()),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_discovery_runs_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("depth BETWEEN 0 AND 1", name="ck_discovery_runs_depth"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed')",
            name="ck_discovery_runs_status",
        ),
        sa.CheckConstraint("seed_count >= 0", name="ck_discovery_runs_seed_count"),
        sa.CheckConstraint("candidate_count >= 0", name="ck_discovery_runs_candidate_count"),
        sa.CheckConstraint("platform_count >= 0", name="ck_discovery_runs_platform_count"),
    )
    op.create_index(
        "idx_discovery_runs_task_created",
        "research_discovery_runs",
        ["research_task_id", "created_at"],
    )

    op.create_table(
        "research_discovery_seeds",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("seed_type", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("source_finding_id", sa.Text()),
        sa.Column("source_entity_candidate_id", sa.Text()),
        sa.Column("source_event_candidate_id", sa.Text()),
        sa.Column("source_candidate_id", sa.Text()),
        sa.Column("relation_to_intent", sa.Text(), nullable=False),
        sa.Column("novelty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("information_utility", sa.Text(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="eligible"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_discovery_seeds_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_discovery_runs.id"],
            name="fk_discovery_seeds_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_content_id"],
            ["library_contents.id"],
            name="fk_discovery_seeds_content",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_finding_id"],
            ["findings.id"],
            name="fk_discovery_seeds_finding",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_candidate_id"],
            ["research_entity_candidates.id"],
            name="fk_discovery_seeds_entity_candidate",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_candidate_id"],
            ["research_event_candidates.id"],
            name="fk_discovery_seeds_event_candidate",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_seeds_candidate",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            _check(
                "seed_type",
                (
                    "core_evidence",
                    "discovery_seed",
                    "favorite",
                    "accepted_candidate",
                    "space_entity",
                    "confirmed_event",
                    "memory_update",
                ),
            ),
            name="ck_discovery_seeds_type",
        ),
        sa.CheckConstraint("novelty BETWEEN 0 AND 1", name="ck_discovery_seeds_novelty"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_discovery_seeds_confidence"),
        sa.CheckConstraint("depth BETWEEN 0 AND 1", name="ck_discovery_seeds_depth"),
    )
    op.create_index(
        "idx_discovery_seeds_run_created",
        "research_discovery_seeds",
        ["run_id", "created_at"],
    )
    op.create_index(
        "idx_discovery_seeds_task_type",
        "research_discovery_seeds",
        ["research_task_id", "seed_type", "created_at"],
    )

    op.create_table(
        "research_discovery_candidates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("candidate_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("parent_candidate_id", sa.Text()),
        sa.Column("source_seed_id", sa.Text()),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("source_platform", sa.Text()),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("novelty_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_strength_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_independence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cross_platform_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("counterevidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actionability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("feedback_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("noise_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("marketing_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("saturation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("resource_cost_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score_explanation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("independent_source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspected_repost_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.Text(), nullable=False, server_default="generated"),
        sa.Column("suggested_next_action", sa.Text()),
        sa.Column("experimental_status", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_discovery_candidates_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_discovery_candidates_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_discovery_runs.id"],
            name="fk_discovery_candidates_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_candidates_parent",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_seed_id"],
            ["research_discovery_seeds.id"],
            name="fk_discovery_candidates_seed",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_content_id"],
            ["library_contents.id"],
            name="fk_discovery_candidates_content",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_check("candidate_type", CANDIDATE_TYPES), name="ck_discovery_candidates_type"),
        sa.CheckConstraint(_check("state", CANDIDATE_STATES), name="ck_discovery_candidates_state"),
        sa.CheckConstraint("depth BETWEEN 0 AND 1", name="ck_discovery_candidates_depth"),
        sa.CheckConstraint("content_count >= 0", name="ck_discovery_candidates_content_count"),
        sa.CheckConstraint("independent_source_count >= 0", name="ck_discovery_candidates_independent_count"),
        sa.CheckConstraint("platform_count >= 0", name="ck_discovery_candidates_platform_count"),
        sa.CheckConstraint("suspected_repost_count >= 0", name="ck_discovery_candidates_repost_count"),
        *[_score_check(column) for column in (
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
        )],
        sa.UniqueConstraint(
            "owner_id",
            "candidate_type",
            "normalized_key",
            name="uq_discovery_candidates_owner_key",
        ),
    )
    op.create_index(
        "idx_discovery_candidates_owner_state_score",
        "research_discovery_candidates",
        ["owner_id", "state", "final_score", "updated_at"],
    )
    op.create_index(
        "idx_discovery_candidates_task_score",
        "research_discovery_candidates",
        ["research_task_id", "final_score", "updated_at"],
    )

    op.create_table(
        "research_discovery_candidate_sources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("seed_id", sa.Text()),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text()),
        sa.Column("platform", sa.Text()),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_title", sa.Text()),
        sa.Column("source_author", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("is_repost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repost_of_content_id", sa.Text()),
        sa.Column("similarity_score", sa.Float()),
        sa.Column("independent_group", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_candidate_sources_candidate",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seed_id"],
            ["research_discovery_seeds.id"],
            name="fk_discovery_candidate_sources_seed",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_discovery_candidate_sources_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_discovery_candidate_sources_content",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("is_repost IN (0, 1)", name="ck_discovery_candidate_sources_repost"),
        sa.CheckConstraint(
            "similarity_score IS NULL OR similarity_score BETWEEN 0 AND 1",
            name="ck_discovery_candidate_sources_similarity",
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "content_id",
            "source_kind",
            name="uq_discovery_candidate_sources_content",
        ),
    )
    op.create_index(
        "idx_discovery_candidate_sources_candidate",
        "research_discovery_candidate_sources",
        ["candidate_id", "created_at"],
    )

    op.create_table(
        "research_discovery_candidate_scores",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("scoring_version", sa.Text(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("components_json", sa.Text(), nullable=False),
        sa.Column("explanation_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_candidate_scores_candidate",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("final_score BETWEEN 0 AND 1", name="ck_discovery_candidate_scores_total"),
    )
    op.create_index(
        "idx_discovery_candidate_scores_candidate_created",
        "research_discovery_candidate_scores",
        ["candidate_id", "created_at"],
    )

    op.create_table(
        "research_discovery_candidate_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("previous_state", sa.Text()),
        sa.Column("next_state", sa.Text(), nullable=False),
        sa.Column("feedback_type", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("actor_type", sa.Text(), nullable=False, server_default="system"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_candidate_events_candidate",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(_check("next_state", CANDIDATE_STATES), name="ck_discovery_candidate_events_state"),
        sa.CheckConstraint(
            "feedback_type IS NULL OR " + _check("feedback_type", FEEDBACK_TYPES),
            name="ck_discovery_candidate_events_feedback",
        ),
    )
    op.create_index(
        "idx_discovery_candidate_events_candidate_created",
        "research_discovery_candidate_events",
        ["candidate_id", "created_at"],
    )

    op.create_table(
        "research_discovery_feedback",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.Text()),
        sa.Column("target_type", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("target_key", sa.Text(), nullable=False),
        sa.Column("feedback_type", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False, server_default="global"),
        sa.Column("scope_key", sa.Text()),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text()),
        sa.Column("follow_up_task_id", sa.Text()),
        sa.Column("undone_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_discovery_feedback_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_discovery_feedback_candidate",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["follow_up_task_id"],
            ["research_tasks.id"],
            name="fk_discovery_feedback_follow_up_task",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_check("feedback_type", FEEDBACK_TYPES), name="ck_discovery_feedback_type"),
        sa.CheckConstraint(_check("scope", FEEDBACK_SCOPES), name="ck_discovery_feedback_scope"),
        sa.CheckConstraint("weight BETWEEN -1 AND 1", name="ck_discovery_feedback_weight"),
    )
    op.create_index(
        "idx_discovery_feedback_owner_scope",
        "research_discovery_feedback",
        ["owner_id", "scope", "scope_key", "created_at"],
    )
    op.create_index(
        "idx_discovery_feedback_candidate_active",
        "research_discovery_feedback",
        ["candidate_id", "undone_at", "created_at"],
    )

    op.create_table(
        "research_discovery_preference_rules",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("feedback_type", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text()),
        sa.Column("adjustment", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_feedback_id", sa.Text()),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_discovery_preference_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_feedback_id"],
            ["research_discovery_feedback.id"],
            name="fk_discovery_preference_feedback",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_check("feedback_type", FEEDBACK_TYPES), name="ck_discovery_preference_type"),
        sa.CheckConstraint(_check("scope", FEEDBACK_SCOPES), name="ck_discovery_preference_scope"),
        sa.CheckConstraint("adjustment BETWEEN -1 AND 1", name="ck_discovery_preference_adjustment"),
        sa.CheckConstraint("active IN (0, 1)", name="ck_discovery_preference_active"),
    )
    op.create_index(
        "idx_discovery_preference_owner_active",
        "research_discovery_preference_rules",
        ["owner_id", "active", "scope", "scope_key"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "research_discovery_preference_rules",
        "research_discovery_feedback",
        "research_discovery_candidate_events",
        "research_discovery_candidate_scores",
        "research_discovery_candidate_sources",
        "research_discovery_candidates",
        "research_discovery_seeds",
        "research_discovery_runs",
    ):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("cannot downgrade discovery tables while data exists")

    op.drop_index("idx_discovery_preference_owner_active", table_name="research_discovery_preference_rules")
    op.drop_table("research_discovery_preference_rules")
    op.drop_index("idx_discovery_feedback_candidate_active", table_name="research_discovery_feedback")
    op.drop_index("idx_discovery_feedback_owner_scope", table_name="research_discovery_feedback")
    op.drop_table("research_discovery_feedback")
    op.drop_index("idx_discovery_candidate_events_candidate_created", table_name="research_discovery_candidate_events")
    op.drop_table("research_discovery_candidate_events")
    op.drop_index("idx_discovery_candidate_scores_candidate_created", table_name="research_discovery_candidate_scores")
    op.drop_table("research_discovery_candidate_scores")
    op.drop_index("idx_discovery_candidate_sources_candidate", table_name="research_discovery_candidate_sources")
    op.drop_table("research_discovery_candidate_sources")
    op.drop_index("idx_discovery_candidates_task_score", table_name="research_discovery_candidates")
    op.drop_index("idx_discovery_candidates_owner_state_score", table_name="research_discovery_candidates")
    op.drop_table("research_discovery_candidates")
    op.drop_index("idx_discovery_seeds_task_type", table_name="research_discovery_seeds")
    op.drop_index("idx_discovery_seeds_run_created", table_name="research_discovery_seeds")
    op.drop_table("research_discovery_seeds")
    op.drop_index("idx_discovery_runs_task_created", table_name="research_discovery_runs")
    op.drop_table("research_discovery_runs")
