import threading
import time

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _client():
    return TestClient(app)


def test_nightly_job_trigger_requires_secret_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "NIGHTLY_JOB_SECRET", None)
    resp = _client().post("/internal/nightly-job", headers={"X-Job-Secret": "anything"})
    assert resp.status_code == 503


def test_nightly_job_trigger_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "NIGHTLY_JOB_SECRET", "correct-secret")
    resp = _client().post("/internal/nightly-job", headers={"X-Job-Secret": "wrong-secret"})
    assert resp.status_code == 401


def test_nightly_job_trigger_rejects_missing_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "NIGHTLY_JOB_SECRET", "correct-secret")
    resp = _client().post("/internal/nightly-job")
    assert resp.status_code == 401


def test_nightly_job_trigger_starts_job_in_background(monkeypatch):
    monkeypatch.setattr(get_settings(), "NIGHTLY_JOB_SECRET", "correct-secret")

    started = threading.Event()

    def fake_run_nightly_update():
        started.set()

    monkeypatch.setattr("app.api.routes_internal.run_nightly_update", fake_run_nightly_update)

    t0 = time.monotonic()
    resp = _client().post("/internal/nightly-job", headers={"X-Job-Secret": "correct-secret"})
    elapsed = time.monotonic() - t0

    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}
    # La risposta torna subito, non aspetta il job (che qui e' istantaneo,
    # ma nella realta' puo' durare minuti: il punto e' che non blocca).
    assert elapsed < 1.0
    assert started.wait(timeout=2), "il job non e' stato eseguito in background"
