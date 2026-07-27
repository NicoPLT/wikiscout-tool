"""Scraping del rating (Sofascore), via due actor Apify pubblici (Fase B, attiva).

ATTENZIONE - unico dei tre scraper reali senza schema di output pubblicamente
documentato in dettaglio: il rating medio "ufficiale" resta comunque coperto
in modo affidabile dal rating partita-per-partita che restituisce
API-Football stesso (vedi app/scrapers/jobs.py::_ingest_new_fixtures), che e'
gia' un dato reale. Questo modulo prova IN PIU' a recuperare il rating da
Sofascore vero e proprio, ma la struttura esatta della risposta dell'actor
"profilo giocatore" andra' verificata/aggiustata con una run reale (vedi
_extract_rating_best_effort) non appena sono disponibili crediti Apify per
un test dal vivo.

Pipeline:
  1. `gio21/sofascore-scraper` (searchTerm=nome) -> risolve lo slug/URL profilo
     del giocatore su Sofascore.
  2. `azzouzana/sofascore-scraper-pro` (startUrls=[profilo]) -> scraping della
     pagina profilo, da cui proviamo ad estrarre il rating piu' recente.

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
SEARCH_ACTOR_ID = "gio21/sofascore-scraper"
PROFILE_ACTOR_ID = "azzouzana/sofascore-scraper-pro"
SEARCH_RUN_URL = f"https://api.apify.com/v2/acts/{SEARCH_ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"
PROFILE_RUN_URL = f"https://api.apify.com/v2/acts/{PROFILE_ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(settings.APIFY_TOKEN)


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _run_actor(url: str, input_payload: dict) -> list[dict]:
    register_call(SOURCE)
    with httpx.Client(timeout=90) as client:
        response = client.post(url, params={"token": settings.APIFY_TOKEN}, json=input_payload)
        response.raise_for_status()
        return response.json()


def _resolve_player_profile(player_name: str) -> dict | None:
    try:
        items = _run_actor(SEARCH_RUN_URL, {"searchTerm": player_name, "includeMatches": False, "maxItems": 5})
    except httpx.HTTPError as exc:
        logger.error("Errore ricerca Sofascore per '%s': %s", player_name, exc)
        return None

    for item in items:
        if item.get("type") == "player" and item.get("url"):
            return item
    return None


def _dig(data: dict, path: list):
    current = data
    for key in path:
        if isinstance(key, int):
            if not isinstance(current, list) or key >= len(current):
                return None
            current = current[key]
        else:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
    return current


def _extract_rating_best_effort(data: dict, player_name: str) -> float | None:
    candidate_paths = [
        ["rating"],
        ["statistics", "rating"],
        ["recentMatches", 0, "rating"],
        ["matches", 0, "rating"],
        ["lastMatches", 0, "rating"],
    ]
    for path in candidate_paths:
        value = _dig(data, path)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    logger.info(
        "Sofascore: struttura output non riconosciuta per '%s' (chiavi disponibili: %s). "
        "Verificare l'output reale dell'actor %s e aggiornare _extract_rating_best_effort.",
        player_name,
        list(data.keys()) if isinstance(data, dict) else type(data),
        PROFILE_ACTOR_ID,
    )
    return None


def fetch_latest_rating(player: Player) -> float | None:
    if not is_configured():
        logger.warning("APIFY_TOKEN non configurato: salto rating Sofascore per player_id=%s", player.id)
        return None

    profile = _resolve_player_profile(player.full_name)
    if profile is None:
        return None

    try:
        items = _run_actor(PROFILE_RUN_URL, {"startUrls": [profile["url"]]})
    except httpx.HTTPError as exc:
        logger.error("Errore scraping profilo Sofascore per player_id=%s: %s", player.id, exc)
        return None

    if not items:
        return None

    return _extract_rating_best_effort(items[0], player.full_name)
