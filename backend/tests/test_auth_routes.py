from fastapi.testclient import TestClient
import pytest

from app.api import routes_auth
from app.core.security import decode_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.fixture()
def auth_client(db_session, monkeypatch):
    email = "login-test@example.com"
    monkeypatch.setattr(routes_auth.settings, "AUTH_EMAIL", email)
    db_session.add(User(email=email, hashed_password=hash_password("test-password")))
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_login_returns_verified_identity_without_second_request(auth_client):
    response = auth_client.post("/api/auth/login", json={
        "email": "login-test@example.com", "password": "test-password",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "login-test@example.com"
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == body["email"]
    me = auth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {"email": body["email"]}


def test_invalid_login_does_not_return_identity_or_token(auth_client):
    response = auth_client.post("/api/auth/login", json={
        "email": "login-test@example.com", "password": "wrong-password",
    })
    assert response.status_code == 401
    assert "email" not in response.json()
    assert "access_token" not in response.json()
