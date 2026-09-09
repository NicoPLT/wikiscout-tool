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


def test_retired_trigger_never_starts_a_background_thread(monkeypatch):
    monkeypatch.setattr(get_settings(), "NIGHTLY_JOB_SECRET", "correct-secret")
    def fail(*a, **k):
        raise AssertionError("No scraping threads may start on the web service")
    monkeypatch.setattr(threading, "Thread", fail)
    from app.api.routes_internal import trigger_nightly_job
    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException) as error:
        trigger_nightly_job("correct-secret")
    assert error.value.status_code == 410
