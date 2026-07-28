"""Add creator watch, metric history, trends, and deterministic briefs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_metrics_and_intelligence"
down_revision: str | Sequence[str] | None = "0008_library_organization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_CHECK = (
    "platform IN ('bili', 'xhs', 'dy', 'zhihu', 'wb', 'tieba', 'ks')"
)


def _non_negative(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column} IS NULL OR {column} >= 0",
        name=name,
    )


def upgrade() -> None:
    op.create_table(
        "creator_watchlist",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("check_frequency", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.Text()),
        sa.Column("next_check_at", sa.Text()),
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
            name="fk_creator_watchlist_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["library_creators.id"],
            name="fk_creator_watchlist_creator",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_creator_watchlist_platform"),
        sa.CheckConstraint(
            "enabled IN (0, 1)",
            name="ck_creator_watchlist_enabled",
        ),
        sa.CheckConstraint(
            "check_frequency IN ('every_6_hours', 'daily', 'weekly')",
            name="ck_creator_watchlist_frequency",
        ),
        sa.CheckConstraint(
            "requested_count BETWEEN 1 AND 5",
            name="ck_creator_watchlist_requested_count",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_creator_watchlist_failures",
        ),
        sa.UniqueConstraint(
            "user_id",
            "creator_id",
            name="uq_creator_watchlist_user_creator",
        ),
    )
    op.create_index(
        "idx_creator_watchlist_due",
        "creator_watchlist",
        ["enabled", "next_check_at"],
    )

    op.create_table(
        "creator_watch_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("watch_id", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
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
            ["watch_id"],
            ["creator_watchlist.id"],
            name="fk_creator_watch_runs_watch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["crawler_tasks.id"],
            name="fk_creator_watch_runs_task",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_creator_watch_runs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_creator_watch_runs_status",
        ),
        sa.UniqueConstraint(
            "watch_id",
            "scheduled_for",
            name="uq_creator_watch_runs_slot",
        ),
        sa.UniqueConstraint(
            "task_id",
            name="uq_creator_watch_runs_task",
        ),
    )
    op.create_index(
        "idx_creator_watch_runs_watch_created",
        "creator_watch_runs",
        ["watch_id", "created_at"],
    )

    op.create_table(
        "content_metric_snapshots",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("view_count", sa.Integer()),
        sa.Column("like_count", sa.Integer()),
        sa.Column("favorite_count", sa.Integer()),
        sa.Column("comment_count", sa.Integer()),
        sa.Column("share_count", sa.Integer()),
        sa.Column("metrics_hash", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_content_metric_snapshots_content",
            ondelete="CASCADE",
        ),
        _non_negative("view_count", "ck_content_snapshots_view_count"),
        _non_negative("like_count", "ck_content_snapshots_like_count"),
        _non_negative("favorite_count", "ck_content_snapshots_favorite_count"),
        _non_negative("comment_count", "ck_content_snapshots_comment_count"),
        _non_negative("share_count", "ck_content_snapshots_share_count"),
        sa.UniqueConstraint(
            "content_id",
            "captured_at",
            name="uq_content_metric_snapshot_time",
        ),
    )
    op.create_index(
        "idx_content_metric_snapshots_entity_time",
        "content_metric_snapshots",
        ["content_id", "captured_at"],
    )

    op.create_table(
        "creator_metric_snapshots",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("follower_count", sa.Integer()),
        sa.Column("following_count", sa.Integer()),
        sa.Column("content_count", sa.Integer()),
        sa.Column("metrics_hash", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["library_creators.id"],
            name="fk_creator_metric_snapshots_creator",
            ondelete="CASCADE",
        ),
        _non_negative("follower_count", "ck_creator_snapshots_follower_count"),
        _non_negative("following_count", "ck_creator_snapshots_following_count"),
        _non_negative("content_count", "ck_creator_snapshots_content_count"),
        sa.UniqueConstraint(
            "creator_id",
            "captured_at",
            name="uq_creator_metric_snapshot_time",
        ),
    )
    op.create_index(
        "idx_creator_metric_snapshots_entity_time",
        "creator_metric_snapshots",
        ["creator_id", "captured_at"],
    )

    op.create_table(
        "trend_signals",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("window_start", sa.Text(), nullable=False),
        sa.Column("window_end", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("volume_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("cross_platform_score", sa.Float(), nullable=False),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("platforms", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("formula_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100 "
            "AND volume_score BETWEEN 0 AND 100 "
            "AND velocity_score BETWEEN 0 AND 100 "
            "AND cross_platform_score BETWEEN 0 AND 100 "
            "AND engagement_score BETWEEN 0 AND 100",
            name="ck_trend_signal_scores",
        ),
        sa.CheckConstraint(
            "status IN ('detected', 'insufficient_data')",
            name="ck_trend_signal_status",
        ),
        sa.UniqueConstraint(
            "topic",
            "window_start",
            "window_end",
            "formula_version",
            name="uq_trend_signal_window",
        ),
    )
    op.create_index(
        "idx_trend_signals_window_score",
        "trend_signals",
        ["window_end", "score"],
    )

    op.create_table(
        "trend_signal_contents",
        sa.Column("trend_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["trend_id"],
            ["trend_signals.id"],
            name="fk_trend_signal_contents_trend",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_trend_signal_contents_content",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "trend_id",
            "content_id",
            name="pk_trend_signal_contents",
        ),
    )

    op.create_table(
        "briefs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("window_start", sa.Text(), nullable=False),
        sa.Column("window_end", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generator", sa.Text(), nullable=False),
        sa.Column("ai_provider", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_briefs_user",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version >= 1", name="ck_briefs_version"),
        sa.CheckConstraint(
            "generator IN ('deterministic', 'ai_enhanced')",
            name="ck_briefs_generator",
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'superseded', 'failed')",
            name="ck_briefs_status",
        ),
        sa.UniqueConstraint(
            "user_id",
            "window_start",
            "window_end",
            "version",
            name="uq_briefs_window_version",
        ),
    )
    op.create_index(
        "idx_briefs_user_created",
        "briefs",
        ["user_id", "created_at"],
    )

    op.create_table(
        "brief_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("brief_id", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("conclusion_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["briefs.id"],
            name="fk_brief_items_brief",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "conclusion_type IN "
            "('fact', 'calculation', 'rule', 'insufficient_data', 'unknown')",
            name="ck_brief_items_conclusion_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_brief_items_position"),
        sa.UniqueConstraint(
            "brief_id",
            "position",
            name="uq_brief_items_position",
        ),
    )

    op.create_table(
        "brief_item_contents",
        sa.Column("brief_item_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brief_item_id"],
            ["brief_items.id"],
            name="fk_brief_item_contents_item",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_brief_item_contents_content",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "brief_item_id",
            "content_id",
            name="pk_brief_item_contents",
        ),
    )
    op.create_table(
        "brief_item_trends",
        sa.Column("brief_item_id", sa.Text(), nullable=False),
        sa.Column("trend_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brief_item_id"],
            ["brief_items.id"],
            name="fk_brief_item_trends_item",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trend_id"],
            ["trend_signals.id"],
            name="fk_brief_item_trends_trend",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "brief_item_id",
            "trend_id",
            name="pk_brief_item_trends",
        ),
    )

    op.create_table(
        "brief_schedules",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("time_of_day", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.Text()),
        sa.Column("next_run_at", sa.Text()),
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
            name="fk_brief_schedules_user",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "enabled IN (0, 1)",
            name="ck_brief_schedules_enabled",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_brief_schedules_failures",
        ),
        sa.UniqueConstraint("user_id", name="uq_brief_schedules_user"),
    )
    op.create_index(
        "idx_brief_schedules_due",
        "brief_schedules",
        ["enabled", "next_run_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    tables = (
        "brief_schedules",
        "brief_item_trends",
        "brief_item_contents",
        "brief_items",
        "briefs",
        "trend_signal_contents",
        "trend_signals",
        "creator_metric_snapshots",
        "content_metric_snapshots",
        "creator_watch_runs",
        "creator_watchlist",
    )
    for table in tables:
        if connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one():
            raise RuntimeError(
                "cannot downgrade intelligence tables while stage-seven data exists"
            )
    op.drop_index("idx_brief_schedules_due", table_name="brief_schedules")
    op.drop_table("brief_schedules")
    op.drop_table("brief_item_trends")
    op.drop_table("brief_item_contents")
    op.drop_table("brief_items")
    op.drop_index("idx_briefs_user_created", table_name="briefs")
    op.drop_table("briefs")
    op.drop_table("trend_signal_contents")
    op.drop_index(
        "idx_trend_signals_window_score",
        table_name="trend_signals",
    )
    op.drop_table("trend_signals")
    op.drop_index(
        "idx_creator_metric_snapshots_entity_time",
        table_name="creator_metric_snapshots",
    )
    op.drop_table("creator_metric_snapshots")
    op.drop_index(
        "idx_content_metric_snapshots_entity_time",
        table_name="content_metric_snapshots",
    )
    op.drop_table("content_metric_snapshots")
    op.drop_index(
        "idx_creator_watch_runs_watch_created",
        table_name="creator_watch_runs",
    )
    op.drop_table("creator_watch_runs")
    op.drop_index("idx_creator_watchlist_due", table_name="creator_watchlist")
    op.drop_table("creator_watchlist")
