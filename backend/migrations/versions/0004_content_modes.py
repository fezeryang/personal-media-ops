"""Expand crawler tasks from search-only inputs to five explicit modes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_content_modes"
down_revision: str | Sequence[str] | None = "0003_remaining_platforms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_COLUMNS = (
    "id",
    "platform",
    "crawler_type",
    "keywords",
    "login_type",
    "status",
    "requested_count",
    "actual_count",
    "output_dir",
    "log_path",
    "qrcode_path",
    "pid",
    "error_message",
    "created_at",
    "started_at",
    "finished_at",
    "cancel_requested",
)


def _common_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("crawler_type", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text()),
        sa.Column("login_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("actual_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_dir", sa.Text(), nullable=False),
        sa.Column("log_path", sa.Text(), nullable=False),
        sa.Column("qrcode_path", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("finished_at", sa.Text()),
        sa.Column(
            "cancel_requested",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    ]


def _common_constraints() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "platform IN "
            "('bili', 'xhs', 'dy', 'zhihu', 'wb', 'tieba', 'ks')",
            name="ck_tasks_platform",
        ),
        sa.CheckConstraint("login_type = 'qrcode'", name="ck_tasks_login"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'waiting_login', "
            "'succeeded', 'failed', 'cancelled')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "requested_count BETWEEN 1 AND 20",
            name="ck_tasks_requested_count",
        ),
        sa.CheckConstraint("actual_count >= 0", name="ck_tasks_actual_count"),
        sa.CheckConstraint(
            "cancel_requested IN (0, 1)",
            name="ck_tasks_cancel_requested",
        ),
    ]


def _create_content_mode_table() -> None:
    op.create_table(
        "crawler_tasks",
        *_common_columns(),
        sa.Column(
            "target_ids",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "target_urls",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "creator_ids",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "creator_urls",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("parent_content_id", sa.Text()),
        sa.Column("parent_comment_id", sa.Text()),
        sa.Column(
            "requested_comment_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "requested_sub_comment_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        *_common_constraints(),
        sa.CheckConstraint(
            "crawler_type IN "
            "('search', 'detail', 'creator', 'comments', 'sub_comments')",
            name="ck_tasks_type",
        ),
        sa.CheckConstraint(
            "(keywords IS NULL OR length(trim(keywords)) > 0)",
            name="ck_tasks_keywords",
        ),
        sa.CheckConstraint(
            "requested_comment_count BETWEEN 0 AND 10",
            name="ck_tasks_requested_comment_count",
        ),
        sa.CheckConstraint(
            "requested_sub_comment_count BETWEEN 0 AND 5",
            name="ck_tasks_requested_sub_comment_count",
        ),
    )


def _create_legacy_table() -> None:
    op.create_table(
        "crawler_tasks",
        *_common_columns(),
        *_common_constraints(),
        sa.CheckConstraint("crawler_type = 'search'", name="ck_tasks_type"),
        sa.CheckConstraint(
            "length(trim(keywords)) > 0",
            name="ck_tasks_keywords",
        ),
    )


def _recreate_status_index() -> None:
    op.create_index(
        "idx_crawler_tasks_status_created",
        "crawler_tasks",
        ["status", "created_at"],
    )


def upgrade() -> None:
    legacy_columns = ", ".join(LEGACY_COLUMNS)
    op.drop_index("idx_crawler_tasks_status_created", table_name="crawler_tasks")
    op.rename_table("crawler_tasks", "crawler_tasks_before_content_modes")
    _create_content_mode_table()
    op.execute(
        f"""
        INSERT INTO crawler_tasks ({legacy_columns})
        SELECT {legacy_columns}
        FROM crawler_tasks_before_content_modes
        """
    )
    op.drop_table("crawler_tasks_before_content_modes")
    _recreate_status_index()


def downgrade() -> None:
    connection = op.get_bind()
    non_search_rows = connection.execute(
        sa.text("SELECT COUNT(*) FROM crawler_tasks WHERE crawler_type != 'search'")
    ).scalar_one()
    if non_search_rows:
        raise RuntimeError(
            "cannot downgrade content modes while non-search crawler tasks exist"
        )

    legacy_columns = ", ".join(LEGACY_COLUMNS)
    op.drop_index("idx_crawler_tasks_status_created", table_name="crawler_tasks")
    op.rename_table("crawler_tasks", "crawler_tasks_before_content_mode_downgrade")
    _create_legacy_table()
    op.execute(
        f"""
        INSERT INTO crawler_tasks ({legacy_columns})
        SELECT {legacy_columns}
        FROM crawler_tasks_before_content_mode_downgrade
        """
    )
    op.drop_table("crawler_tasks_before_content_mode_downgrade")
    _recreate_status_index()
