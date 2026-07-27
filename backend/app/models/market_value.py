from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PlayerMarketValueHistory(Base):
    """Storico valore di mercato (Transfermarkt), una riga per rilevazione."""

    __tablename__ = "player_market_value_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)

    value_eur: Mapped[float] = mapped_column(Numeric(12, 2))
    recorded_at: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(50), default="seed")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    player: Mapped["Player"] = relationship(back_populates="market_value_history")
