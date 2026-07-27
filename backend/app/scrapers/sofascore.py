"""Scraping mirato del rating post-partita (Sofascore/Fotmob), via Apify actor.

Spento finche' APIFY_TOKEN non e' configurato.
"""

import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.player import Player
from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "sofascore"
APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
SOFASCORE_ACTOR_ID = "your-sofascore-actor-id"  # da sostituire con l'actor Apify scelto


def is_configured() -> bool:
    return bool(settings.APIFY_TOKEN)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _run_actor(input_payload: dict) -> list[dict]:
    register_call(SOURCE)
    url = APIFY_RUN_URL.format(actor_id=SOFASCORE_ACTOR_ID)
    with httpx.Client(timeout=60) as client:
        response = client.post(url, params={"token": settings.APIFY_TOKEN}, json=input_payload)
        response.raise_for_status()
        return response.json()


def fetch_latest_rating(player: Player) -> float | None:
    if not is_configured():
        logger.warning("APIFY_TOKEN non configurato: salto fetch rating per player_id=%s", player.id)
        return None

    if not player.sofascore_id:
        return None

    try:
        items = _run_actor({"sofascore_id": player.sofascore_id})
    except httpx.HTTPError as exc:
        logger.error("Errore scraping Sofascore per player_id=%s: %s", player.id, exc)
        return None

    if not items:
        return None
    return items[0].get("rating")
