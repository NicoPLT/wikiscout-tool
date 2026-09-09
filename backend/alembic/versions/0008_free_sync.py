"""Persistent scrape checkpoints and cached profile data (no existing data removed)."""
from alembic import op
import sqlalchemy as sa

revision = "0008_free_sync"
down_revision = "0007_add_player_watch_alerts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("players", sa.Column("sync_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("players", sa.Column("sync_status", sa.String(20), nullable=False, server_default="pending"))
    for name, default in (("sync_state", "{}"), ("seasons_data", "[]"), ("transfers_data", "[]")):
        op.add_column("players", sa.Column(name, sa.JSON(), nullable=False, server_default=default))
    op.add_column("player_stats_matches", sa.Column("sofascore_ref", sa.String(50), nullable=True))
    op.create_table(
        "job_leases",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("owner", sa.String(36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("INSERT INTO job_leases (name) VALUES ('nightly_update')")


def downgrade():
    op.drop_table("job_leases")
    op.drop_column("player_stats_matches", "sofascore_ref")
    for name in ("transfers_data", "seasons_data", "sync_state", "sync_status", "sync_attempted_at"):
        op.drop_column("players", name)
