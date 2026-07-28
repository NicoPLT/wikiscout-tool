from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.player import Player
from app.models.user import User
from app.models.watch_alert import WatchAlertTriggerType
from app.models.watchlist import Watchlist
from app.services import watch_alert_service as svc


def _client(db_session):
    def _override_get_db():
        yield db_session

    user = db_session.query(User).first()

    def _override_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    return TestClient(app)


def test_get_watch_alerts_serializes_trigger_type_as_plain_string(db_session):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    player = Player(full_name="Test Player", current_team="Test FC")
    db_session.add(player)
    db_session.flush()
    db_session.add(Watchlist(user_id=user.id, player_id=player.id))
    db_session.commit()

    from app.models.watch_alert import PlayerWatchAlert

    db_session.add(
        PlayerWatchAlert(
            player_id=player.id,
            trigger_type=WatchAlertTriggerType.rating_streak,
            trigger_detail=">= 7.5 nelle ultime 2 partite",
        )
    )
    db_session.commit()

    client = _client(db_session)
    resp = client.get("/api/watch-alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    # deve serializzare il VALORE dell'enum ("rating_streak"), non la sua
    # rappresentazione Python ("WatchAlertTriggerType.rating_streak").
    assert data[0]["trigger_type"] == "rating_streak"
    assert data[0]["player"]["full_name"] == "Test Player"

    app.dependency_overrides.clear()


def test_dismiss_watch_alert_via_api(db_session):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    player = Player(full_name="Test Player", current_team="Test FC")
    db_session.add(player)
    db_session.flush()
    db_session.add(Watchlist(user_id=user.id, player_id=player.id))
    db_session.commit()

    alert = svc.create_manual_alert(db_session, user.id, player.id, "nota")

    client = _client(db_session)
    resp = client.post(f"/api/watch-alerts/{alert.id}/dismiss")
    assert resp.status_code == 204

    resp = client.get("/api/watch-alerts")
    assert resp.json() == []

    app.dependency_overrides.clear()


def test_dismiss_unknown_alert_returns_404(db_session):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()

    client = _client(db_session)
    resp = client.post("/api/watch-alerts/999999/dismiss")
    assert resp.status_code == 404

    app.dependency_overrides.clear()


def test_create_manual_watch_alert_via_api_adds_to_watchlist(db_session):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    player = Player(full_name="Nuovo Talento", current_team="Test FC")
    db_session.add(player)
    db_session.commit()

    client = _client(db_session)
    resp = client.post("/api/watch-alerts", json={"player_id": player.id, "note": "Visto dal vivo"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["trigger_type"] is None
    assert data["is_manual"] is True
    assert data["trigger_detail"] == "Visto dal vivo"
    assert data["player"]["full_name"] == "Nuovo Talento"

    assert db_session.query(Watchlist).filter(Watchlist.player_id == player.id, Watchlist.user_id == user.id).first() is not None

    app.dependency_overrides.clear()


def test_create_manual_watch_alert_unknown_player_returns_404(db_session):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()

    client = _client(db_session)
    resp = client.post("/api/watch-alerts", json={"player_id": 999999, "note": "nota"})
    assert resp.status_code == 404

    app.dependency_overrides.clear()
