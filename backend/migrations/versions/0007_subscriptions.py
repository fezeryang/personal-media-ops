"""Add keyword subscriptions, durable runs, and task ownership."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_subscriptions"
down_revision: str | Sequence[str] | None = "0006_access_control"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_CHECK = (
    "platform IN ('bili', 'xhs', 'dy', 'zhihu', 'wb', 'tieba', 'ks')"
)


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(collation="NOCASE"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schedule_type", sa.Text(), nullable=False),
        sa.Column("schedule_config", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.Text()),
        sa.Column("next_run_at", sa.Text()),
        sa.Column("last_success_at", sa.Text()),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_subscriptions_user",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_subscriptions_enabled"),
        sa.CheckConstraint(
            "schedule_type IN "
            "('manual', 'every_6_hours', 'daily', 'weekdays', 'weekly')",
            name="ck_subscriptions_schedule_type",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_subscriptions_failures",
        ),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_subscriptions_user_name",
        ),
    )
    op.create_index(
        "idx_subscriptions_due",
        "subscriptions",
        ["enabled", "next_run_at"],
    )

    op.create_table(
        "subscription_platforms",
        sa.Column("subscription_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name="fk_subscription_platforms_subscription",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_subscription_platform"),
        sa.CheckConstraint(
            "requested_count BETWEEN 1 AND 20",
            name="ck_subscription_platform_requested_count",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_subscription_platform_position",
        ),
        sa.PrimaryKeyConstraint(
            "subscription_id",
            "platform",
            name="pk_subscription_platforms",
        ),
        sa.UniqueConstraint(
            "subscription_id",
            "position",
            name="uq_subscription_platform_position",
        ),
    )

    op.create_table(
        "subscription_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("subscription_id", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("finished_at", sa.Text()),
        sa.Column(
            "new_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "existing_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "changed_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name="fk_subscription_runs_subscription",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_subscription_runs_trigger",
        ),
        sa.CheckConstraint(
            "status IN "
            "('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled')",
            name="ck_subscription_runs_status",
        ),
        sa.CheckConstraint(
            "new_content_count >= 0 AND existing_content_count >= 0 "
            "AND changed_content_count >= 0",
            name="ck_subscription_runs_counts",
        ),
        sa.UniqueConstraint(
            "subscription_id",
            "scheduled_for",
            name="uq_subscription_runs_slot",
        ),
    )
    op.create_index(
        "idx_subscription_runs_subscription_created",
        "subscription_runs",
        ["subscription_id", "created_at"],
    )
    op.create_index(
        "idx_subscription_runs_status",
        "subscription_runs",
        ["status", "created_at"],
    )

    op.create_table(
        "subscription_run_tasks",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "new_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "existing_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "changed_content_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("error_summary", sa.Text()),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["subscription_runs.id"],
            name="fk_subscription_run_tasks_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["crawler_tasks.id"],
            name="fk_subscription_run_tasks_task",
        ),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_subscription_run_task_platform"),
        sa.CheckConstraint(
            "sequence >= 0",
            name="ck_subscription_run_task_sequence",
        ),
        sa.PrimaryKeyConstraint(
            "run_id",
            "task_id",
            name="pk_subscription_run_tasks",
        ),
        sa.UniqueConstraint(
            "run_id",
            "platform",
            name="uq_subscription_run_task_platform",
        ),
        sa.UniqueConstraint(
            "task_id",
            name="uq_subscription_run_task_owner",
        ),
    )
    op.create_index(
        "idx_subscription_run_tasks_task",
        "subscription_run_tasks",
        ["task_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "subscription_run_tasks",
        "subscription_runs",
        "subscription_platforms",
        "subscriptions",
    ):
        if connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one():
            raise RuntimeError(
                "cannot downgrade subscriptions while subscription data exists"
            )
    op.drop_index(
        "idx_subscription_run_tasks_task",
        table_name="subscription_run_tasks",
    )
    op.drop_table("subscription_run_tasks")
    op.drop_index("idx_subscription_runs_status", table_name="subscription_runs")
    op.drop_index(
        "idx_subscription_runs_subscription_created",
        table_name="subscription_runs",
    )
    op.drop_table("subscription_runs")
    op.drop_table("subscription_platforms")
    op.drop_index("idx_subscriptions_due", table_name="subscriptions")
    op.drop_table("subscriptions")
