"""add season_label to players

Revision ID: 0003_add_season_label
Revises: 0002_add_external_ref
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_season_label"
down_revision: Union[str, None] = "0002_add_external_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("season_label", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "season_label")
