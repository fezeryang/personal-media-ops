"""Add owner-scoped research spaces and typed item links."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_research_spaces"
down_revision: str | Sequence[str] | None = "0015_limited_discovery_and_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ITEM_TYPES = (
    "research_task",
    "discovery_candidate",
    "evidence",
    "entity",
    "event",
    "finding",
    "unresolved_question",
    "memory",
)


def upgrade() -> None:
    op.create_table(
        "research_spaces",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_research_spaces_owner",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_research_spaces_status",
        ),
        sa.UniqueConstraint("owner_id", "name", name="uq_research_spaces_owner_name"),
    )
    op.create_index(
        "idx_research_spaces_owner_status",
        "research_spaces",
        ["owner_id", "status", "updated_at"],
    )

    op.create_table(
        "research_space_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("space_id", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text()),
        sa.Column("source_candidate_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["research_spaces.id"],
            name="fk_research_space_items_space",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_candidate_id"],
            ["research_discovery_candidates.id"],
            name="fk_research_space_items_candidate",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "item_type IN ('research_task', 'discovery_candidate', 'evidence', 'entity', 'event', 'finding', 'unresolved_question', 'memory')",
            name="ck_research_space_items_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_research_space_items_position"),
        sa.UniqueConstraint(
            "space_id",
            "item_type",
            "item_id",
            name="uq_research_space_items_item",
        ),
    )
    op.create_index(
        "idx_research_space_items_space_position",
        "research_space_items",
        ["space_id", "position", "created_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("research_space_items", "research_spaces"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("cannot downgrade research spaces while data exists")
    op.drop_index("idx_research_space_items_space_position", table_name="research_space_items")
    op.drop_table("research_space_items")
    op.drop_index("idx_research_spaces_owner_status", table_name="research_spaces")
    op.drop_table("research_spaces")
