from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PlayerStatsMatch(Base):
    """Statistiche partita per partita, fonte di verita' per la pagina di dettaglio."""

    __tablename__ = "player_stats_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)

    match_date: Mapped[date] = mapped_column(Date, index=True)
    competition: Mapped[str] = mapped_column(String(150))
    opponent: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    xg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    xa: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="seed")
    # id della partita nella fonte esterna (es. fixture id API-Football), usato
    # per evitare di duplicare la riga quando il job notturno rigira sullo stesso match.
    external_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    player: Mapped["Player"] = relationship(back_populates="stats_matches")
