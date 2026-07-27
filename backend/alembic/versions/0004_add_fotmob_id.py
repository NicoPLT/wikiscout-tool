"""add fotmob_id to players

Revision ID: 0004_add_fotmob_id
Revises: 0003_add_season_label
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_add_fotmob_id"
down_revision: Union[str, None] = "0003_add_season_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("fotmob_id", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "fotmob_id")
