from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.base_class import Base
from app.db.session import get_db
from app.main import app
from app.models.data_source_log import DataSourceLog
from app.models.job_lease import JobLease
from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.user import User
from app.models.watchlist import Watchlist
from app.scrapers import jobs, transfermarkt_performance as tm
from app.scrapers.errors import SourceUnavailable
from app.services import player_service as ps, watch_alert_service as alerts
from app.services.backup_service import export_data, restore_data


def seed(db, count=1):
    user = User(email="audit@example.test", hashed_password="DO-NOT-EXPORT")
    db.add(user)
    db.flush()
    players = []
    for i in range(count):
        player = Player(full_name=f"Player {i}", transfermarkt_id=str(i+1), current_team="Test Club")
        db.add(player)
        db.flush()
        db.add(Watchlist(user_id=user.id, player_id=player.id, notes="My private notes", tags=["left-foot"]))
        players.append(player)
    db.commit()
    return user, players


def forbidden(*args, **kwargs):
    raise AssertionError("A read/import must not contact a scraper")


def test_http_import_and_profile_reads_are_database_only(db_session, monkeypatch):
    user, _ = seed(db_session, 0)
    for name in ("resolve_sofascore_link", "resolve_date_of_birth", "resolve_fotmob_link", "_apply_transfermarkt_performance", "_backfill_market_value_history"):
        monkeypatch.setattr(ps, name, forbidden)
    monkeypatch.setattr(tm, "get_all_games", forbidden)
    monkeypatch.setattr(tm, "get_transfer_history", forbidden)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.post("/api/watchlist/import", json={"transfermarkt_id":"900", "full_name":"New Player"})
        assert response.status_code == 201
        player_id = response.json()["id"]
        assert response.json()["last_synced_at"] is None
        assert response.json()["sync_status"] == "pending"
        for suffix in ("", "/seasons", "/transfers"):
            assert client.get(f"/api/players/{player_id}{suffix}").status_code == 200
        duplicate = client.post("/api/watchlist/import", json={"transfermarkt_id":"900", "full_name":"New Player"})
        assert duplicate.json()["id"] == player_id
    finally:
        app.dependency_overrides.clear()


def test_200_players_with_missing_metadata_do_not_scrape(db_session, monkeypatch):
    user, _ = seed(db_session, 200)
    monkeypatch.setattr(tm, "get_date_of_birth", forbidden)
    monkeypatch.setattr(ps, "resolve_date_of_birth", forbidden)
    for _ in range(2):
        assert len(ps.get_watchlist_rows(db_session, user.id, use_cache=False)) == 200


def test_market_snapshot_and_history_refresh_without_apify(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    player.market_value_eur = 1000000
    points = [tm.MarketValuePoint(recorded_at=date(2026, 1, 1), value_eur=1000000),
              tm.MarketValuePoint(recorded_at=date(2026, 9, 1), value_eur=2000000)]
    monkeypatch.setattr(tm, "get_market_value_history", lambda *a, **k: points)
    monkeypatch.setattr(ps.transfermarkt, "fetch_market_value", forbidden)
    assert ps._backfill_market_value_history(db_session, player)
    assert ps._backfill_market_value_history(db_session, player)
    assert float(player.market_value_eur) == 2000000
    assert float(player.market_value_change_pct) == 100
    assert player.market_value_updated_at.date() == date(2026, 9, 1)
    assert len(list(db_session.execute(select(PlayerMarketValueHistory)).scalars())) == 2


def test_sofascore_unavailable_does_not_overwrite_valid_link(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    player.sofascore_id = "123"
    player.rating_avg = 8
    monkeypatch.setattr(ps.sofascore, "get_season_stats", lambda *a: None)
    assert not ps._apply_sofascore_link(db_session, SimpleNamespace(ok=True), player, 999)
    assert player.sofascore_id == "123"
    assert player.rating_avg == 8
    assert not ps._apply_sofascore_link(db_session, SimpleNamespace(ok=False), player, 999)


def test_match_ratings_enable_alerts_without_duplicate_matches(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    rows = []
    for i in range(3):
        row = PlayerStatsMatch(player_id=player.id, match_date=date.today()-timedelta(days=i*7),
            competition="League", opponent="Other FC", is_home=True, minutes_played=90,
            source="transfermarkt-leistungsdaten", external_ref=f"tm-{i}")
        db_session.add(row)
        rows.append(row)
    db_session.commit()
    monkeypatch.setattr(ps.sofascore, "get_season_stats", lambda *a: {"rating_avg":8.2,"xg_season":1,"xa_season":None})
    fetch = Mock(return_value=[{"external_ref":f"ss-{i}", "match_date":row.match_date,
        "home_team":"Test Club", "away_team":"Other FC", "rating":8.5, "xg":0.5, "xa":None}
        for i, row in enumerate(rows)])
    monkeypatch.setattr(ps.sofascore, "get_recent_matches", fetch)
    assert ps._apply_sofascore_link(db_session, SimpleNamespace(ok=True), player, 123)
    db_session.commit()
    assert len(player.stats_matches) == 3
    assert alerts._detect_rating_streak(player.stats_matches, 7.5, 3)
    assert ps._apply_sofascore_link(db_session, SimpleNamespace(ok=True), player, 123)
    assert fetch.call_count == 1  # already rated matches do not generate another fetch


def test_ambiguous_match_is_not_assigned_a_rating(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    for i in range(2):
        db_session.add(PlayerStatsMatch(player_id=player.id, match_date=date.today(), competition="League",
            opponent="Other FC", is_home=True, source="transfermarkt-leistungsdaten", external_ref=str(i)))
    db_session.commit()
    monkeypatch.setattr(ps.sofascore, "get_season_stats", lambda *a: {"rating_avg":8})
    monkeypatch.setattr(ps.sofascore, "get_recent_matches", lambda *a, **k: [dict(external_ref="ss",match_date=date.today(),away_team="Other FC",rating=9)])
    assert ps._apply_sofascore_link(db_session, SimpleNamespace(ok=True), player, 123)
    assert all(row.rating is None for row in player.stats_matches)


def worker_stubs(monkeypatch, db):
    monkeypatch.setattr(jobs, "SessionLocal", sessionmaker(bind=db.bind))
    monkeypatch.setattr(jobs, "_refresh_links", lambda *a: True)
    monkeypatch.setattr(jobs, "_refresh_transfers", lambda *a: True)
    monkeypatch.setattr(ps, "_backfill_market_value_history", lambda *a: True)
    monkeypatch.setattr(ps, "_apply_transfermarkt_performance", lambda *a: True)
    monkeypatch.setattr(jobs, "_refresh_ratings", lambda *a: True)
    session = Mock()
    session.__enter__ = Mock(return_value=SimpleNamespace(ok=True))
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(jobs.sofascore, "SofascoreSession", lambda: session)


def test_worker_resumes_and_preserves_last_good_data(db_session, monkeypatch):
    _, players = seed(db_session, 2)
    worker_stubs(monkeypatch, db_session)
    calls = []
    def stats(db, player):
        calls.append(player.id)
        if player.id == players[0].id:
            raise SourceUnavailable("offline")
        player.goals_season = 7
        return True
    monkeypatch.setattr(ps, "_apply_transfermarkt_performance", stats)
    result = jobs.run_nightly_update()
    db_session.expire_all()
    assert result["status"] == "partial"
    assert players[0].last_synced_at is None
    assert players[0].sync_state["stats"]["error"]
    assert players[1].last_synced_at is not None
    assert players[1].goals_season == 7
    assert jobs.run_nightly_update()["status"] == "partial"
    assert len(calls) == 2  # successful sources and failures both respect retry dates


def test_source_outage_is_bounded_and_other_sources_continue(db_session, monkeypatch):
    seed(db_session, 6)
    worker_stubs(monkeypatch, db_session)
    fetch = Mock(side_effect=SourceUnavailable("offline"))
    monkeypatch.setattr(ps, "_apply_transfermarkt_performance", fetch)
    result = jobs.run_nightly_update()
    assert fetch.call_count == get_settings().SYNC_SOURCE_FAILURE_LIMIT
    assert result["deferred"] > 0
    assert result["succeeded"] == 6 * 4


def test_transfermarkt_accepts_null_season_metadata(monkeypatch):
    game = {
        "gameInformation": {
            "gameId": "match-1", "competitionId": "BRA1", "seasonId": 2025,
            "season": None, "date": {"dateTimeUTC": "2026-09-05T00:00:00Z"},
            "isNationalGame": False, "isGamePostponed": False,
        },
        "clubsInformation": {
            "club": {"clubId": "10010", "venue": "home"},
            "opponent": {"clubId": "8793"},
        },
        "statistics": {
            "generalStatistics": {"participationState": "played"},
            "playingTimeStatistics": {"playedMinutes": 90, "isStarting": True},
            "goalStatistics": {"goalsScoredTotal": 1, "assists": 0},
            "cardStatistics": {},
        },
    }
    monkeypatch.setattr(tm, "get_all_games", lambda player_id: [game])
    monkeypatch.setattr(tm, "get_club_primary_competition", lambda club_id: "BRA1")
    monkeypatch.setattr(tm, "resolve_competition_names", lambda ids: {"BRA1": "Serie A"})
    monkeypatch.setattr(tm, "resolve_club_names", lambda ids: {"10010": "Bahia"})

    summary = tm.list_season_options("676035", "10010")[0]
    assert summary.season_label == "2025"
    assert summary.goals == 1


def test_worker_rolls_back_one_failed_source_and_continues(db_session, monkeypatch):
    _, players = seed(db_session, 2)
    first_id = players[0].id
    worker_stubs(monkeypatch, db_session)
    def stats(db, player):
        if player.id == first_id:
            db.add(PlayerStatsMatch(player_id=player.id))  # invalid required date
            db.flush()
        player.goals_season = 9
        return True
    monkeypatch.setattr(ps, "_apply_transfermarkt_performance", stats)
    result = jobs.run_nightly_update()
    db_session.expire_all()
    assert result["status"] == "partial"
    assert players[0].goals_season == 0
    assert players[1].goals_season == 9
    assert db_session.execute(select(DataSourceLog)).scalar_one().status == "partial"


def test_all_failed_sources_never_mark_player_fresh(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    worker_stubs(monkeypatch, db_session)
    for owner, name in ((ps,"_apply_transfermarkt_performance"),(ps,"_backfill_market_value_history"),
        (jobs,"_refresh_links"),(jobs,"_refresh_transfers"),(jobs,"_refresh_ratings")):
        monkeypatch.setattr(owner,name,lambda *a: False)
    assert jobs.run_nightly_update()["status"] == "error"
    db_session.refresh(player)
    assert player.last_synced_at is None
    assert player.sync_status == "error"


def test_lock_rejects_overlap_and_recovers_after_expiry(db_session):
    assert jobs.acquire_lease(db_session, "one")
    assert not jobs.acquire_lease(db_session, "two")
    lease = db_session.get(JobLease, jobs.LEASE_NAME)
    lease.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    assert jobs.acquire_lease(db_session, "two")
    with pytest.raises(RuntimeError):
        jobs.renew_lease(db_session, "one")
    jobs.release_lease(db_session, "one")
    db_session.expire_all()
    assert db_session.get(JobLease,jobs.LEASE_NAME).owner == "two"


def test_time_budget_stops_before_any_scraping(db_session, monkeypatch):
    seed(db_session, 2)
    worker_stubs(monkeypatch, db_session)
    monkeypatch.setattr(get_settings(), "SYNC_MAX_SECONDS", 0)
    monkeypatch.setattr(ps, "_apply_transfermarkt_performance", forbidden)
    assert jobs.run_nightly_update()["deferred"] == 2


def test_export_and_restore_preserve_notes_without_credentials(db_session, monkeypatch):
    user, (player,) = seed(db_session)
    payload = export_data(db_session)
    import json
    assert "DO-NOT-EXPORT" not in json.dumps(payload)
    assert "hashed_password" not in payload["tables"]["users"][0]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as target:
        monkeypatch.setattr(get_settings(), "AUTH_PASSWORD_HASH", "new-hash")
        restore_data(target, payload)
        entry = target.execute(select(Watchlist)).scalar_one()
        assert entry.notes == "My private notes"
        assert entry.tags == ["left-foot"]
        assert target.get(Player,player.id).full_name == player.full_name
        assert target.execute(select(User)).scalar_one().hashed_password == "new-hash"
        with pytest.raises(ValueError, match="vuoto"):
            restore_data(target, payload)
    engine.dispose()


def test_export_requires_login():
    assert TestClient(app).get("/api/watchlist/export").status_code == 401


def test_transfer_alert_uses_cached_history_without_network(db_session, monkeypatch):
    _, (player,) = seed(db_session)
    transfer = tm.TransferRecord(transfer_id="t1",transfer_date=date.today(),club_from_name="Old",club_to_name="New")
    player.transfers_data = [transfer.model_dump(mode="json")]
    monkeypatch.setattr(tm,"get_transfer_history",forbidden)
    created = alerts.detect_alerts_for_player(db_session,player)
    assert len(created) == 1 and created[0].trigger_type.value == "recent_transfer"


@pytest.mark.parametrize("value", ["https://example.com/player/test/123", "abc123", "0", "https://www.sofascore.com/team/test/123"])
def test_manual_sofascore_rejects_invalid_url_before_network(db_session, monkeypatch, value):
    user, (player,) = seed(db_session)
    monkeypatch.setattr(ps.sofascore,"SofascoreSession",forbidden)
    assert ps.link_sofascore_manual(db_session,user.id,player.id,value) is None


def test_backup_cli_encryption_and_restore_round_trip(db_session, monkeypatch, tmp_path):
    import sys
    from cryptography.fernet import Fernet, InvalidToken
    from app.db import session as db_module
    from scripts import backup
    seed(db_session)
    monkeypatch.setattr(db_module,"SessionLocal",sessionmaker(bind=db_session.bind))
    key = Fernet.generate_key()
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY",key.decode())
    path=tmp_path / "snapshot.enc"
    monkeypatch.setattr(sys,"argv",["backup.py","--output",str(path)])
    backup.main()
    assert b"My private notes" not in path.read_bytes()
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db_module,"SessionLocal",sessionmaker(bind=engine))
    monkeypatch.setattr(get_settings(),"AUTH_PASSWORD_HASH","restored-hash")
    monkeypatch.setattr(sys,"argv",["backup.py","--restore",str(path)])
    backup.main()
    with sessionmaker(bind=engine)() as restored:
        assert restored.execute(select(Watchlist)).scalar_one().notes == "My private notes"
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY",Fernet.generate_key().decode())
    with pytest.raises(InvalidToken):
        backup.main()
    engine.dispose()


def test_migration_preserves_existing_rows_and_initializes_checkpoints():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).resolve().parents[1] / "alembic/versions/0008_free_sync.py"
    spec=importlib.util.spec_from_file_location("migration_free_sync",path)
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine=create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE players (id INTEGER PRIMARY KEY, full_name TEXT)"))
        connection.execute(text("INSERT INTO players VALUES (1, 'Existing Player')"))
        connection.execute(text("CREATE TABLE player_stats_matches (id INTEGER PRIMARY KEY)"))
        migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade()
        row=connection.execute(text("SELECT full_name, sync_status, sync_state, seasons_data FROM players")).one()
        assert tuple(row) == ("Existing Player","pending","{}","[]")
        assert connection.execute(text("SELECT name FROM job_leases")).scalar_one() == "nightly_update"
    engine.dispose()


def test_network_errors_are_not_reported_as_successful_empty_history(monkeypatch):
    import httpx
    from app.scrapers.errors import strict_scraping
    monkeypatch.setattr(tm,"_get",Mock(side_effect=httpx.ConnectError("offline")))
    token=strict_scraping.set(True)
    try:
        with pytest.raises(httpx.ConnectError):
            tm.get_market_value_history("1")
        with pytest.raises(httpx.ConnectError):
            tm.get_transfer_history("1")
    finally:
        strict_scraping.reset(token)
