"""Resumable, zero-paid-provider worker; run by GitHub Actions or locally."""
import logging
import time
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.data_source_log import DataSourceLog
from app.models.job_lease import JobLease
from app.models.player import Player
from app.models.watchlist import Watchlist
from app.scrapers import sofascore, transfermarkt_performance
from app.scrapers.errors import SourceUnavailable, strict_scraping
from app.services import player_service, watch_alert_service

logger = logging.getLogger(__name__)
settings = get_settings()
LEASE_NAME = "nightly_update"
LEASE_MINUTES = 10
# API-Football and Apify are deliberately absent from this worker.
INTERVALS = {"stats": 20, "market": 24 * 7, "transfers": 24 * 7, "links": 24 * 7, "ratings": 20}


class NoPlayerData(RuntimeError):
    pass


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def acquire_lease(db, owner):
    if db.get(JobLease, LEASE_NAME) is None:
        try:
            db.add(JobLease(name=LEASE_NAME))
            db.commit()
        except IntegrityError:
            db.rollback()
    now = datetime.now(timezone.utc)
    changed = db.execute(update(JobLease).execution_options(synchronize_session=False).where(JobLease.name == LEASE_NAME,
        or_(JobLease.owner.is_(None), JobLease.expires_at <= now)).values(
        owner=owner, expires_at=now + timedelta(minutes=LEASE_MINUTES))).rowcount
    db.commit()
    return changed == 1


def renew_lease(db, owner):
    now = datetime.now(timezone.utc)
    changed = db.execute(update(JobLease).execution_options(synchronize_session=False).where(JobLease.name == LEASE_NAME,
        JobLease.owner == owner, JobLease.expires_at > now).values(
        expires_at=now + timedelta(minutes=LEASE_MINUTES))).rowcount
    if changed != 1:
        db.rollback()
        raise RuntimeError("Lock aggiornamento scaduto o acquisito da un altro processo")


def release_lease(db, owner):
    db.execute(update(JobLease).execution_options(synchronize_session=False).where(JobLease.name == LEASE_NAME, JobLease.owner == owner)
        .values(owner=None, expires_at=None))
    db.commit()


def _is_due(state, now):
    next_attempt = state.get("next_attempt_at")
    return not next_attempt or datetime.fromisoformat(next_attempt) <= now


def _refresh_transfers(db, player):
    transfers = transfermarkt_performance.get_transfer_history(player.transfermarkt_id)
    player.transfers_data = [t.model_dump(mode="json") for t in transfers]
    completed = [t for t in transfers if t.transfer_date <= datetime.now(timezone.utc).date()]
    if completed:
        latest = max(completed, key=lambda t: t.transfer_date)
        if latest.club_to_name:
            player.current_team = latest.club_to_name
    return True  # an empty, successful history is valid


def _refresh_links(db, player):
    player_service.resolve_date_of_birth(player)
    player_service.resolve_fotmob_link(player)
    return bool(player.date_of_birth or player.fotmob_id)


def _refresh_ratings(db, player, session):
    if not session.ok:
        raise SourceUnavailable("Sessione Sofascore non disponibile")
    if player.sofascore_id:
        return player_service._apply_sofascore_link(db, session, player, int(player.sofascore_id))
    return player_service.link_sofascore_profile(db, session, player)


def _player_status(player):
    states = player.sync_state or {}
    if any(s.get("error") for s in states.values()):
        return "partial" if any(s.get("last_success_at") for s in states.values()) else "error"
    if all(states.get(source, {}).get("last_success_at") for source in INTERVALS):
        return "success"
    return "pending"


def run_nightly_update() -> dict:
    """Commit every source/player separately. A rerun skips completed work.

    Per-source circuit breakers and a wall-clock budget bound free usage.
    Sorting by oldest attempt prevents starvation when the budget is exhausted.
    """
    db = SessionLocal()
    owner = str(uuid4())
    started = time.monotonic()
    failures = dict.fromkeys(INTERVALS, 0)
    result = {"status": "success", "succeeded": 0, "failed": 0, "deferred": 0, "players_processed": 0}
    token = strict_scraping.set(True)
    acquired = False
    try:
        acquired = acquire_lease(db, owner)
        if not acquired:
            return {**result, "status": "already_running"}
        candidates = db.execute(select(Player.id, Player.sync_attempted_at).join(Watchlist).distinct()).all()
        candidates.sort(key=lambda row: _utc(row.sync_attempted_at) or datetime.min.replace(tzinfo=timezone.utc))
        ids = [row.id for row in candidates]
        db.commit()
        with ExitStack() as stack:
            session = None
            for player_id in ids:
                if time.monotonic() - started >= settings.SYNC_MAX_SECONDS:
                    result["deferred"] += len(ids) - result["players_processed"]
                    break
                did_work = False
                for source, interval in INTERVALS.items():
                    if time.monotonic() - started >= settings.SYNC_MAX_SECONDS:
                        result["deferred"] += 1
                        break
                    player = db.get(Player, player_id)
                    if player is None:
                        break  # removed while the worker was running
                    state = dict((player.sync_state or {}).get(source, {}))
                    now = datetime.now(timezone.utc)
                    if not _is_due(state, now):
                        continue
                    if failures[source] >= settings.SYNC_SOURCE_FAILURE_LIMIT:
                        result["deferred"] += 1
                        continue
                    renew_lease(db, owner)
                    db.commit()
                    did_work = True
                    try:
                        if source == "ratings":
                            if session is None:
                                session = stack.enter_context(sofascore.SofascoreSession())
                            ok = _refresh_ratings(db, player, session)
                        elif source == "stats":
                            ok = player_service._apply_transfermarkt_performance(db, player)
                        elif source == "market":
                            ok = player_service._backfill_market_value_history(db, player)
                        elif source == "transfers":
                            ok = _refresh_transfers(db, player) if player.transfermarkt_id else False
                        else:
                            ok = _refresh_links(db, player)
                        if not ok:
                            raise NoPlayerData("Nessun dato verificabile disponibile")
                        finished = datetime.now(timezone.utc)
                        state.update(last_attempt_at=now.isoformat(), last_success_at=finished.isoformat(),
                            next_attempt_at=(finished + timedelta(hours=interval)).isoformat(), error=None)
                        # Only an actual performance refresh marks the dashboard as fresh.
                        if source == "stats":
                            player.last_synced_at = finished
                        failures[source] = 0
                        result["succeeded"] += 1
                    except Exception as exc:
                        db.rollback()
                        player = db.get(Player, player_id)
                        if player is None:
                            break
                        # User-facing messages never contain URLs, credentials or tracebacks.
                        state.update(last_attempt_at=now.isoformat(),
                            next_attempt_at=(now + timedelta(hours=settings.SYNC_RETRY_HOURS)).isoformat(),
                            error=f"Dati non disponibili ({type(exc).__name__})")
                        # A missing player mapping is not a provider-wide outage.
                        failures[source] = failures[source] + 1 if not isinstance(exc, NoPlayerData) else 0
                        result["failed"] += 1
                        logger.warning("Aggiornamento %s fallito per player_id=%s (%s)", source, player_id, type(exc).__name__)
                    player.sync_state = {**(player.sync_state or {}), source: state}
                    player.sync_attempted_at = now
                    player.sync_status = _player_status(player)
                    renew_lease(db, owner)  # fencing: a stale worker cannot commit its data
                    db.commit()
                if did_work:
                    try:
                        player = db.get(Player, player_id)
                        if player is not None:
                            watch_alert_service.detect_alerts_for_player(db, player)
                            renew_lease(db, owner)
                            db.commit()
                    except Exception:
                        db.rollback()
                        result["failed"] += 1
                        logger.exception("Errore rilevamento alert per player_id=%s", player_id)
                result["players_processed"] += 1
        states = db.execute(select(Player.sync_state).join(Watchlist)).scalars().all()
        result["unresolved"] = sum(1 for state in states if any(
            not (state or {}).get(source, {}).get("last_success_at") or (state or {}).get(source, {}).get("error")
            for source in INTERVALS))
        has_success = result["succeeded"] or any(
            entry.get("last_success_at") for state in states for entry in (state or {}).values())
        result["status"] = (("partial" if has_success else "error")
            if result["failed"] or result["deferred"] or result["unresolved"] else "success")
        # Keep operational logs bounded; user notes and player histories are retained.
        db.execute(delete(DataSourceLog).where(DataSourceLog.run_at < datetime.now(timezone.utc) - timedelta(days=30)))
        db.add(DataSourceLog(job_name=LEASE_NAME, source="all", status=result["status"],
            message=f"Fonti aggiornate: {result['succeeded']}; errori: {result['failed']}; rinviati: {result['deferred']}; profili incompleti: {result['unresolved']}",
            players_processed=result["players_processed"], duration_ms=int((time.monotonic()-started)*1000)))
        db.commit()
        return result
    except Exception:
        db.rollback()
        logger.exception("Aggiornamento interrotto; i checkpoint completati sono conservati")
        raise
    finally:
        strict_scraping.reset(token)
        if acquired:
            try:
                release_lease(db, owner)
            except Exception:
                db.rollback()
                logger.exception("Rilascio lock fallito; scadra' automaticamente")
        db.close()
