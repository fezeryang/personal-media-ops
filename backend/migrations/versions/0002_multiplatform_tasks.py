"""Expand crawler task platform constraint to Bilibili, XHS, and Douyin."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_multiplatform_tasks"
down_revision: str | Sequence[str] | None = "0001_legacy_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_COLUMNS = (
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


def _create_tasks_table(platform_constraint: str) -> None:
    op.create_table(
        "crawler_tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("crawler_type", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False),
        sa.Column("login_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column(
            "actual_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
        sa.CheckConstraint(platform_constraint, name="ck_tasks_platform"),
        sa.CheckConstraint("crawler_type = 'search'", name="ck_tasks_type"),
        sa.CheckConstraint("length(trim(keywords)) > 0", name="ck_tasks_keywords"),
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
    )


def _rebuild(platform_constraint: str) -> None:
    columns = ", ".join(TASK_COLUMNS)
    op.drop_index("idx_crawler_tasks_status_created", table_name="crawler_tasks")
    op.rename_table("crawler_tasks", "crawler_tasks_before_platform_migration")
    _create_tasks_table(platform_constraint)
    op.execute(
        f"""
        INSERT INTO crawler_tasks ({columns})
        SELECT {columns}
        FROM crawler_tasks_before_platform_migration
        """
    )
    op.drop_table("crawler_tasks_before_platform_migration")
    op.create_index(
        "idx_crawler_tasks_status_created",
        "crawler_tasks",
        ["status", "created_at"],
    )


def upgrade() -> None:
    _rebuild("platform IN ('bili', 'xhs', 'dy')")


def downgrade() -> None:
    connection = op.get_bind()
    non_bilibili = connection.execute(
        sa.text("SELECT COUNT(*) FROM crawler_tasks WHERE platform != 'bili'")
    ).scalar_one()
    if non_bilibili:
        raise RuntimeError(
            "cannot downgrade while crawler_tasks contains non-Bilibili rows"
        )
    _rebuild("platform = 'bili'")
