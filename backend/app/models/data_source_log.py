from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class DataSourceLog(Base):
    """Log di ogni esecuzione dei job di aggiornamento, per debug/monitoraggio."""

    __tablename__ = "data_sources_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(50))  # api_football | understat | transfermarkt | sofascore
    status: Mapped[str] = mapped_column(String(20))  # success | error | skipped
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    players_processed: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
