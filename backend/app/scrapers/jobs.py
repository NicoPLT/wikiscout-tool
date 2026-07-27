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
from app.models.player import Player
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
    since = (now - timedelta(hours=48)).date()
    matches = api_football.fetch_recent_match_stats(player, since)
    if not matches:
        return
    # Fase B: qui andra' il parsing della risposta API-Football in righe
    # PlayerStatsMatch + il ricalcolo degli aggregati denormalizzati su Player.
    player.stats_updated_at = now


def _update_xg_xa(db: Session, player: Player, now: datetime) -> None:
    if not player.is_xg_covered:
        return
    data = understat.fetch_xg_xa(player)
    if not data:
        return
    player.xg_season = data.get("xG", player.xg_season)
    player.xa_season = data.get("xA", player.xa_season)


def _update_market_value(db: Session, player: Player, now: datetime) -> None:
    if player.market_value_updated_at and (now - player.market_value_updated_at) < timedelta(
        days=MARKET_VALUE_REFRESH_DAYS
    ):
        return

    new_value = transfermarkt.fetch_market_value(player)
    if new_value is None:
        return

    previous = float(player.market_value_eur) if player.market_value_eur is not None else new_value
    player.market_value_change_eur = new_value - previous
    player.market_value_change_pct = ((new_value - previous) / previous * 100) if previous else 0
    player.market_value_eur = new_value
    player.market_value_updated_at = now


def _update_rating(db: Session, player: Player, now: datetime) -> None:
    rating = sofascore.fetch_latest_rating(player)
    if rating is None:
        return
    player.rating_avg = rating
    player.rating_updated_at = now
