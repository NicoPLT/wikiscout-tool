"""add player_watch_alerts table (One to Watch)

Revision ID: 0007_add_player_watch_alerts
Revises: 0006_add_season_card_stats
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_add_player_watch_alerts"
down_revision: Union[str, None] = "0006_add_season_card_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

watch_alert_trigger_type = sa.Enum(
    "rating_streak",
    "goal_streak",
    "assist_streak",
    "recent_transfer",
    "market_value_spike",
    name="watch_alert_trigger_type",
)


def upgrade() -> None:
    op.create_table(
        "player_watch_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        # Il tipo Enum viene creato automaticamente da create_table (una sola
        # volta) perche' non esiste ancora; per il downgrade va invece
        # eliminato esplicitamente, drop_table non lo fa da solo.
        sa.Column("trigger_type", watch_alert_trigger_type, nullable=True),
        sa.Column("trigger_detail", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_seen", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_player_watch_alerts_player_id", "player_watch_alerts", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_player_watch_alerts_player_id", table_name="player_watch_alerts")
    op.drop_table("player_watch_alerts")
    watch_alert_trigger_type.drop(op.get_bind(), checkfirst=True)
