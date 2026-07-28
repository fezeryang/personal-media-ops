"""Add single-owner sessions and scoped API keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_access_control"
down_revision: str | Sequence[str] | None = "0005_library_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(collation="NOCASE"), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.Text()),
        sa.Column("last_login_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "is_active IN (0, 1)",
            name="ck_users_is_active",
        ),
        sa.CheckConstraint(
            "failed_login_count >= 0",
            name="ck_users_failed_login_count",
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("csrf_token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_sessions_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index(
        "idx_sessions_user_active",
        "sessions",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.Text()),
        sa.Column("expires_at", sa.Text()),
        sa.Column("revoked_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_api_keys_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("key_prefix", name="uq_api_keys_prefix"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_hash"),
    )
    op.create_index(
        "idx_api_keys_user_active",
        "api_keys",
        ["user_id", "revoked_at", "expires_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("api_keys", "sessions", "users"):
        if connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one():
            raise RuntimeError(
                "cannot downgrade access control while owner data exists"
            )
    op.drop_index("idx_api_keys_user_active", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("idx_sessions_user_active", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
