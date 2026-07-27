"""Client per Fotmob: usato SOLO per risolvere l'id giocatore e costruire il
link diretto al profilo nella scheda giocatore (nessuna statistica viene
letta da qui, quelle restano su Transfermarkt/Sofascore).

Endpoint scoperto intercettando il traffico di rete della barra di ricerca
di fotmob.com (nessuna chiave/token richiesto, nessun blocco anti-bot
incontrato con richieste HTTP dirette):
  - /api/data/search/suggest?hits=...&lang=...&term=...  -> suggerimenti di
    ricerca per nome, include type="player", id numerico e teamName.

L'URL del profilo (/players/{id}/{slug}) accetta qualunque slug segnaposto:
verificato dal vivo che risolve comunque al profilo corretto.
"""

import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)

SOURCE = "fotmob"
BASE_URL = "https://www.fotmob.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def is_configured() -> bool:
    """Nessuna chiave richiesta: e' un endpoint pubblico non autenticato."""
    return True


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def search_players(name: str) -> list[dict]:
    """Suggerimenti di ricerca per nome: ritorna i candidati grezzi con
    almeno id, name, teamName (usato per il matching squadra in
    resolve_fotmob_id).
    """
    register_call(SOURCE)
    try:
        with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=15) as client:
            response = client.get(
                "/api/data/search/suggest", params={"hits": 10, "lang": "en", "term": name}
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("Errore ricerca Fotmob per '%s': %s", name, exc)
        return []

    for group in data if isinstance(data, list) else []:
        if group.get("title", {}).get("key") == "players":
            return [s for s in group.get("suggestions", []) if s.get("type") == "player"]
    return []


def resolve_fotmob_id(full_name: str, current_team: str | None) -> str | None:
    """Trova l'id Fotmob del giocatore, preferendo il candidato la cui
    squadra corrisponde a `current_team` quando ci sono piu' omonimi.
    Nessun tentativo di disambiguazione oltre questo: e' solo per un link,
    non per statistiche, quindi in caso di dubbio meglio nessun link che uno
    sbagliato -> None se non c'e' un solo candidato chiaro.
    """
    candidates = search_players(full_name)
    if not candidates:
        return None
    if len(candidates) == 1:
        return str(candidates[0]["id"])

    if current_team:
        team_lower = current_team.strip().lower()
        for c in candidates:
            team_name = (c.get("teamName") or "").strip().lower()
            if team_name and (team_name in team_lower or team_lower in team_name):
                return str(c["id"])

    return None
