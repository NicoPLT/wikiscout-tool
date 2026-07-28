from datetime import date, timedelta

from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.user import User
from app.models.watch_alert import PlayerWatchAlert, WatchAlertTriggerType
from app.models.watchlist import Watchlist
from app.scrapers.transfermarkt_performance import TransferRecord
from app.services import watch_alert_service as svc

RATING_THRESHOLD = 7.5
STREAK_LEN = 2
TRANSFER_DAYS = 30
SPIKE_PCT = 20.0
SPIKE_WINDOW_DAYS = 60


def _match(days_ago: int, *, rating=None, goals=0, assists=0):
    return PlayerStatsMatch(
        match_date=date.today() - timedelta(days=days_ago),
        competition="Serie A",
        minutes_played=90,
        goals=goals,
        assists=assists,
        rating=rating,
    )


# --- _detect_rating_streak -------------------------------------------------


def test_rating_streak_triggers_at_exact_threshold():
    # Caso limite esplicitamente richiesto: rating esattamente 7.5 su
    # entrambe le ultime 2 partite deve contare come trigger (">=", non ">").
    matches = [_match(0, rating=7.5), _match(3, rating=7.5), _match(7, rating=9.0)]
    detail = svc._detect_rating_streak(matches, RATING_THRESHOLD, STREAK_LEN)
    assert detail is not None
    assert "7.5" in detail


def test_rating_streak_does_not_trigger_if_one_match_below_threshold():
    matches = [_match(0, rating=7.5), _match(3, rating=7.4)]
    assert svc._detect_rating_streak(matches, RATING_THRESHOLD, STREAK_LEN) is None


def test_rating_streak_does_not_trigger_with_missing_rating():
    matches = [_match(0, rating=8.0), _match(3, rating=None)]
    assert svc._detect_rating_streak(matches, RATING_THRESHOLD, STREAK_LEN) is None


def test_rating_streak_does_not_trigger_with_fewer_matches_than_required():
    matches = [_match(0, rating=9.0)]
    assert svc._detect_rating_streak(matches, RATING_THRESHOLD, STREAK_LEN) is None


# --- _detect_goal_streak / _detect_assist_streak ---------------------------


def test_goal_streak_triggers_with_a_goal_in_each_recent_match():
    matches = [_match(0, goals=1), _match(3, goals=2), _match(7, goals=0)]
    assert svc._detect_goal_streak(matches, STREAK_LEN) is not None


def test_goal_streak_does_not_trigger_if_any_recent_match_has_no_goal():
    matches = [_match(0, goals=1), _match(3, goals=0)]
    assert svc._detect_goal_streak(matches, STREAK_LEN) is None


def test_assist_streak_triggers_with_an_assist_in_each_recent_match():
    matches = [_match(0, assists=1), _match(3, assists=1)]
    assert svc._detect_assist_streak(matches, STREAK_LEN) is not None


def test_assist_streak_does_not_trigger_if_any_recent_match_has_no_assist():
    matches = [_match(0, assists=1), _match(3, assists=0)]
    assert svc._detect_assist_streak(matches, STREAK_LEN) is None


# --- _detect_market_value_spike ---------------------------------------------


def _mv(days_ago: int, value: float):
    return PlayerMarketValueHistory(
        value_eur=value, recorded_at=date.today() - timedelta(days=days_ago), source="test"
    )


def test_market_value_spike_triggers_above_threshold():
    history = [_mv(90, 10_000_000), _mv(61, 10_000_000), _mv(0, 13_000_000)]  # +30%
    detail = svc._detect_market_value_spike(history, SPIKE_WINDOW_DAYS, SPIKE_PCT)
    assert detail is not None
    assert "+30%" in detail


def test_market_value_spike_does_not_trigger_at_exact_threshold():
    # "superiore a" (>) una soglia: esattamente +20% non deve scattare.
    history = [_mv(61, 10_000_000), _mv(0, 12_000_000)]  # esattamente +20%
    assert svc._detect_market_value_spike(history, SPIKE_WINDOW_DAYS, SPIKE_PCT) is None


def test_market_value_spike_does_not_trigger_without_enough_history():
    history = [_mv(5, 10_000_000), _mv(0, 13_000_000)]  # nessun punto vecchio >= 60gg
    assert svc._detect_market_value_spike(history, SPIKE_WINDOW_DAYS, SPIKE_PCT) is None


def test_market_value_spike_does_not_trigger_on_decrease():
    history = [_mv(61, 10_000_000), _mv(0, 8_000_000)]
    assert svc._detect_market_value_spike(history, SPIKE_WINDOW_DAYS, SPIKE_PCT) is None


# --- _detect_recent_transfer -------------------------------------------------


def _transfer(days_ago: int):
    return TransferRecord(
        transfer_id="1",
        transfer_date=date.today() - timedelta(days=days_ago),
        club_from_name="Club A",
        club_to_name="Club B",
    )


def test_recent_transfer_triggers_within_window():
    detail = svc._detect_recent_transfer([_transfer(10)], TRANSFER_DAYS, date.today())
    assert detail is not None
    assert "Club A" in detail and "Club B" in detail


def test_recent_transfer_triggers_at_exact_boundary_day():
    detail = svc._detect_recent_transfer([_transfer(TRANSFER_DAYS)], TRANSFER_DAYS, date.today())
    assert detail is not None


def test_recent_transfer_does_not_trigger_past_window():
    assert svc._detect_recent_transfer([_transfer(TRANSFER_DAYS + 1)], TRANSFER_DAYS, date.today()) is None


def test_recent_transfer_does_not_trigger_with_no_transfers():
    assert svc._detect_recent_transfer([], TRANSFER_DAYS, date.today()) is None


# --- orchestrator: detect_alerts_for_player + dedup -------------------------


def _seed_watchlisted_player(db_session, **player_kwargs) -> Player:
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()

    player = Player(full_name="Test Player", current_team="Test FC", **player_kwargs)
    db_session.add(player)
    db_session.flush()

    db_session.add(Watchlist(user_id=user.id, player_id=player.id))
    db_session.commit()
    return player


def test_orchestrator_creates_alert_for_triggered_criterion(db_session):
    player = _seed_watchlisted_player(db_session)
    for m in (_match(0, rating=8.0, goals=1), _match(3, rating=8.0, goals=1)):
        m.player_id = player.id
        db_session.add(m)
    db_session.commit()
    db_session.refresh(player)

    created = svc.detect_alerts_for_player(db_session, player)
    db_session.commit()

    trigger_types = {a.trigger_type for a in created}
    assert WatchAlertTriggerType.rating_streak in trigger_types
    assert WatchAlertTriggerType.goal_streak in trigger_types


def test_orchestrator_does_not_create_duplicate_alert_across_two_nightly_runs(db_session):
    """Punto 8: far girare il job due notti di fila con dati che
    soddisfano lo stesso criterio non deve creare due alert identici."""
    player = _seed_watchlisted_player(db_session)
    for m in (_match(0, rating=8.0), _match(3, rating=8.0)):
        m.player_id = player.id
        db_session.add(m)
    db_session.commit()
    db_session.refresh(player)

    first_run = svc.detect_alerts_for_player(db_session, player)
    db_session.commit()
    assert len(first_run) == 1

    # Seconda notte: la serie e' ancora valida (nessun nuovo dato che la
    # interrompe) -> non deve ricreare l'alert gia' attivo.
    second_run = svc.detect_alerts_for_player(db_session, player)
    db_session.commit()
    assert second_run == []

    active_alerts = (
        db_session.query(PlayerWatchAlert)
        .filter(PlayerWatchAlert.player_id == player.id, PlayerWatchAlert.trigger_type == WatchAlertTriggerType.rating_streak)
        .all()
    )
    assert len(active_alerts) == 1


def test_orchestrator_recreates_alert_after_dismissal(db_session):
    """Un alert scartato non deve piu' contare come 'attivo' ai fini della
    dedup: se il criterio e' ancora vero, puo' essere ri-creato."""
    player = _seed_watchlisted_player(db_session)
    for m in (_match(0, rating=8.0), _match(3, rating=8.0)):
        m.player_id = player.id
        db_session.add(m)
    db_session.commit()
    db_session.refresh(player)

    first_run = svc.detect_alerts_for_player(db_session, player)
    db_session.commit()
    assert len(first_run) == 1

    first_run[0].is_dismissed = True
    db_session.commit()

    second_run = svc.detect_alerts_for_player(db_session, player)
    db_session.commit()
    assert len(second_run) == 1


def test_orchestrator_no_alerts_when_no_criteria_met(db_session):
    player = _seed_watchlisted_player(db_session)
    m = _match(0, rating=6.0, goals=0, assists=0)
    m.player_id = player.id
    db_session.add(m)
    db_session.commit()
    db_session.refresh(player)

    assert svc.detect_alerts_for_player(db_session, player) == []


# --- manual alerts -----------------------------------------------------------


def test_create_manual_alert(db_session):
    player = _seed_watchlisted_player(db_session)

    alert = svc.create_manual_alert(db_session, player.id, "Visto dal vivo, impressionante nell'uno contro uno")

    assert alert.id is not None
    assert alert.trigger_type is None
    assert alert.is_manual is True
    assert alert.is_dismissed is False
    assert "impressionante" in alert.trigger_detail


def test_manual_alerts_are_never_deduplicated(db_session):
    player = _seed_watchlisted_player(db_session)

    svc.create_manual_alert(db_session, player.id, "Nota 1")
    svc.create_manual_alert(db_session, player.id, "Nota 1")

    manual_alerts = (
        db_session.query(PlayerWatchAlert).filter(PlayerWatchAlert.player_id == player.id, PlayerWatchAlert.is_manual.is_(True)).all()
    )
    assert len(manual_alerts) == 2


# --- list / dismiss / unseen count ------------------------------------------


def test_list_active_alerts_excludes_dismissed(db_session):
    player = _seed_watchlisted_player(db_session)
    user_id = db_session.query(Watchlist).filter(Watchlist.player_id == player.id).first().user_id

    active = svc.create_manual_alert(db_session, player.id, "attivo")
    dismissed = svc.create_manual_alert(db_session, player.id, "scartato")
    dismissed.is_dismissed = True
    db_session.commit()

    results = svc.list_active_alerts(db_session, user_id)
    ids = {a.id for a in results}
    assert active.id in ids
    assert dismissed.id not in ids


def test_dismiss_alert_marks_dismissed_and_scopes_by_user(db_session):
    player = _seed_watchlisted_player(db_session)
    user_id = db_session.query(Watchlist).filter(Watchlist.player_id == player.id).first().user_id
    alert = svc.create_manual_alert(db_session, player.id, "nota")

    ok = svc.dismiss_alert(db_session, user_id, alert.id)
    assert ok is True

    db_session.refresh(alert)
    assert alert.is_dismissed is True

    # utente inesistente/non proprietario -> non trovato
    assert svc.dismiss_alert(db_session, user_id + 999, alert.id) is False


def test_count_and_mark_unseen_alerts(db_session):
    player = _seed_watchlisted_player(db_session)
    user_id = db_session.query(Watchlist).filter(Watchlist.player_id == player.id).first().user_id

    svc.create_manual_alert(db_session, player.id, "nota 1")
    svc.create_manual_alert(db_session, player.id, "nota 2")

    assert svc.count_unseen_alerts(db_session, user_id) == 2

    svc.mark_all_seen(db_session, user_id)
    assert svc.count_unseen_alerts(db_session, user_id) == 0
