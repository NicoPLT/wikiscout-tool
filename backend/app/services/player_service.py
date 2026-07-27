"""Repository/service layer per l'accesso ai dati giocatori.

Questo modulo e' l'unico punto in cui l'API legge/scrive le tabelle players,
player_stats_matches, player_market_value_history e watchlists. Che i dati
in queste tabelle siano stati scritti dal seed di mock (Fase A) o dal job
notturno di scraping reale (Fase B) e' del tutto trasparente qui: cambia solo
chi popola le tabelle, non come vengono lette. Frontend e modello dati non
vanno mai toccati passando da A a B.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.watchlist import Watchlist
from app.schemas.player import (
    MarketValuePoint,
    MarketValueTrendPoint,
    MatchStatLine,
    PlayerDetail,
    PlayerRow,
    PlayerSearchResult,
    RecentUpdateItem,
    WatchlistSummary,
)
from app.scrapers import api_football
from app.services.cache_service import cache_delete_prefix, cache_get, cache_set

WATCHLIST_CACHE_PREFIX = "watchlist:user:"


def _player_to_row(player: Player, watchlist_entry: Watchlist | None) -> PlayerRow:
    return PlayerRow(
        id=player.id,
        full_name=player.full_name,
        photo_url=player.photo_url,
        current_team=player.current_team,
        league=player.league,
        position=player.position,
        market_value_eur=float(player.market_value_eur) if player.market_value_eur is not None else None,
        market_value_change_eur=(
            float(player.market_value_change_eur) if player.market_value_change_eur is not None else None
        ),
        market_value_change_pct=(
            float(player.market_value_change_pct) if player.market_value_change_pct is not None else None
        ),
        goals_last5=player.goals_last5,
        assists_last5=player.assists_last5,
        goals_season=player.goals_season,
        assists_season=player.assists_season,
        appearances_season=player.appearances_season,
        minutes_season=player.minutes_season,
        rating_avg=float(player.rating_avg) if player.rating_avg is not None else None,
        is_xg_covered=player.is_xg_covered,
        xg_season=float(player.xg_season) if player.xg_season is not None else None,
        xa_season=float(player.xa_season) if player.xa_season is not None else None,
        watchlist_notes=watchlist_entry.notes if watchlist_entry else None,
        watchlist_tags=watchlist_entry.tags if watchlist_entry else None,
        last_synced_at=player.last_synced_at,
    )


def get_watchlist_rows(db: Session, user_id: int, use_cache: bool = True) -> list[PlayerRow]:
    cache_key = f"{WATCHLIST_CACHE_PREFIX}{user_id}"
    if use_cache:
        cached = cache_get(cache_key)
        if cached is not None:
            return [PlayerRow.model_validate(row) for row in cached]

    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .options(selectinload(Watchlist.player))
    )
    entries = db.execute(stmt).scalars().all()
    rows = [_player_to_row(entry.player, entry) for entry in entries]

    cache_set(cache_key, [row.model_dump() for row in rows])
    return rows


def invalidate_watchlist_cache(user_id: int) -> None:
    cache_delete_prefix(f"{WATCHLIST_CACHE_PREFIX}{user_id}")


def get_player_detail(db: Session, user_id: int, player_id: int) -> PlayerDetail | None:
    player = db.get(Player, player_id)
    if player is None:
        return None

    watchlist_entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()

    recent_matches = sorted(player.stats_matches, key=lambda m: m.match_date, reverse=True)[:20]
    market_history = sorted(player.market_value_history, key=lambda m: m.recorded_at)

    row = _player_to_row(player, watchlist_entry)
    return PlayerDetail(
        **row.model_dump(),
        date_of_birth=player.date_of_birth,
        nationality=player.nationality,
        transfermarkt_id=player.transfermarkt_id,
        api_football_id=player.api_football_id,
        sofascore_id=player.sofascore_id,
        stats_updated_at=player.stats_updated_at,
        market_value_updated_at=player.market_value_updated_at,
        rating_updated_at=player.rating_updated_at,
        recent_matches=[MatchStatLine.model_validate(m) for m in recent_matches],
        market_value_history=[MarketValuePoint.model_validate(m) for m in market_history],
    )


def search_all_players(db: Session, user_id: int, query: str) -> list[PlayerSearchResult]:
    """Autocomplete: unisce i giocatori gia' nel nostro DB con una ricerca live
    su API-Football, cosi' lo scout puo' trovare e aggiungere QUALSIASI
    giocatore reale, non solo quelli gia' importati.
    """
    stmt = select(Player).where(Player.full_name.ilike(f"%{query}%")).limit(20)
    local_players = db.execute(stmt).scalars().all()

    watchlisted_ids = set(
        db.execute(select(Watchlist.player_id).where(Watchlist.user_id == user_id)).scalars().all()
    )
    known_api_football_ids = set(
        db.execute(select(Player.api_football_id).where(Player.api_football_id.is_not(None))).scalars().all()
    )

    results = [
        PlayerSearchResult(
            source="local",
            id=p.id,
            full_name=p.full_name,
            current_team=p.current_team,
            league=p.league,
            photo_url=p.photo_url,
            in_watchlist=p.id in watchlisted_ids,
        )
        for p in local_players
    ]

    if len(query.strip()) >= 3:
        for candidate in api_football.search_players(query):
            af_id = str(candidate["id"])
            if af_id in known_api_football_ids:
                continue  # gia' rappresentato tra i risultati locali

            results.append(
                PlayerSearchResult(
                    source="api_football",
                    api_football_id=af_id,
                    full_name=candidate["name"],
                    current_team=candidate["team"],
                    league=candidate["league"],
                    photo_url=candidate["photo"],
                    in_watchlist=False,
                )
            )

    return results[:20]


def import_player_from_api_football(db: Session, user_id: int, api_football_id: str) -> Player | None:
    """Crea (se non esiste) un giocatore reale a partire dal suo id API-Football,
    con statistiche stagionali reali e le ultime 5 partite reali, poi lo
    aggiunge alla watchlist. Ritorna None se API-Football non e' configurata
    o il giocatore non viene trovato.
    """
    existing = db.execute(
        select(Player).where(Player.api_football_id == api_football_id)
    ).scalar_one_or_none()
    if existing is not None:
        add_to_watchlist(db, user_id, existing.id, None, None)
        return existing

    entry = api_football.get_player_by_id(int(api_football_id))
    if entry is None:
        return None

    snapshot = api_football.build_player_snapshot(entry)

    dob = None
    if snapshot["date_of_birth"]:
        try:
            dob = date.fromisoformat(snapshot["date_of_birth"])
        except ValueError:
            dob = None

    player = Player(
        full_name=snapshot["full_name"],
        date_of_birth=dob,
        nationality=snapshot["nationality"],
        position=snapshot["position"],
        current_team=snapshot["current_team"],
        league=snapshot["league"],
        photo_url=snapshot["photo_url"],
        api_football_id=api_football_id,
        is_xg_covered=snapshot["is_xg_covered"],
        goals_season=snapshot["goals_season"],
        assists_season=snapshot["assists_season"],
        appearances_season=snapshot["appearances_season"],
        minutes_season=snapshot["minutes_season"],
        stats_updated_at=datetime.now(timezone.utc),
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(player)
    db.flush()

    team_id = snapshot.get("team_id")
    if team_id:
        recent_matches = _fetch_recent_match_rows(player, team_id)
        db.add_all(recent_matches)
        db.flush()
        _recompute_last5(player, recent_matches)

    db.commit()
    db.refresh(player)

    add_to_watchlist(db, user_id, player.id, None, None)
    return player


def _fetch_recent_match_rows(player: Player, team_id: int) -> list[PlayerStatsMatch]:
    """Chiamata una tantum (costo accettabile solo all'aggiunta in watchlist):
    recupera le ultime 5 partite della squadra e ne estrae le statistiche del
    singolo giocatore, se ha giocato.
    """
    rows: list[PlayerStatsMatch] = []
    fixtures = api_football.get_team_recent_fixtures(team_id, last=5)

    for fixture in fixtures:
        fixture_id = fixture.get("fixture", {}).get("id")
        match_date = api_football.fixture_match_date(fixture)
        if fixture_id is None or match_date is None:
            continue

        stats = api_football.get_fixture_player_stats(fixture_id, int(player.api_football_id))
        if stats is None:
            continue

        games = stats.get("statistics", [{}])[0].get("games", {}) if stats.get("statistics") else {}
        goals = stats.get("statistics", [{}])[0].get("goals", {}) if stats.get("statistics") else {}
        teams = fixture.get("teams", {})
        is_home = (teams.get("home", {}) or {}).get("id") == team_id

        rating_raw = games.get("rating")
        rating = float(rating_raw) if rating_raw else None

        rows.append(
            PlayerStatsMatch(
                player_id=player.id,
                match_date=match_date,
                competition=fixture.get("league", {}).get("name") or player.league or "N/D",
                opponent=(teams.get("away") if is_home else teams.get("home") or {}).get("name"),
                is_home=is_home,
                minutes_played=games.get("minutes") or 0,
                goals=goals.get("total") or 0,
                assists=goals.get("assists") or 0,
                rating=rating,
                source="api_football",
                external_ref=str(fixture_id),
            )
        )

    return rows


def _recompute_last5(player: Player, matches: list[PlayerStatsMatch]) -> None:
    last5 = sorted(matches, key=lambda m: m.match_date, reverse=True)[:5]
    player.goals_last5 = sum(m.goals for m in last5)
    player.assists_last5 = sum(m.assists for m in last5)
    rated = [m.rating for m in matches if m.rating is not None]
    if rated:
        player.rating_avg = round(sum(rated) / len(rated), 2)
        player.rating_updated_at = datetime.now(timezone.utc)


def add_to_watchlist(db: Session, user_id: int, player_id: int, notes: str | None, tags: list[str] | None) -> Watchlist:
    existing = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if existing:
        return existing

    entry = Watchlist(user_id=user_id, player_id=player_id, notes=notes, tags=tags)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    invalidate_watchlist_cache(user_id)
    return entry


def update_watchlist_entry(
    db: Session, user_id: int, player_id: int, notes: str | None, tags: list[str] | None
) -> Watchlist | None:
    entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if entry is None:
        return None

    if notes is not None:
        entry.notes = notes
    if tags is not None:
        entry.tags = tags
    db.commit()
    db.refresh(entry)
    invalidate_watchlist_cache(user_id)
    return entry


def remove_from_watchlist(db: Session, user_id: int, player_id: int) -> bool:
    entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if entry is None:
        return False

    db.delete(entry)
    db.commit()
    invalidate_watchlist_cache(user_id)
    return True


def get_watchlist_summary(db: Session, user_id: int) -> WatchlistSummary:
    """Aggrega i dati della watchlist per i widget di sintesi della dashboard
    (gauge rating medio, trend valore di mercato, lista ultimi aggiornamenti).
    """
    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .options(selectinload(Watchlist.player).selectinload(Player.market_value_history))
    )
    entries = db.execute(stmt).scalars().all()
    players = [entry.player for entry in entries]

    ratings = [float(p.rating_avg) for p in players if p.rating_avg is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    total_market_value = sum(float(p.market_value_eur or 0) for p in players)

    # Trend aggregato: allinea gli storici per posizione (i punti del seed sono
    # generati con la stessa cadenza per ogni giocatore); ogni indice diventa
    # un punto del grafico sommando i valori di tutti i giocatori a quell'indice.
    histories = [sorted(p.market_value_history, key=lambda h: h.recorded_at) for p in players]
    max_len = max((len(h) for h in histories), default=0)
    trend: list[MarketValueTrendPoint] = []
    for i in range(max_len):
        total = 0.0
        latest_date = None
        for h in histories:
            if i < len(h):
                total += float(h[i].value_eur)
                if latest_date is None or h[i].recorded_at > latest_date:
                    latest_date = h[i].recorded_at
            elif h:
                total += float(h[-1].value_eur)
        if latest_date is not None:
            trend.append(MarketValueTrendPoint(recorded_at=latest_date, total_value_eur=round(total, 2)))

    recent_updates: list[RecentUpdateItem] = []
    for p in players:
        if p.market_value_updated_at is not None:
            recent_updates.append(
                RecentUpdateItem(
                    player_id=p.id,
                    full_name=p.full_name,
                    photo_url=p.photo_url,
                    kind="market_value",
                    label="Valore di mercato aggiornato",
                    change_pct=float(p.market_value_change_pct) if p.market_value_change_pct is not None else None,
                    at=p.market_value_updated_at,
                )
            )
        if p.rating_updated_at is not None:
            recent_updates.append(
                RecentUpdateItem(
                    player_id=p.id,
                    full_name=p.full_name,
                    photo_url=p.photo_url,
                    kind="rating",
                    label=f"Rating aggiornato a {p.rating_avg}",
                    change_pct=None,
                    at=p.rating_updated_at,
                )
            )
    recent_updates.sort(key=lambda item: item.at, reverse=True)

    return WatchlistSummary(
        players_count=len(players),
        avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
        total_market_value_eur=round(total_market_value, 2),
        market_value_trend=trend,
        recent_updates=recent_updates[:8],
    )
