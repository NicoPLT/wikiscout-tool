"""'One to Watch': segnalazioni automatiche su chi-tra-i-giocatori-gia'-in-
watchlist sta performando meglio del solito, valutate a fine job notturno
(dopo che partite/valore di mercato sono gia' stati aggiornati per il giro).

Non e' scoperta di nuovi giocatori nel mondo: analizza solo la watchlist
gia' esistente, per gli stessi limiti di rate-limit su Transfermarkt/
Sofascore che hanno guidato tutta l'architettura di scraping del progetto.

Le funzioni `_detect_*` sono pure (nessun accesso a DB/rete): prendono in
input i dati gia' caricati e le soglie esplicite, cosi' sono testabili senza
dover costruire un giro completo del job. Solo `detect_alerts_for_player`
fa I/O (query DB per la dedup, chiamata Transfermarkt per i trasferimenti).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.watch_alert import PlayerWatchAlert, WatchAlertTriggerType
from app.models.watchlist import Watchlist
from app.scrapers import transfermarkt_performance

logger = logging.getLogger(__name__)
settings = get_settings()


def _detect_rating_streak(
    matches: Sequence[PlayerStatsMatch], threshold: float, streak_len: int
) -> str | None:
    """`matches` gia' ordinate piu' recente prima. Richiede le prime
    `streak_len` partite TUTTE con rating valorizzato e >= soglia."""
    if len(matches) < streak_len:
        return None
    recent = matches[:streak_len]
    if all(m.rating is not None and float(m.rating) >= threshold for m in recent):
        return f"Rating Sofascore >= {threshold:g} nelle ultime {streak_len} partite consecutive"
    return None


def _detect_goal_streak(matches: Sequence[PlayerStatsMatch], streak_len: int) -> str | None:
    if len(matches) < streak_len:
        return None
    recent = matches[:streak_len]
    if all((m.goals or 0) >= 1 for m in recent):
        return f"Almeno 1 goal in ciascuna delle ultime {streak_len} partite consecutive"
    return None


def _detect_assist_streak(matches: Sequence[PlayerStatsMatch], streak_len: int) -> str | None:
    if len(matches) < streak_len:
        return None
    recent = matches[:streak_len]
    if all((m.assists or 0) >= 1 for m in recent):
        return f"Almeno 1 assist in ciascuna delle ultime {streak_len} partite consecutive"
    return None


def _detect_market_value_spike(
    history: Sequence[PlayerMarketValueHistory], window_days: int, pct_threshold: float
) -> str | None:
    """Confronta l'ultima rilevazione con quella piu' recente disponibile
    che risalga ad almeno `window_days` fa. Se non c'e' abbastanza storico
    per coprire la finestra, non valuta (nessun falso positivo su dati
    incompleti)."""
    if len(history) < 2:
        return None
    ordered = sorted(history, key=lambda h: h.recorded_at)
    latest = ordered[-1]
    cutoff = latest.recorded_at - timedelta(days=window_days)
    reference_candidates = [h for h in ordered if h.recorded_at <= cutoff]
    if not reference_candidates:
        return None
    reference = reference_candidates[-1]

    reference_value = float(reference.value_eur)
    if reference_value <= 0:
        return None

    pct_change = (float(latest.value_eur) - reference_value) / reference_value * 100
    if pct_change > pct_threshold:
        return f"+{pct_change:.0f}% negli ultimi {window_days} giorni"
    return None


def _detect_recent_transfer(
    transfers: Sequence["transfermarkt_performance.TransferRecord"], days: int, today: date
) -> str | None:
    if not transfers:
        return None
    most_recent = max(transfers, key=lambda t: t.transfer_date)
    if (today - most_recent.transfer_date).days > days:
        return None
    origin = most_recent.club_from_name or "N/D"
    destination = most_recent.club_to_name or "N/D"
    return f"Trasferimento il {most_recent.transfer_date.isoformat()} ({origin} -> {destination})"


def detect_alerts_for_player(db: Session, player: Player, today: date | None = None) -> list[PlayerWatchAlert]:
    """Valuta tutti i criteri per `player` e crea una riga in
    player_watch_alerts per ogni criterio soddisfatto che non ha gia' un
    alert attivo (non scartato) dello stesso trigger_type: evita di
    ricreare un alert ogni notte finche' lo scout non lo scarta, anche se
    nel frattempo il dettaglio testuale cambierebbe (es. lo streak si
    allunga da 2 a 3 partite)."""
    today = today or date.today()

    matches = sorted(player.stats_matches, key=lambda m: m.match_date, reverse=True)
    history = list(player.market_value_history)

    candidates: list[tuple[WatchAlertTriggerType, str]] = []

    detail = _detect_rating_streak(matches, settings.WATCH_ALERT_RATING_THRESHOLD, settings.WATCH_ALERT_STREAK_MATCHES)
    if detail:
        candidates.append((WatchAlertTriggerType.rating_streak, detail))

    detail = _detect_goal_streak(matches, settings.WATCH_ALERT_STREAK_MATCHES)
    if detail:
        candidates.append((WatchAlertTriggerType.goal_streak, detail))

    detail = _detect_assist_streak(matches, settings.WATCH_ALERT_STREAK_MATCHES)
    if detail:
        candidates.append((WatchAlertTriggerType.assist_streak, detail))

    detail = _detect_market_value_spike(
        history, settings.WATCH_ALERT_MARKET_VALUE_WINDOW_DAYS, settings.WATCH_ALERT_MARKET_VALUE_SPIKE_PCT
    )
    if detail:
        candidates.append((WatchAlertTriggerType.market_value_spike, detail))

    if player.transfermarkt_id:
        try:
            transfers = transfermarkt_performance.get_transfer_history(player.transfermarkt_id)
        except Exception:  # noqa: BLE001 - un problema sui trasferimenti non deve bloccare gli altri criteri
            logger.exception("Errore fetch storico trasferimenti per player_id=%s", player.id)
            transfers = []
        detail = _detect_recent_transfer(transfers, settings.WATCH_ALERT_RECENT_TRANSFER_DAYS, today)
        if detail:
            candidates.append((WatchAlertTriggerType.recent_transfer, detail))

    if not candidates:
        return []

    existing_active_types = set(
        db.execute(
            select(PlayerWatchAlert.trigger_type).where(
                PlayerWatchAlert.player_id == player.id,
                PlayerWatchAlert.is_dismissed.is_(False),
                PlayerWatchAlert.trigger_type.is_not(None),
            )
        ).scalars()
    )

    created: list[PlayerWatchAlert] = []
    for trigger_type, detail_text in candidates:
        if trigger_type in existing_active_types:
            continue
        alert = PlayerWatchAlert(
            player_id=player.id,
            trigger_type=trigger_type,
            trigger_detail=detail_text,
            is_manual=False,
        )
        db.add(alert)
        created.append(alert)

    return created


def create_manual_alert(db: Session, player_id: int, note: str) -> PlayerWatchAlert:
    """Segnalazione aggiunta a mano dallo scout (punto 5): trigger_type=None
    identifica sempre una segnalazione manuale, a prescindere dai criteri
    automatici."""
    alert = PlayerWatchAlert(
        player_id=player_id,
        trigger_type=None,
        trigger_detail=note,
        is_manual=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_active_alerts(db: Session, user_id: int) -> list[PlayerWatchAlert]:
    """Alert attivi (non scartati) per i giocatori nella watchlist di
    questo utente, piu' recenti prima."""
    stmt = (
        select(PlayerWatchAlert)
        .join(Watchlist, Watchlist.player_id == PlayerWatchAlert.player_id)
        .where(Watchlist.user_id == user_id, PlayerWatchAlert.is_dismissed.is_(False))
        .options(selectinload(PlayerWatchAlert.player))
        .order_by(PlayerWatchAlert.detected_at.desc())
    )
    return list(db.execute(stmt).scalars().unique().all())


def count_unseen_alerts(db: Session, user_id: int) -> int:
    stmt = (
        select(func.count(PlayerWatchAlert.id))
        .select_from(PlayerWatchAlert)
        .join(Watchlist, Watchlist.player_id == PlayerWatchAlert.player_id)
        .where(
            Watchlist.user_id == user_id,
            PlayerWatchAlert.is_dismissed.is_(False),
            PlayerWatchAlert.is_seen.is_(False),
        )
    )
    return db.execute(stmt).scalar_one()


def mark_all_seen(db: Session, user_id: int) -> None:
    ids = list(
        db.execute(
            select(PlayerWatchAlert.id)
            .join(Watchlist, Watchlist.player_id == PlayerWatchAlert.player_id)
            .where(Watchlist.user_id == user_id, PlayerWatchAlert.is_seen.is_(False))
        ).scalars()
    )
    if not ids:
        return
    db.execute(update(PlayerWatchAlert).where(PlayerWatchAlert.id.in_(ids)).values(is_seen=True))
    db.commit()


def dismiss_alert(db: Session, user_id: int, alert_id: int) -> bool:
    """True se l'alert esiste ed appartiene (tramite watchlist) a questo
    utente. Non elimina la riga: resta in DB per storico/audit."""
    stmt = (
        select(PlayerWatchAlert)
        .join(Watchlist, Watchlist.player_id == PlayerWatchAlert.player_id)
        .where(PlayerWatchAlert.id == alert_id, Watchlist.user_id == user_id)
    )
    alert = db.execute(stmt).scalars().first()
    if alert is None:
        return False
    alert.is_dismissed = True
    db.commit()
    return True
