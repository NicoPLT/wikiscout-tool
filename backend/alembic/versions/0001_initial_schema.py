"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column("position", sa.String(length=50), nullable=True),
        sa.Column("current_team", sa.String(length=150), nullable=True),
        sa.Column("league", sa.String(length=150), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("transfermarkt_id", sa.String(length=50), nullable=True),
        sa.Column("api_football_id", sa.String(length=50), nullable=True),
        sa.Column("sofascore_id", sa.String(length=50), nullable=True),
        sa.Column("understat_id", sa.String(length=50), nullable=True),
        sa.Column("is_xg_covered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("goals_last5", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists_last5", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals_season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists_season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("appearances_season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minutes_season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating_avg", sa.Numeric(4, 2), nullable=True),
        sa.Column("xg_season", sa.Numeric(5, 2), nullable=True),
        sa.Column("xa_season", sa.Numeric(5, 2), nullable=True),
        sa.Column("market_value_eur", sa.Numeric(12, 2), nullable=True),
        sa.Column("market_value_change_eur", sa.Numeric(12, 2), nullable=True),
        sa.Column("market_value_change_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("stats_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_value_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rating_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_players_full_name", "players", ["full_name"])

    op.create_table(
        "player_stats_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("competition", sa.String(length=150), nullable=False),
        sa.Column("opponent", sa.String(length=150), nullable=True),
        sa.Column("is_home", sa.Boolean(), nullable=True),
        sa.Column("minutes_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Numeric(4, 2), nullable=True),
        sa.Column("xg", sa.Numeric(5, 2), nullable=True),
        sa.Column("xa", sa.Numeric(5, 2), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_player_stats_matches_player_id", "player_stats_matches", ["player_id"])
    op.create_index("ix_player_stats_matches_match_date", "player_stats_matches", ["match_date"])

    op.create_table(
        "player_market_value_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value_eur", sa.Numeric(12, 2), nullable=False),
        sa.Column("recorded_at", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_player_market_value_history_player_id", "player_market_value_history", ["player_id"]
    )
    op.create_index(
        "ix_player_market_value_history_recorded_at", "player_market_value_history", ["recorded_at"]
    )

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "player_id", name="uq_watchlist_user_player"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])
    op.create_index("ix_watchlists_player_id", "watchlists", ["player_id"])

    op.create_table(
        "data_sources_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("players_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_data_sources_log_job_name", "data_sources_log", ["job_name"])
    op.create_index("ix_data_sources_log_run_at", "data_sources_log", ["run_at"])


def downgrade() -> None:
    op.drop_table("data_sources_log")
    op.drop_table("watchlists")
    op.drop_table("player_market_value_history")
    op.drop_table("player_stats_matches")
    op.drop_index("ix_players_full_name", table_name="players")
    op.drop_table("players")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
