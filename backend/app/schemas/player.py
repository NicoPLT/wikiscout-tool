from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PlayerRow(BaseModel):
    """Riga della tabella principale (stile Excel) della dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    photo_url: str | None
    current_team: str | None
    league: str | None
    position: str | None

    market_value_eur: float | None
    market_value_change_eur: float | None
    market_value_change_pct: float | None

    goals_last5: int
    assists_last5: int
    goals_season: int
    assists_season: int
    appearances_season: int
    minutes_season: int
    # Stagione a cui si riferiscono i campi *_season (es. "25/26"): non e'
    # sempre quella in corso, se il giocatore non ha ancora dati recenti
    # (trasferimento, infortunio, stagione appena iniziata) mostra l'ultima
    # stagione reale disponibile.
    season_label: str | None = None
    rating_avg: float | None

    is_xg_covered: bool
    xg_season: float | None
    xa_season: float | None

    watchlist_notes: str | None = None
    watchlist_tags: list[str] | None = None

    last_synced_at: datetime | None


class MatchStatLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_date: date
    competition: str
    opponent: str | None
    is_home: bool | None
    minutes_played: int
    goals: int
    assists: int
    rating: float | None
    xg: float | None
    xa: float | None


class MarketValuePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recorded_at: date
    value_eur: float


class PlayerDetail(PlayerRow):
    date_of_birth: date | None
    nationality: str | None
    transfermarkt_id: str | None
    api_football_id: str | None
    sofascore_id: str | None

    stats_updated_at: datetime | None
    market_value_updated_at: datetime | None
    rating_updated_at: datetime | None

    recent_matches: list[MatchStatLine]
    market_value_history: list[MarketValuePoint]


class MarketValueTrendPoint(BaseModel):
    recorded_at: date
    total_value_eur: float


class RecentUpdateItem(BaseModel):
    player_id: int
    full_name: str
    photo_url: str | None
    kind: str  # "market_value" | "rating" | "stats"
    label: str
    change_pct: float | None
    at: datetime


class WatchlistSummary(BaseModel):
    players_count: int
    avg_rating: float | None
    total_market_value_eur: float
    market_value_trend: list[MarketValueTrendPoint]
    recent_updates: list[RecentUpdateItem]


class WatchlistAddRequest(BaseModel):
    player_id: int
    notes: str | None = None
    tags: list[str] | None = None


class WatchlistUpdateRequest(BaseModel):
    notes: str | None = None
    tags: list[str] | None = None


class PlayerSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # "local": gia' presente nel nostro DB (id popolato). "transfermarkt": trovato
    # in tempo reale su Transfermarkt ma non ancora importato (id assente,
    # transfermarkt_id popolato) -> il frontend deve chiamare /watchlist/import.
    source: str = "local"
    id: int | None = None
    transfermarkt_id: str | None = None
    full_name: str
    current_team: str | None
    league: str | None
    photo_url: str | None
    in_watchlist: bool = False
    # Presenti solo per source="transfermarkt": Transfermarkt si cerca per
    # NOME, non per id, quindi per importare un candidato il frontend rimanda
    # indietro questi campi cosi' come li ha ricevuti dalla ricerca, invece
    # di far ricercare al backend l'id come se fosse un nome (non funziona).
    position: str | None = None
    nationality: str | None = None
    market_value_eur: float | None = None


class WatchlistImportRequest(BaseModel):
    transfermarkt_id: str
    full_name: str
    current_team: str | None = None
    position: str | None = None
    nationality: str | None = None
    market_value_eur: float | None = None
    photo_url: str | None = None


class SofascoreLinkRequest(BaseModel):
    """Collegamento manuale: URL del profilo Sofascore (o solo l'id numerico)."""

    sofascore_url_or_id: str


class PlayerSeasonOption(BaseModel):
    """Una voce del selettore stagioni nella pagina di dettaglio (sola
    lettura: non modifica la 'stagione corrente' salvata sul giocatore)."""

    season_id: int
    season_label: str
    competition_name: str | None
    appearances: int
    goals: int
    assists: int
    minutes_played: int
