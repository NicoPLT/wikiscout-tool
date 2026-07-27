from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Player(Base):
    """Anagrafica giocatore + snapshot denormalizzato usato dalla dashboard.

    Le colonne di snapshot (goals_last5, market_value_eur, ecc.) vengono scritte
    dal job notturno (o dal seed di mock in Fase A) a partire dalle tabelle
    di dettaglio player_stats_matches / player_market_value_history, cosi'
    la dashboard fa una sola query semplice senza aggregazioni pesanti.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)

    full_name: Mapped[str] = mapped_column(String(150), index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_team: Mapped[str | None] = mapped_column(String(150), nullable=True)
    league: Mapped[str | None] = mapped_column(String(150), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Mapping id esterni
    transfermarkt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    api_football_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sofascore_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    understat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Solo per il link diretto al profilo Fotmob nella scheda giocatore:
    # nessuna statistica viene letta da Fotmob, quindi non e' mai coinvolto
    # nel job notturno se non per risolvere/aggiornare questo id.
    fotmob_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Il campionato del giocatore rientra tra quelli coperti da Understat (xG/xA)?
    is_xg_covered: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Snapshot denormalizzato per la dashboard ---
    goals_last5: Mapped[int] = mapped_column(Integer, default=0)
    assists_last5: Mapped[int] = mapped_column(Integer, default=0)
    goals_season: Mapped[int] = mapped_column(Integer, default=0)
    assists_season: Mapped[int] = mapped_column(Integer, default=0)
    appearances_season: Mapped[int] = mapped_column(Integer, default=0)
    minutes_season: Mapped[int] = mapped_column(Integer, default=0)
    # Etichetta della stagione a cui si riferiscono goals_season/assists_season/
    # appearances_season/minutes_season (es. "25/26"). Non e' sempre la
    # stagione "in corso": se il giocatore non ha ancora giocato nella
    # stagione corrente (trasferimento recente, stagione appena iniziata,
    # infortunio), questi campi ricadono sull'ultima stagione con dati
    # reali, ed e' importante mostrare allo scout a quale stagione si
    # riferiscono i numeri invece di lasciarlo intuire.
    season_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rating_avg: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    xg_season: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    xa_season: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    market_value_eur: Mapped[int | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_value_change_eur: Mapped[int | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_value_change_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    stats_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_value_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rating_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    stats_matches: Mapped[list["PlayerStatsMatch"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    market_value_history: Mapped[list["PlayerMarketValueHistory"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    watchlist_entries: Mapped[list["Watchlist"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
