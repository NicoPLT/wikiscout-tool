import logging
import threading

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings
from app.scrapers.jobs import run_nightly_update

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/nightly-job", status_code=status.HTTP_202_ACCEPTED)
def trigger_nightly_job(x_job_secret: str | None = Header(default=None)) -> dict:
    """Innesca on-demand lo stesso giro di aggiornamento notturno di
    app/core/scheduler.py, per deploy dove il processo non resta acceso da
    solo (es. piano free di Render, che addormenta il servizio dopo
    inattivita': uno scheduler interno non si sveglierebbe all'orario
    giusto). Pensato per essere richiamato da un Cron Job esterno gratuito
    al posto dello scheduler interno — imposta ENABLE_SCHEDULER=false
    quando usi questo endpoint, altrimenti il giro rischia di partire due
    volte in parallelo.

    Autenticazione via header segreto (non il login utente normale: il
    chiamante e' un cron esterno, non uno scout loggato). Risponde subito
    (202) e fa girare il job in un thread separato, perche' un giro
    completo — scraping live di piu' fonti per tutta la watchlist — puo'
    richiedere diversi minuti, troppo per restare in attesa della risposta
    HTTP di un semplice trigger.
    """
    if not settings.NIGHTLY_JOB_SECRET:
        raise HTTPException(status_code=503, detail="NIGHTLY_JOB_SECRET non configurato")
    if x_job_secret != settings.NIGHTLY_JOB_SECRET:
        raise HTTPException(status_code=401, detail="Non autorizzato")

    thread = threading.Thread(target=run_nightly_update, daemon=True)
    thread.start()
    logger.info("Giro di aggiornamento notturno innescato via /internal/nightly-job")
    return {"status": "started"}
