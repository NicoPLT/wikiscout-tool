import secrets
from fastapi import APIRouter, Header, HTTPException
from app.core.config import get_settings

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/nightly-job")
def trigger_nightly_job(x_job_secret: str | None = Header(default=None)):
    """Legacy trigger retired: run the worker itself in GitHub Actions.

    Returning 202 here used to leave a non-durable thread on Render Free.
    An explicit error prevents old cron clients reporting a false success.
    """
    configured = get_settings().NIGHTLY_JOB_SECRET
    if not configured:
        raise HTTPException(status_code=503, detail="Trigger HTTP disattivato: usare GitHub Actions")
    if not x_job_secret or not secrets.compare_digest(x_job_secret, configured):
        raise HTTPException(status_code=401, detail="Non autorizzato")
    raise HTTPException(status_code=410, detail="Eseguire scripts/run_nightly.py con GitHub Actions")
