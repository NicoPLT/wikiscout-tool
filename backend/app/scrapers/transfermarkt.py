"""Scraping mirato di Transfermarkt per il valore di mercato (Fase B, attiva).

Usa l'actor Apify pubblico `automation-lab/transfermarkt-scraper`, che cerca
per NOME giocatore (non serve un transfermarkt_id pre-registrato) e ritorna
tra gli altri campi `marketValueNumeric` (valore in EUR) e `currentClub`,
usato per scegliere il risultato giusto quando piu' giocatori omonimi
compaiono nella ricerca. Aggiornamento pensato per girare settimanalmente
(vedi MARKET_VALUE_REFRESH_DAYS in jobs.py), non ad ogni run notturno.

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

SOURCE = "transfermarkt"
ACTOR_ID = "automation-lab/transfermarkt-scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(settings.APIFY_TOKEN)


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _run_actor(input_payload: dict) -> list[dict]:
    register_call(SOURCE)
    with httpx.Client(timeout=90) as client:
        response = client.post(APIFY_RUN_URL, params={"token": settings.APIFY_TOKEN}, json=input_payload)
        response.raise_for_status()
        return response.json()


def _best_match(items: list[dict], current_team: str | None) -> dict | None:
    if not items:
        return None
    if not current_team:
        return items[0]

    team_lower = current_team.strip().lower()
    for item in items:
        club = (item.get("currentClub") or "").strip().lower()
        if club and (team_lower in club or club in team_lower):
            return item
    return items[0]


def fetch_market_value(player: Player) -> tuple[float, str | None] | None:
    """Ritorna (valore_eur, transfermarkt_player_id) o None se non trovato/spento."""
    if not is_configured():
        logger.warning("APIFY_TOKEN non configurato: salto valore di mercato per player_id=%s", player.id)
        return None

    try:
        items = _run_actor(
            {
                "searchQueries": [player.full_name],
                "maxPlayersPerQuery": 5,
                "language": "en",
            }
        )
    except httpx.HTTPError as exc:
        logger.error("Errore scraping Transfermarkt per player_id=%s: %s", player.id, exc)
        return None

    match = _best_match(items, player.current_team)
    if not match or match.get("marketValueNumeric") is None:
        return None

    return float(match["marketValueNumeric"]), str(match.get("playerId")) if match.get("playerId") else None
