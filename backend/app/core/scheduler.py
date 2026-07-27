import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.scrapers.jobs import run_nightly_update

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler() -> None:
    if not settings.ENABLE_SCHEDULER:
        logger.info("Scheduler disabilitato via ENABLE_SCHEDULER=false")
        return

    scheduler.add_job(
        run_nightly_update,
        trigger=CronTrigger(hour=settings.NIGHTLY_JOB_HOUR, minute=settings.NIGHTLY_JOB_MINUTE),
        id="nightly_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler avviato: job notturno alle %02d:%02d UTC",
        settings.NIGHTLY_JOB_HOUR,
        settings.NIGHTLY_JOB_MINUTE,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
