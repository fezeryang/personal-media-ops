"""Add durable research query and evidence quality metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_research_quality_foundation"
down_revision: str | Sequence[str] | None = "0011_ai_runtime_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUERY_TYPES = (
    "product",
    "tool",
    "company",
    "creator",
    "person",
    "event",
    "need",
    "scenario",
    "technology",
    "generic_topic",
)
QUERY_STATUSES = (
    "candidate",
    "approved",
    "rejected",
    "running",
    "completed",
    "failed",
)
SUPPORT_TYPES = ("direct", "contextual", "contradictory", "background")
SUPPORT_STRENGTHS = ("strong", "medium", "weak")
COUNTEREVIDENCE_STATUSES = ("found", "not_found", "unknown")


def _in_check(column: str, values: Sequence[str]) -> str:
    encoded = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({encoded})"


def upgrade() -> None:
    op.create_table(
        "research_queries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("source_finding_id", sa.Text()),
        sa.Column("parent_query_id", sa.Text()),
        sa.Column("generation_reason", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("specificity_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("noise_risk_score", sa.Float(), nullable=False),
        sa.Column("expected_value_score", sa.Float()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("crawler_task_id", sa.Text()),
        sa.Column("executed_at", sa.Text()),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("existing_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_queries_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_content_id"],
            ["library_contents.id"],
            name="fk_research_queries_source_content",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_finding_id"],
            ["findings.id"],
            name="fk_research_queries_source_finding",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_query_id"],
            ["research_queries.id"],
            name="fk_research_queries_parent",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["crawler_task_id"],
            ["crawler_tasks.id"],
            name="fk_research_queries_crawler_task",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_in_check("query_type", QUERY_TYPES), name="ck_research_queries_type"),
        sa.CheckConstraint(_in_check("status", QUERY_STATUSES), name="ck_research_queries_status"),
        sa.CheckConstraint("length(trim(query)) > 0", name="ck_research_queries_query"),
        sa.CheckConstraint("length(trim(normalized_query)) > 0", name="ck_research_queries_normalized"),
        sa.CheckConstraint("length(trim(generation_reason)) > 0", name="ck_research_queries_reason"),
        sa.CheckConstraint("specificity_score BETWEEN 0 AND 1", name="ck_research_queries_specificity"),
        sa.CheckConstraint("novelty_score BETWEEN 0 AND 1", name="ck_research_queries_novelty"),
        sa.CheckConstraint("noise_risk_score BETWEEN 0 AND 1", name="ck_research_queries_noise"),
        sa.CheckConstraint("relevance_score IS NULL OR relevance_score BETWEEN 0 AND 1", name="ck_research_queries_relevance"),
        sa.CheckConstraint("expected_value_score IS NULL OR expected_value_score BETWEEN 0 AND 1", name="ck_research_queries_value"),
        sa.CheckConstraint(
            "result_count >= 0 AND new_content_count >= 0 AND existing_content_count >= 0 "
            "AND updated_content_count >= 0 AND duplicate_evidence_count >= 0",
            name="ck_research_queries_counts",
        ),
    )
    op.create_index(
        "idx_research_queries_task_created",
        "research_queries",
        ["research_task_id", "created_at", "id"],
    )
    op.create_index(
        "idx_research_queries_normalized",
        "research_queries",
        ["normalized_query"],
    )
    op.create_index(
        "idx_research_queries_parent",
        "research_queries",
        ["parent_query_id"],
    )

    op.create_table(
        "evidence_occurrences",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("finding_id", sa.Text()),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("crawler_task_id", sa.Text()),
        sa.Column("research_query_id", sa.Text()),
        sa.Column("first_seen_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_evidence_occurrences_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_evidence_occurrences_finding",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_evidence_occurrences_content",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["crawler_task_id"],
            ["crawler_tasks.id"],
            name="fk_evidence_occurrences_crawler_task",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["research_query_id"],
            ["research_queries.id"],
            name="fk_evidence_occurrences_query",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("occurrence_count >= 1", name="ck_evidence_occurrences_count"),
    )
    op.create_index(
        "idx_evidence_occurrences_task_content",
        "evidence_occurrences",
        ["research_task_id", "content_id"],
    )
    op.create_index(
        "idx_evidence_occurrences_finding",
        "evidence_occurrences",
        ["finding_id", "content_id"],
    )
    op.create_index(
        "idx_evidence_occurrences_query",
        "evidence_occurrences",
        ["research_query_id", "content_id"],
    )

    # Persist the ingestion classification before the Worker notifies the
    # Research runtime.  This keeps restart recovery exact if the process
    # exits after the library transaction commits but before the research
    # task is woken.
    with op.batch_alter_table("crawler_tasks", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "research_new_content_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "research_existing_content_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "research_updated_content_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.create_check_constraint(
            "ck_crawler_tasks_research_content_counts",
            "research_new_content_count >= 0 AND research_existing_content_count >= 0 "
            "AND research_updated_content_count >= 0",
        )

    with op.batch_alter_table("findings", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "counterevidence_status",
                sa.Text(),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(
            sa.Column(
                "counterevidence_explanation",
                sa.Text(),
                nullable=False,
                server_default="历史 Finding 未记录反证状态。",
            )
        )
        batch_op.create_check_constraint(
            "ck_findings_counterevidence_status",
            _in_check("counterevidence_status", COUNTEREVIDENCE_STATUSES),
        )

    with op.batch_alter_table("finding_contents", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "support_type",
                sa.Text(),
                nullable=False,
                server_default="background",
            )
        )
        batch_op.add_column(
            sa.Column(
                "support_strength",
                sa.Text(),
                nullable=False,
                server_default="weak",
            )
        )
        batch_op.add_column(
            sa.Column(
                "support_explanation",
                sa.Text(),
                nullable=False,
                server_default="历史 Finding 未记录证据支持说明。",
            )
        )
        batch_op.create_check_constraint(
            "ck_finding_contents_support_type",
            _in_check("support_type", SUPPORT_TYPES),
        )
        batch_op.create_check_constraint(
            "ck_finding_contents_support_strength",
            _in_check("support_strength", SUPPORT_STRENGTHS),
        )


def downgrade() -> None:
    connection = op.get_bind()
    existing = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM research_queries) "
            "OR EXISTS(SELECT 1 FROM evidence_occurrences)"
        )
    ).scalar()
    if existing:
        raise RuntimeError(
            "refusing to discard research quality queries or evidence occurrences"
        )

    op.drop_table("evidence_occurrences")
    op.drop_table("research_queries")

    with op.batch_alter_table("finding_contents", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_finding_contents_support_strength", type_="check")
        batch_op.drop_constraint("ck_finding_contents_support_type", type_="check")
        batch_op.drop_column("support_explanation")
        batch_op.drop_column("support_strength")
        batch_op.drop_column("support_type")

    with op.batch_alter_table("findings", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_findings_counterevidence_status", type_="check")
        batch_op.drop_column("counterevidence_explanation")
        batch_op.drop_column("counterevidence_status")

    with op.batch_alter_table("crawler_tasks", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_crawler_tasks_research_content_counts", type_="check")
        batch_op.drop_column("research_updated_content_count")
        batch_op.drop_column("research_existing_content_count")
        batch_op.drop_column("research_new_content_count")
