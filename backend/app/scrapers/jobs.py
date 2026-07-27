"""Job notturno di aggiornamento dati per tutti i giocatori in watchlist.

Orchestrazione (eseguita una volta al giorno, ore configurate in .env), per
ogni giocatore in watchlist:
  1. Transfermarkt (Apify, invariato): valore di mercato, solo se l'ultimo
     aggiornamento risale a piu' di 7 giorni fa.
  2. Transfermarkt (client diretto tmapi.transfermarkt.technology):
     statistiche stagionali sul campionato principale del club attuale
     (goal/assist/presenze/minuti) e ultime partite reali con
     goal/assist/minuti/competizione/avversario.
  3. Sofascore: SOLO rating e xG/xA (dati che Transfermarkt non ha mai
     pubblicato) — un'unica sessione browser Playwright riutilizzata per
     tutti i giocatori del giro.
  4. (opzionale, spento di default) API-Football legacy, solo se
     ENABLE_API_FOOTBALL=true — vedi app/services/providers/api_football.py.
  5. Scrive ogni esito in data_sources_log e il timestamp "ultimo
     aggiornamento" per riga.

Se una fonte non e' disponibile o un giocatore non ha un link valido
(es. sofascore_id non ancora risolto), lo step viene saltato con un log,
senza mai rompere il job per gli altri giocatori.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.data_source_log import DataSourceLog
from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.watchlist import Watchlist
from app.scrapers import sofascore, transfermarkt
from app.services.cache_service import cache_delete_prefix
from app.services.player_service import WATCHLIST_CACHE_PREFIX

logger = logging.getLogger(__name__)
settings = get_settings()

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
            _update_market_value(db, player, now)
            _update_from_transfermarkt_performance(db, player, now)
            _backfill_market_value_history(db, player)
            _resolve_fotmob_link(db, player)
            _resolve_date_of_birth(db, player)
            processed += 1

        # Una sola sessione browser Sofascore per tutti i giocatori del giro
        # (evita di pagare avvio/consenso una volta per giocatore).
        with sofascore.SofascoreSession() as session:
            for player in players:
                _update_from_sofascore(db, session, player, now)

        if settings.ENABLE_API_FOOTBALL:
            _run_legacy_api_football_step(db, players, now)

        for player in players:
            player.last_synced_at = now
            db.add(player)

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


def _update_from_transfermarkt_performance(db: Session, player: Player, now: datetime) -> None:
    from app.services.player_service import _apply_transfermarkt_performance

    _apply_transfermarkt_performance(db, player)


def _backfill_market_value_history(db: Session, player: Player) -> None:
    from app.services.player_service import _backfill_market_value_history as _backfill

    _backfill(db, player)


def _resolve_fotmob_link(db: Session, player: Player) -> None:
    from app.services.player_service import resolve_fotmob_link

    resolve_fotmob_link(player)


def _resolve_date_of_birth(db: Session, player: Player) -> None:
    from app.services.player_service import resolve_date_of_birth

    resolve_date_of_birth(player)


def _update_from_sofascore(db: Session, session: "sofascore.SofascoreSession", player: Player, now: datetime) -> None:
    if not session.ok:
        logger.warning("Sessione Sofascore non disponibile: salto tutti i giocatori per questo giro")
        return

    from app.services.player_service import _apply_sofascore_link, link_sofascore_profile

    if not player.sofascore_id:
        # Prima volta che vediamo questo giocatore senza link: prova a
        # risolverlo automaticamente (stesso pattern usato in fase di import).
        link_sofascore_profile(db, session, player)
        return

    _apply_sofascore_link(db, session, player, int(player.sofascore_id))


def _run_legacy_api_football_step(db: Session, players: list[Player], now: datetime) -> None:
    """Step legacy/opzionale, spento di default (ENABLE_API_FOOTBALL=false).
    Non fa piu' parte del percorso critico: Transfermarkt/Sofascore coprono
    gia' ricerca, valore di mercato, statistiche, rating e xG/xA.
    """
    from app.services.providers import api_football

    if not api_football.is_configured():
        return

    logger.info("Step legacy API-Football attivo (ENABLE_API_FOOTBALL=true)")
    for player in players:
        if not player.api_football_id:
            continue
        try:
            api_football_id = int(player.api_football_id)
        except ValueError:
            continue
        entry = api_football.get_player_by_id(api_football_id)
        if entry is None:
            continue
        # Intenzionalmente non sovrascrive i campi principali (li gestiscono
        # ormai Transfermarkt/Sofascore): questo step resta un semplice hook
        # per usi futuri (es. formazioni) su dati che non tocchiamo altrove.
        logger.debug("API-Football legacy: dati disponibili per player_id=%s", player.id)
