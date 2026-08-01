"""Add the durable AI Runtime research task and evidence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_ai_runtime_research"
down_revision: str | Sequence[str] | None = "0010_ai_model_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESEARCH_STATUSES = (
    "Draft",
    "Planning",
    "Researching",
    "WaitingCrawl",
    "WaitingLogin",
    "Summarizing",
    "AwaitingReview",
    "Done",
    "BudgetExceeded",
    "Failed",
    "Cancelled",
)
FINDING_KINDS = ("fact", "inference")
FINDING_STATUSES = ("active", "superseded")


def _in_check(column: str, values: Sequence[str]) -> str:
    encoded = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({encoded})"


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False, server_default="research"),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("platforms", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="Draft"),
        sa.Column("plan", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("context", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result", sa.Text()),
        sa.Column(
            "execution_trace",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "proposed_actions",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("route_snapshot", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("budget_crawl_limit", sa.Integer(), nullable=False),
        sa.Column("budget_content_limit", sa.Integer(), nullable=False),
        sa.Column("budget_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("budget_token_limit", sa.Integer(), nullable=False),
        sa.Column("budget_cost_limit", sa.Numeric(24, 12)),
        sa.Column("budget_cost_currency", sa.Text()),
        sa.Column("budget_cost_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_crawl_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(24, 12)),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.Text()),
        sa.Column("waiting_crawl_task_id", sa.Text()),
        sa.Column("paused", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_research_tasks_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["waiting_crawl_task_id"],
            ["crawler_tasks.id"],
            name="fk_research_tasks_waiting_crawl",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("task_type = 'research'", name="ck_research_tasks_type"),
        sa.CheckConstraint(
            _in_check("status", RESEARCH_STATUSES),
            name="ck_research_tasks_status",
        ),
        sa.CheckConstraint(
            "budget_crawl_limit BETWEEN 0 AND 100",
            name="ck_research_tasks_crawl_budget",
        ),
        sa.CheckConstraint(
            "budget_content_limit BETWEEN 0 AND 10000",
            name="ck_research_tasks_content_budget",
        ),
        sa.CheckConstraint(
            "budget_duration_seconds BETWEEN 1 AND 604800",
            name="ck_research_tasks_duration_budget",
        ),
        sa.CheckConstraint(
            "budget_token_limit BETWEEN 1 AND 10000000",
            name="ck_research_tasks_token_budget",
        ),
        sa.CheckConstraint(
            "budget_cost_limit IS NULL OR budget_cost_limit >= 0",
            name="ck_research_tasks_cost_budget",
        ),
        sa.CheckConstraint(
            "budget_cost_enabled IN (0, 1)",
            name="ck_research_tasks_cost_enabled",
        ),
        sa.CheckConstraint(
            "paused IN (0, 1)",
            name="ck_research_tasks_paused",
        ),
        sa.CheckConstraint(
            "consumed_crawl_count >= 0 AND consumed_content_count >= 0 "
            "AND consumed_duration_seconds >= 0 AND input_tokens >= 0 "
            "AND output_tokens >= 0 AND cached_tokens >= 0",
            name="ck_research_tasks_consumption",
        ),
    )
    op.create_index(
        "idx_research_tasks_user_status_updated",
        "research_tasks",
        ["user_id", "status", "updated_at"],
    )
    op.create_index(
        "idx_research_tasks_waiting_crawl",
        "research_tasks",
        ["waiting_crawl_task_id"],
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("derivation", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_findings_research_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            _in_check("kind", FINDING_KINDS),
            name="ck_findings_kind",
        ),
        sa.CheckConstraint(
            _in_check("status", FINDING_STATUSES),
            name="ck_findings_status",
        ),
        sa.CheckConstraint("round_number >= 0", name="ck_findings_round"),
    )
    op.create_index(
        "idx_findings_task_round",
        "findings",
        ["research_task_id", "round_number", "created_at"],
    )

    op.create_table(
        "finding_contents",
        sa.Column("finding_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("evidence_role", sa.Text(), nullable=False, server_default="supports"),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_finding_contents_finding",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_finding_contents_content",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("finding_id", "content_id"),
        sa.CheckConstraint(
            "evidence_role IN ('supports', 'derived_from')",
            name="ck_finding_contents_role",
        ),
    )
    op.create_index(
        "idx_finding_contents_content",
        "finding_contents",
        ["content_id", "finding_id"],
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_events_research_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "research_task_id",
            "fingerprint",
            name="uq_events_task_fingerprint",
        ),
        sa.CheckConstraint("round_number >= 0", name="ck_events_round"),
    )
    op.create_index(
        "idx_events_task_round",
        "events",
        ["research_task_id", "round_number", "created_at"],
    )

    op.create_table(
        "event_contents",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("evidence_role", sa.Text(), nullable=False, server_default="member"),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_event_contents_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_event_contents_content",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", "content_id"),
        sa.CheckConstraint(
            "evidence_role IN ('member', 'primary')",
            name="ck_event_contents_role",
        ),
    )
    op.create_index(
        "idx_event_contents_content",
        "event_contents",
        ["content_id", "event_id"],
    )

    with op.batch_alter_table("crawler_tasks", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("research_task_id", sa.Text()))
        batch_op.create_foreign_key(
            "fk_crawler_tasks_research_task",
            "research_tasks",
            ["research_task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "idx_crawler_tasks_research_task",
            ["research_task_id"],
        )

    with op.batch_alter_table(
        "ai_model_invocations",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(sa.Column("research_task_id", sa.Text()))
        batch_op.create_foreign_key(
            "fk_ai_invocations_research_task",
            "research_tasks",
            ["research_task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "idx_ai_invocations_research_task",
            ["research_task_id", "started_at"],
        )


def downgrade() -> None:
    connection = op.get_bind()
    existing = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM research_tasks) "
            "OR EXISTS(SELECT 1 FROM findings) "
            "OR EXISTS(SELECT 1 FROM events) "
            "OR EXISTS(SELECT 1 FROM finding_contents) "
            "OR EXISTS(SELECT 1 FROM event_contents) "
            "OR EXISTS(SELECT 1 FROM crawler_tasks WHERE research_task_id IS NOT NULL) "
            "OR EXISTS(SELECT 1 FROM ai_model_invocations "
            "WHERE research_task_id IS NOT NULL)"
        )
    ).scalar()
    if existing:
        raise RuntimeError(
            "refusing to discard AI Runtime tasks, evidence, or invocation links"
        )

    with op.batch_alter_table(
        "ai_model_invocations",
        recreate="always",
    ) as batch_op:
        batch_op.drop_index("idx_ai_invocations_research_task")
        batch_op.drop_constraint("fk_ai_invocations_research_task", type_="foreignkey")
        batch_op.drop_column("research_task_id")

    with op.batch_alter_table("crawler_tasks", recreate="always") as batch_op:
        batch_op.drop_index("idx_crawler_tasks_research_task")
        batch_op.drop_constraint("fk_crawler_tasks_research_task", type_="foreignkey")
        batch_op.drop_column("research_task_id")

    op.drop_index("idx_event_contents_content", table_name="event_contents")
    op.drop_table("event_contents")
    op.drop_index("idx_events_task_round", table_name="events")
    op.drop_table("events")
    op.drop_index("idx_finding_contents_content", table_name="finding_contents")
    op.drop_table("finding_contents")
    op.drop_index("idx_findings_task_round", table_name="findings")
    op.drop_table("findings")
    op.drop_index("idx_research_tasks_waiting_crawl", table_name="research_tasks")
    op.drop_index("idx_research_tasks_user_status_updated", table_name="research_tasks")
    op.drop_table("research_tasks")
