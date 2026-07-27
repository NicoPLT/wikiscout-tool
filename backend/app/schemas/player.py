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

    # "local": gia' presente nel nostro DB (id popolato). "api_football": trovato
    # in tempo reale su API-Football ma non ancora importato (id assente,
    # api_football_id popolato) -> il frontend deve chiamare /watchlist/import.
    source: str = "local"
    id: int | None = None
    api_football_id: str | None = None
    full_name: str
    current_team: str | None
    league: str | None
    photo_url: str | None
    in_watchlist: bool = False


class WatchlistImportRequest(BaseModel):
    api_football_id: str
