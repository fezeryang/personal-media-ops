"""Add tags, one favorite flag, and ordered topic collections."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_library_organization"
down_revision: str | Sequence[str] | None = "0007_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "library_contents",
        sa.Column(
            "is_favorite",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "idx_library_contents_favorite",
        "library_contents",
        ["is_favorite", "last_collected_at"],
    )

    op.create_table(
        "library_tags",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(collation="NOCASE"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_library_tags_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_library_tags_user_name",
        ),
    )

    op.create_table(
        "library_content_tags",
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("tag_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_library_content_tags_content",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["library_tags.id"],
            name="fk_library_content_tags_tag",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "tag_id",
            name="pk_library_content_tags",
        ),
    )
    op.create_index(
        "idx_library_content_tags_tag",
        "library_content_tags",
        ["tag_id", "content_id"],
    )

    op.create_table(
        "library_collections",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(collation="NOCASE"), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_library_collections_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_library_collections_user_name",
        ),
    )

    op.create_table(
        "library_collection_items",
        sa.Column("collection_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["library_collections.id"],
            name="fk_library_collection_items_collection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_library_collection_items_content",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_library_collection_items_position",
        ),
        sa.PrimaryKeyConstraint(
            "collection_id",
            "content_id",
            name="pk_library_collection_items",
        ),
        sa.UniqueConstraint(
            "collection_id",
            "position",
            name="uq_library_collection_items_position",
        ),
    )
    op.create_index(
        "idx_library_collection_items_content",
        "library_collection_items",
        ["content_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    favorite_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM library_contents WHERE is_favorite = 1"
        )
    ).scalar_one()
    related = sum(
        connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one()
        for table in (
            "library_collection_items",
            "library_collections",
            "library_content_tags",
            "library_tags",
        )
    )
    if favorite_count or related:
        raise RuntimeError(
            "cannot downgrade library organization while organization data exists"
        )
    op.drop_index(
        "idx_library_collection_items_content",
        table_name="library_collection_items",
    )
    op.drop_table("library_collection_items")
    op.drop_table("library_collections")
    op.drop_index(
        "idx_library_content_tags_tag",
        table_name="library_content_tags",
    )
    op.drop_table("library_content_tags")
    op.drop_table("library_tags")
    op.drop_index(
        "idx_library_contents_favorite",
        table_name="library_contents",
    )
    op.drop_column("library_contents", "is_favorite")
