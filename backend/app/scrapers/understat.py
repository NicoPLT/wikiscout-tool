"""Integrazione Understat per xG/xA (Fase B, attiva), via l'actor Apify
`parseforge/understat-xg-scraper`.

L'actor ritorna TUTTI i giocatori di un campionato/stagione in un'unica
chiamata: la mettiamo in cache su Redis per 24h cosi' un solo run serve
tutti i giocatori copiati in watchlist per quel campionato, invece di una
chiamata per giocatore. Attiva solo per player.is_xg_covered=True (Top 5
campionati europei coperti da Understat) e solo se APIFY_TOKEN e' configurato.
"""

import json
import logging
import unicodedata

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.db.redis_client import redis_client
from app.models.player import Player
from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "understat"
ACTOR_ID = "parseforge/understat-xg-scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"
CACHE_TTL_SECONDS = 24 * 60 * 60

LEAGUE_TO_UNDERSTAT_CODE = {
    "premier league": "EPL",
    "la liga": "La_liga",
    "bundesliga": "Bundesliga",
    "serie a": "Serie_A",
    "ligue 1": "Ligue_1",
}


def is_configured() -> bool:
    return bool(settings.APIFY_TOKEN)


def _normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.strip().lower()


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _run_actor(input_payload: dict) -> list[dict]:
    register_call(SOURCE)
    with httpx.Client(timeout=120) as client:
        response = client.post(APIFY_RUN_URL, params={"token": settings.APIFY_TOKEN}, json=input_payload)
        response.raise_for_status()
        return response.json()


def _get_league_dataset(league_code: str, season: int) -> list[dict]:
    cache_key = f"understat:{league_code}:{season}"
    cached = redis_client.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    try:
        items = _run_actor({"league": league_code, "season": season, "maxItems": 1000})
    except httpx.HTTPError as exc:
        logger.error("Errore scraping Understat per %s/%s: %s", league_code, season, exc)
        return []

    redis_client.set(cache_key, json.dumps(items), ex=CACHE_TTL_SECONDS)
    return items


def fetch_xg_xa(player: Player, season: int) -> dict | None:
    if not is_configured():
        logger.warning("APIFY_TOKEN non configurato: salto xG/xA per player_id=%s", player.id)
        return None

    if not player.is_xg_covered or not player.league:
        return None

    league_code = LEAGUE_TO_UNDERSTAT_CODE.get(player.league.strip().lower())
    if not league_code:
        return None

    dataset = _get_league_dataset(league_code, season)
    if not dataset:
        return None

    target = _normalize_name(player.full_name)
    target_surname = target.split()[-1] if target else ""

    exact_matches = [row for row in dataset if _normalize_name(row.get("playerName", "")) == target]
    if exact_matches:
        match = exact_matches[0]
    else:
        surname_matches = [
            row for row in dataset if _normalize_name(row.get("playerName", "")).endswith(target_surname)
        ]
        if len(surname_matches) != 1:
            return None
        match = surname_matches[0]

    return {"xG": match.get("xG"), "xA": match.get("xA")}
