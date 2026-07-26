"""Adopt or create the legacy Bilibili crawler task schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_legacy_tasks"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPECTED_COLUMNS = {
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
}


def _columns() -> list[sa.Column[object]]:
    return [
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
    ]


def _legacy_constraints() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint("platform = 'bili'", name="ck_tasks_platform"),
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
    ]


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table("crawler_tasks"):
        columns = {column["name"] for column in inspector.get_columns("crawler_tasks")}
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(
                "existing crawler_tasks schema does not match the legacy baseline"
            )
    else:
        op.create_table(
            "crawler_tasks",
            *_columns(),
            *_legacy_constraints(),
        )

    indexes = {
        index["name"] for index in sa.inspect(connection).get_indexes("crawler_tasks")
    }
    if "idx_crawler_tasks_status_created" not in indexes:
        op.create_index(
            "idx_crawler_tasks_status_created",
            "crawler_tasks",
            ["status", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("idx_crawler_tasks_status_created", table_name="crawler_tasks")
    op.drop_table("crawler_tasks")
