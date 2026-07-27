"""add tags table and watchlists.tag_id

Revision ID: 0005_add_tags
Revises: 0004_add_fotmob_id
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_tags"
down_revision: Union[str, None] = "0004_add_fotmob_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])

    op.add_column(
        "watchlists",
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watchlists", "tag_id")
    op.drop_index("ix_tags_user_id", table_name="tags")
    op.drop_table("tags")
