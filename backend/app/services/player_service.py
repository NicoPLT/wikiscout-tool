"""Repository/service layer per l'accesso ai dati giocatori.

Questo modulo e' l'unico punto in cui l'API legge/scrive le tabelle players,
player_stats_matches, player_market_value_history e watchlists. Che i dati
in queste tabelle siano stati scritti dal seed di mock (Fase A) o dal job
notturno di scraping reale (Fase B) e' del tutto trasparente qui: cambia solo
chi popola le tabelle, non come vengono lette. Frontend e modello dati non
vanno mai toccati passando da A a B.
"""

import re
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
from app.scrapers import sofascore, transfermarkt
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
    su Transfermarkt, cosi' lo scout puo' trovare e aggiungere QUALSIASI
    giocatore reale, non solo quelli gia' importati. Nessun vincolo di
    stagione (a differenza della vecchia integrazione API-Football).
    """
    stmt = select(Player).where(Player.full_name.ilike(f"%{query}%")).limit(20)
    local_players = db.execute(stmt).scalars().all()

    watchlisted_ids = set(
        db.execute(select(Watchlist.player_id).where(Watchlist.user_id == user_id)).scalars().all()
    )
    known_transfermarkt_ids = set(
        db.execute(select(Player.transfermarkt_id).where(Player.transfermarkt_id.is_not(None))).scalars().all()
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

    if len(query.strip()) >= 2:
        for candidate in transfermarkt.search_players_transfermarkt(query):
            tm_id = candidate["transfermarkt_id"]
            if tm_id in known_transfermarkt_ids:
                continue  # gia' rappresentato tra i risultati locali

            results.append(
                PlayerSearchResult(
                    source="transfermarkt",
                    transfermarkt_id=tm_id,
                    full_name=candidate["full_name"],
                    current_team=candidate["current_team"],
                    league=None,
                    photo_url=candidate["photo_url"],
                    in_watchlist=False,
                    position=candidate["position"],
                    nationality=candidate["nationality"],
                    market_value_eur=candidate["market_value_eur"],
                )
            )

    return results[:20]


def import_player_from_transfermarkt(
    db: Session,
    user_id: int,
    transfermarkt_id: str,
    full_name: str,
    current_team: str | None,
    position: str | None,
    nationality: str | None,
    market_value_eur: float | None,
    photo_url: str | None,
) -> Player | None:
    """Crea (se non esiste) un giocatore reale a partire dai dati del
    candidato Transfermarkt gia' ottenuti in fase di ricerca (Transfermarkt
    si cerca per NOME, non per id: non ha senso ri-cercare l'id come se
    fosse un nome, per questo il chiamante passa i dati gia' noti invece di
    un semplice id). Prova poi a risolvere il mapping Sofascore per
    nome+squadra e a popolare statistiche stagionali/ultime partite reali.
    Se il mapping Sofascore fallisce o e' ambiguo, il giocatore viene
    comunque aggiunto (con dati Transfermarkt) e lo scout potra' collegare
    Sofascore manualmente in un secondo momento.
    """
    existing = db.execute(
        select(Player).where(Player.transfermarkt_id == transfermarkt_id)
    ).scalar_one_or_none()
    if existing is not None:
        add_to_watchlist(db, user_id, existing.id, None, None)
        return existing

    player = Player(
        full_name=full_name,
        nationality=nationality,
        position=position,
        current_team=current_team,
        photo_url=photo_url,
        transfermarkt_id=transfermarkt_id,
        market_value_eur=market_value_eur,
        market_value_updated_at=datetime.now(timezone.utc) if market_value_eur is not None else None,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(player)
    db.flush()

    with sofascore.SofascoreSession() as session:
        link_sofascore_profile(db, session, player)

    db.commit()
    db.refresh(player)

    add_to_watchlist(db, user_id, player.id, None, None)
    return player


def link_sofascore_profile(db: Session, session: "sofascore.SofascoreSession", player: Player) -> bool:
    """Prova a risolvere e collegare il profilo Sofascore di `player` (per
    nome+squadra attuale) e, se riesce, popola subito statistiche stagionali
    e ultime partite reali. Ritorna True se il collegamento e' riuscito.
    Ambiguo/non trovato -> non tocca nulla, il chiamante decide come gestirlo
    (import automatico: lascia N/D; link manuale: segnala allo scout).
    """
    if not session.ok:
        return False

    candidates = sofascore.search_players(session, player.full_name)
    match = _best_sofascore_match(candidates, player.current_team)
    if match is None:
        return False

    return _apply_sofascore_link(db, session, player, match["id"])


def _best_sofascore_match(candidates: list[dict], current_team: str | None) -> dict | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if not current_team:
        return None  # piu' di un omonimo e nessuna squadra per disambiguare: ambiguo

    team_lower = current_team.strip().lower()
    team_matches = [
        c for c in candidates if c.get("team") and (team_lower in c["team"].lower() or c["team"].lower() in team_lower)
    ]
    if len(team_matches) == 1:
        return team_matches[0]
    return None  # 0 o piu' di 1 match per squadra: resta ambiguo, non indoviniamo


def _apply_sofascore_link(db: Session, session: "sofascore.SofascoreSession", player: Player, sofascore_id: int) -> bool:
    player.sofascore_id = str(sofascore_id)

    season_stats = sofascore.get_season_stats(session, sofascore_id)
    if season_stats:
        player.league = season_stats["league"] or player.league
        player.current_team = season_stats["current_team"] or player.current_team
        player.goals_season = season_stats["goals_season"]
        player.assists_season = season_stats["assists_season"]
        player.appearances_season = season_stats["appearances_season"]
        player.minutes_season = season_stats["minutes_season"]
        player.is_xg_covered = season_stats["xg_season"] is not None
        if season_stats["xg_season"] is not None:
            player.xg_season = season_stats["xg_season"]
        if season_stats["xa_season"] is not None:
            player.xa_season = season_stats["xa_season"]
        player.stats_updated_at = datetime.now(timezone.utc)

    recent_matches = sofascore.get_recent_matches(session, sofascore_id, limit=5)
    if recent_matches:
        existing_refs = {
            ref
            for ref in db.execute(
                select(PlayerStatsMatch.external_ref).where(PlayerStatsMatch.player_id == player.id)
            ).scalars()
            if ref
        }
        new_rows = [
            PlayerStatsMatch(
                player_id=player.id,
                match_date=m["match_date"],
                competition=m["competition"],
                opponent=m["opponent"],
                is_home=m["is_home"],
                minutes_played=m["minutes_played"],
                goals=m["goals"],
                assists=m["assists"],
                rating=m["rating"],
                source="sofascore",
                external_ref=m["external_ref"],
            )
            for m in recent_matches
            if m["external_ref"] not in existing_refs
        ]
        if new_rows:
            db.add_all(new_rows)
            db.flush()

        rated = [m["rating"] for m in recent_matches if m["rating"] is not None]
        if rated:
            player.rating_avg = round(sum(rated) / len(rated), 2)
            player.rating_updated_at = datetime.now(timezone.utc)

        player.goals_last5 = sum(m["goals"] for m in recent_matches[:5])
        player.assists_last5 = sum(m["assists"] for m in recent_matches[:5])

    return True


def link_sofascore_manual(db: Session, user_id: int, player_id: int, sofascore_url_or_id: str) -> Player | None:
    """Collegamento manuale (fallback quando l'auto-match fallisce/e' ambiguo):
    lo scout incolla l'URL del profilo Sofascore corretto (o il solo id
    numerico finale), e ricalcoliamo subito statistiche/ultime partite reali.
    """
    player = db.get(Player, player_id)
    if player is None:
        return None

    digits = re.search(r"(\d+)\D*$", sofascore_url_or_id.strip())
    if not digits:
        return None
    sofascore_id = int(digits.group(1))

    with sofascore.SofascoreSession() as session:
        ok = _apply_sofascore_link(db, session, player, sofascore_id)
    if not ok:
        return None

    db.commit()
    db.refresh(player)
    invalidate_watchlist_cache(user_id)
    return player


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
