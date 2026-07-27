"""Job notturno di aggiornamento dati per tutti i giocatori in watchlist.

Orchestrazione (eseguita una volta al giorno, ore configurate in .env):
  1. Per ogni giocatore in almeno una watchlist, controlla se ha giocato
     nelle ultime 24-48h (API-Football) e in caso aggiorna le statistiche.
  2. Se il campionato e' coperto da Understat, aggiorna xG/xA.
  3. Aggiorna il valore di mercato (Transfermarkt) solo se l'ultimo
     aggiornamento risale a piu' di 7 giorni fa.
  4. Aggiorna il rating (Sofascore/Fotmob) se disponibile.
  5. Scrive ogni esito in data_sources_log.

Finche' le chiavi API-Football/Apify non sono configurate, ogni step logga
un warning e viene saltato (vedi app/scrapers/*.py) senza mai rompere il job
o l'app: la dashboard continua a leggere l'ultimo snapshot scritto nel DB
(dal seed di mock in Fase A, o dal job stesso una volta attive le chiavi).
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.data_source_log import DataSourceLog
from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.watchlist import Watchlist
from app.scrapers import api_football, sofascore, transfermarkt, understat
from app.services.cache_service import cache_delete_prefix
from app.services.player_service import WATCHLIST_CACHE_PREFIX

logger = logging.getLogger(__name__)

MARKET_VALUE_REFRESH_DAYS = 7


def _log_run(db: Session, job_name: str, source: str, status: str, message: str, players_processed: int, duration_ms: int) -> None:
    db.add(
        DataSourceLog(
            job_name=job_name,
            source=source,
            status=status,
            message=message,
            players_processed=players_processed,
            duration_ms=duration_ms,
        )
    )
    db.commit()


def _watchlisted_players(db: Session) -> list[Player]:
    player_ids = db.execute(select(Watchlist.player_id).distinct()).scalars().all()
    if not player_ids:
        return []
    return db.execute(select(Player).where(Player.id.in_(player_ids))).scalars().all()


def run_nightly_update() -> None:
    db = SessionLocal()
    start = time.monotonic()
    now = datetime.now(timezone.utc)
    processed = 0

    try:
        players = _watchlisted_players(db)
        logger.info("Job notturno: %s giocatori in watchlist da controllare", len(players))

        for player in players:
            _update_recent_stats(db, player, now)
            _update_xg_xa(db, player, now)
            _update_market_value(db, player, now)
            _update_rating(db, player, now)
            player.last_synced_at = now
            db.add(player)
            processed += 1

        db.commit()

        for user_id in db.execute(select(Watchlist.user_id).distinct()).scalars().all():
            cache_delete_prefix(f"{WATCHLIST_CACHE_PREFIX}{user_id}")

        duration_ms = int((time.monotonic() - start) * 1000)
        _log_run(db, "nightly_update", "all", "success", "Job completato", processed, duration_ms)
    except Exception as exc:  # noqa: BLE001 - vogliamo loggare qualsiasi errore e non far crashare lo scheduler
        logger.exception("Errore nel job notturno")
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_run(db, "nightly_update", "all", "error", str(exc), processed, duration_ms)
    finally:
        db.close()


def _update_recent_stats(db: Session, player: Player, now: datetime) -> None:
    """Rinfresca gli aggregati stagionali e aggiunge eventuali nuove partite
    reali (giocate nelle ultime 48h) per un giocatore con un vero
    api_football_id. I giocatori del seed di mock hanno id fittizi
    (es. "mock-af-3") e vengono saltati senza errore.
    """
    if not player.api_football_id:
        return
    try:
        api_football_id = int(player.api_football_id)
    except ValueError:
        logger.info("player_id=%s ha un api_football_id non reale (seed mock): salto", player.id)
        return

    entry = api_football.get_player_by_id(api_football_id)
    if entry is None:
        return

    snapshot = api_football.build_player_snapshot(entry)
    player.current_team = snapshot["current_team"] or player.current_team
    player.league = snapshot["league"] or player.league
    player.is_xg_covered = snapshot["is_xg_covered"]
    player.goals_season = snapshot["goals_season"]
    player.assists_season = snapshot["assists_season"]
    player.appearances_season = snapshot["appearances_season"]
    player.minutes_season = snapshot["minutes_season"]

    team_id = snapshot.get("team_id")
    if team_id:
        _ingest_new_fixtures(db, player, team_id, api_football_id, now)

    player.stats_updated_at = now


def _ingest_new_fixtures(db: Session, player: Player, team_id: int, api_football_id: int, now: datetime) -> None:
    existing_refs = {
        ref
        for ref in db.execute(
            select(PlayerStatsMatch.external_ref).where(PlayerStatsMatch.player_id == player.id)
        ).scalars()
        if ref
    }

    fixtures = api_football.get_team_recent_fixtures(team_id, last=2)
    new_rows: list[PlayerStatsMatch] = []

    for fixture in fixtures:
        if not api_football.is_recently_finished(fixture, within_hours=48):
            continue

        fixture_id = fixture.get("fixture", {}).get("id")
        if fixture_id is None or str(fixture_id) in existing_refs:
            continue

        stats = api_football.get_fixture_player_stats(fixture_id, api_football_id)
        if stats is None:
            continue

        games = stats.get("statistics", [{}])[0].get("games", {}) if stats.get("statistics") else {}
        goals = stats.get("statistics", [{}])[0].get("goals", {}) if stats.get("statistics") else {}
        teams = fixture.get("teams", {})
        is_home = (teams.get("home", {}) or {}).get("id") == team_id
        rating_raw = games.get("rating")

        new_rows.append(
            PlayerStatsMatch(
                player_id=player.id,
                match_date=api_football.fixture_match_date(fixture) or now.date(),
                competition=fixture.get("league", {}).get("name") or player.league or "N/D",
                opponent=(teams.get("away") if is_home else teams.get("home") or {}).get("name"),
                is_home=is_home,
                minutes_played=games.get("minutes") or 0,
                goals=goals.get("total") or 0,
                assists=goals.get("assists") or 0,
                rating=float(rating_raw) if rating_raw else None,
                source="api_football",
                external_ref=str(fixture_id),
            )
        )

    if not new_rows:
        return

    db.add_all(new_rows)
    db.flush()

    all_matches = db.execute(
        select(PlayerStatsMatch)
        .where(PlayerStatsMatch.player_id == player.id)
        .order_by(PlayerStatsMatch.match_date.desc())
        .limit(5)
    ).scalars().all()

    player.goals_last5 = sum(m.goals for m in all_matches)
    player.assists_last5 = sum(m.assists for m in all_matches)

    rated_new = [r.rating for r in new_rows if r.rating is not None]
    if rated_new and not sofascore.is_configured():
        # Se non abbiamo ancora una fonte Sofascore reale, usiamo il rating
        # match-by-match di API-Football (comunque dato reale) come base.
        player.rating_avg = round(rated_new[-1], 2) if len(rated_new) == 1 else round(
            sum(rated_new) / len(rated_new), 2
        )
        player.rating_updated_at = now


def _update_xg_xa(db: Session, player: Player, now: datetime) -> None:
    if not player.is_xg_covered:
        return
    data = understat.fetch_xg_xa(player, season=api_football.current_season())
    if not data:
        return
    player.xg_season = data.get("xG", player.xg_season)
    player.xa_season = data.get("xA", player.xa_season)


def _update_market_value(db: Session, player: Player, now: datetime) -> None:
    if player.market_value_updated_at and (now - player.market_value_updated_at) < timedelta(
        days=MARKET_VALUE_REFRESH_DAYS
    ):
        return

    result = transfermarkt.fetch_market_value(player)
    if result is None:
        return
    new_value, transfermarkt_id = result

    previous = float(player.market_value_eur) if player.market_value_eur is not None else new_value
    player.market_value_change_eur = new_value - previous
    player.market_value_change_pct = ((new_value - previous) / previous * 100) if previous else 0
    player.market_value_eur = new_value
    player.market_value_updated_at = now
    if transfermarkt_id and not player.transfermarkt_id:
        player.transfermarkt_id = transfermarkt_id

    db.add(
        PlayerMarketValueHistory(
            player_id=player.id,
            value_eur=new_value,
            recorded_at=now.date(),
            source="transfermarkt",
        )
    )


def _update_rating(db: Session, player: Player, now: datetime) -> None:
    rating = sofascore.fetch_latest_rating(player)
    if rating is None:
        return
    player.rating_avg = rating
    player.rating_updated_at = now
