"""add external_ref to player_stats_matches

Revision ID: 0002_add_external_ref
Revises: 0001_initial_schema
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_external_ref"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_stats_matches",
        sa.Column("external_ref", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_player_stats_matches_external_ref", "player_stats_matches", ["external_ref"]
    )


def downgrade() -> None:
    op.drop_index("ix_player_stats_matches_external_ref", table_name="player_stats_matches")
    op.drop_column("player_stats_matches", "external_ref")
