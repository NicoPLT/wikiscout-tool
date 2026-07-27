"""Integrazione API-Football (Fase B).

Finche' API_FOOTBALL_KEY non e' configurata in .env, ogni funzione qui logga
un warning e ritorna None/[] senza rompere il job notturno: questo modulo e'
scritto e pronto, ma resta "spento" fino a quando non si ottiene la chiave
(vedi README per dove registrarsi).
"""

import logging
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.player import Player
from app.scrapers.rate_limit import is_near_limit, register_call

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = "https://v3.football.api-sports.io"
SOURCE = "api_football"


def is_configured() -> bool:
    return bool(settings.API_FOOTBALL_KEY)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _get(path: str, params: dict) -> dict:
    register_call(SOURCE)
    headers = {"x-apisports-key": settings.API_FOOTBALL_KEY or ""}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=15) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def fetch_recent_match_stats(player: Player, since: date) -> list[dict] | None:
    """Ritorna le statistiche delle partite giocate da `since` ad oggi, o None se skip."""
    if not is_configured():
        logger.warning("API_FOOTBALL_KEY non configurata: salto fetch per player_id=%s", player.id)
        return None

    if is_near_limit(SOURCE, settings.API_FOOTBALL_DAILY_LIMIT):
        logger.warning(
            "Vicini al limite giornaliero API-Football (%s chiamate): salto fetch per player_id=%s",
            settings.API_FOOTBALL_DAILY_LIMIT,
            player.id,
        )
        return None

    if not player.api_football_id:
        logger.info("Player %s senza api_football_id, salto", player.id)
        return None

    try:
        data = _get("/players", {"id": player.api_football_id, "season": since.year})
    except httpx.HTTPError as exc:
        logger.error("Errore chiamando API-Football per player_id=%s: %s", player.id, exc)
        return None

    return data.get("response", [])
