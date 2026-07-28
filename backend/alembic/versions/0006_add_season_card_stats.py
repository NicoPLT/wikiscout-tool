"""add starts/yellow_cards/red_cards season stats to players

Revision ID: 0006_add_season_card_stats
Revises: 0005_add_tags
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_add_season_card_stats"
down_revision: Union[str, None] = "0005_add_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("starts_season", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "players",
        sa.Column("yellow_cards_season", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "players",
        sa.Column("red_cards_season", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("players", "red_cards_season")
    op.drop_column("players", "yellow_cards_season")
    op.drop_column("players", "starts_season")
