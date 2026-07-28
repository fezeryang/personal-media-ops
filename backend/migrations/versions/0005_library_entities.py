"""Create the normalized content library and task provenance tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_library_entities"
down_revision: str | Sequence[str] | None = "0004_content_modes"
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
        "library_contents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("cover_url", sa.Text()),
        sa.Column("author_source_id", sa.Text()),
        sa.Column("author_name", sa.Text()),
        sa.Column("published_at", sa.Text()),
        sa.Column("first_collected_at", sa.Text(), nullable=False),
        sa.Column("last_collected_at", sa.Text(), nullable=False),
        sa.Column("source_keyword", sa.Text()),
        sa.Column("view_count", sa.Integer()),
        sa.Column("like_count", sa.Integer()),
        sa.Column("favorite_count", sa.Integer()),
        sa.Column("comment_count", sa.Integer()),
        sa.Column("share_count", sa.Integer()),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_library_contents_platform"),
        _non_negative("view_count", "ck_library_contents_view_count"),
        _non_negative("like_count", "ck_library_contents_like_count"),
        _non_negative("favorite_count", "ck_library_contents_favorite_count"),
        _non_negative("comment_count", "ck_library_contents_comment_count"),
        _non_negative("share_count", "ck_library_contents_share_count"),
        sa.UniqueConstraint(
            "platform",
            "source_content_id",
            name="uq_library_contents_platform_source",
        ),
    )
    op.create_index(
        "idx_library_contents_published_at",
        "library_contents",
        ["published_at"],
    )
    op.create_index(
        "idx_library_contents_last_collected_at",
        "library_contents",
        ["last_collected_at"],
    )
    op.create_index(
        "idx_library_contents_source_keyword",
        "library_contents",
        ["source_keyword"],
    )

    op.create_table(
        "library_creators",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_creator_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text()),
        sa.Column("profile_url", sa.Text()),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("follower_count", sa.Integer()),
        sa.Column("following_count", sa.Integer()),
        sa.Column("content_count", sa.Integer()),
        sa.Column("first_collected_at", sa.Text(), nullable=False),
        sa.Column("last_collected_at", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_library_creators_platform"),
        _non_negative("follower_count", "ck_library_creators_follower_count"),
        _non_negative("following_count", "ck_library_creators_following_count"),
        _non_negative("content_count", "ck_library_creators_content_count"),
        sa.UniqueConstraint(
            "platform",
            "source_creator_id",
            name="uq_library_creators_platform_source",
        ),
    )
    op.create_index(
        "idx_library_creators_last_collected_at",
        "library_creators",
        ["last_collected_at"],
    )

    op.create_table(
        "library_comments",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_comment_id", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text(), nullable=False),
        sa.Column("parent_comment_id", sa.Text()),
        sa.Column("author_source_id", sa.Text()),
        sa.Column("author_name", sa.Text()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer()),
        sa.Column("reply_count", sa.Integer()),
        sa.Column("published_at", sa.Text()),
        sa.Column("collected_at", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(PLATFORM_CHECK, name="ck_library_comments_platform"),
        _non_negative("like_count", "ck_library_comments_like_count"),
        _non_negative("reply_count", "ck_library_comments_reply_count"),
        sa.UniqueConstraint(
            "platform",
            "source_comment_id",
            name="uq_library_comments_platform_source",
        ),
    )
    op.create_index(
        "idx_library_comments_content",
        "library_comments",
        ["platform", "source_content_id"],
    )
    op.create_index(
        "idx_library_comments_parent",
        "library_comments",
        ["platform", "parent_comment_id"],
    )
    op.create_index(
        "idx_library_comments_published_at",
        "library_comments",
        ["published_at"],
    )

    op.create_table(
        "content_creator_links",
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("first_collected_at", sa.Text(), nullable=False),
        sa.Column("last_collected_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["library_contents.id"],
            name="fk_content_creator_content",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["library_creators.id"],
            name="fk_content_creator_creator",
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "creator_id",
            name="pk_content_creator_links",
        ),
    )
    op.create_index(
        "idx_content_creator_links_creator",
        "content_creator_links",
        ["creator_id"],
    )

    op.create_table(
        "crawl_task_entities",
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["crawler_tasks.id"],
            name="fk_crawl_task_entities_task",
        ),
        sa.CheckConstraint(
            "entity_type IN ('content', 'creator', 'comment')",
            name="ck_crawl_task_entities_type",
        ),
        sa.PrimaryKeyConstraint(
            "task_id",
            "entity_type",
            "entity_id",
            name="pk_crawl_task_entities",
        ),
    )
    op.create_index(
        "idx_crawl_task_entities_entity",
        "crawl_task_entities",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "crawl_task_entities",
        "content_creator_links",
        "library_comments",
        "library_creators",
        "library_contents",
    ):
        row_count = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one()
        if row_count:
            raise RuntimeError(
                "cannot downgrade library entities while collected data exists"
            )

    op.drop_index(
        "idx_crawl_task_entities_entity",
        table_name="crawl_task_entities",
    )
    op.drop_table("crawl_task_entities")
    op.drop_index(
        "idx_content_creator_links_creator",
        table_name="content_creator_links",
    )
    op.drop_table("content_creator_links")
    op.drop_index("idx_library_comments_published_at", table_name="library_comments")
    op.drop_index("idx_library_comments_parent", table_name="library_comments")
    op.drop_index("idx_library_comments_content", table_name="library_comments")
    op.drop_table("library_comments")
    op.drop_index(
        "idx_library_creators_last_collected_at",
        table_name="library_creators",
    )
    op.drop_table("library_creators")
    op.drop_index(
        "idx_library_contents_source_keyword",
        table_name="library_contents",
    )
    op.drop_index(
        "idx_library_contents_last_collected_at",
        table_name="library_contents",
    )
    op.drop_index(
        "idx_library_contents_published_at",
        table_name="library_contents",
    )
    op.drop_table("library_contents")
