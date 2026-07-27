"""Transfermarkt: ricerca giocatori (scraping HTTP diretto) + valore di
mercato (Apify, INVARIATO).

`search_players_transfermarkt` e' la nuova fonte primaria per
l'autocompletamento: usa lo stesso endpoint di ricerca pubblico dietro la
barra di ricerca del sito (`/schnellsuche/ergebnis/schnellsuche`), verificato
raggiungibile con una normale richiesta HTTP (nessun blocco anti-bot
incontrato, a differenza di Sofascore). Nessuna dipendenza da stagione o
piano a pagamento: funziona sempre, per qualunque giocatore reale.

`fetch_market_value` resta esattamente come prima (actor Apify
`automation-lab/transfermarkt-scraper`, spento finche' APIFY_TOKEN non e'
configurato) — non toccato.
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.player import Player
from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "transfermarkt"
ACTOR_ID = "automation-lab/transfermarkt-scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"

SEARCH_BASE_URL = "https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche"
SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_SEARCH_RESULTS = 8


def is_configured() -> bool:
    return bool(settings.APIFY_TOKEN)


def _parse_market_value_string(raw: str | None) -> float | None:
    if not raw:
        return None
    match = re.search(r"([\d.,]+)\s*([mk])?", raw.replace("€", "").strip(), re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix == "m":
        return number * 1_000_000
    if suffix == "k":
        return number * 1_000
    return number


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def search_players_transfermarkt(query: str) -> list[dict]:
    """Cerca giocatori reali per nome (anche parziale) direttamente su
    Transfermarkt. Nessuna chiave/token richiesto, nessun vincolo di
    stagione: funziona per qualunque giocatore, di qualunque campionato.
    """
    register_call(SOURCE)
    try:
        with httpx.Client(headers=SEARCH_HEADERS, timeout=15, follow_redirects=True) as client:
            response = client.get(SEARCH_BASE_URL, params={"query": query})
            response.raise_for_status()
            response.encoding = "utf-8"  # Transfermarkt non sempre dichiara il charset negli header
            html = response.text
    except httpx.HTTPError as exc:
        logger.error("Errore ricerca Transfermarkt per '%s': %s", query, exc)
        return []

    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    for inline_table in soup.select("table.inline-table"):
        name_link = inline_table.select_one("td.hauptlink a")
        if not name_link or not name_link.get("href"):
            continue

        match = re.search(r"/spieler/(\d+)", name_link["href"])
        if not match:
            continue
        transfermarkt_id = match.group(1)
        full_name = name_link.get("title") or name_link.get_text(strip=True)

        photo_img = inline_table.find("img")
        photo_url = photo_img.get("src") if photo_img else None

        rows = inline_table.select("tr")
        current_team = None
        if len(rows) > 1:
            team_link = rows[1].select_one("a")
            if team_link:
                current_team = team_link.get("title") or team_link.get_text(strip=True)

        parent_row = inline_table.find_parent("tr")
        position = None
        nationality = None
        market_value_display = None
        if parent_row is not None:
            for cell in parent_row.find_all("td", recursive=False):
                classes = cell.get("class") or []
                if "zentriert" in classes:
                    text = cell.get_text(strip=True)
                    img = cell.find("img")
                    if img and not text:
                        title = img.get("title", "")
                        if title and title != current_team:
                            nationality = title
                    elif text and not text.isdigit() and position is None:
                        position = text
                elif "rechts" in classes and "€" in cell.get_text():
                    market_value_display = cell.get_text(strip=True)

        results.append(
            {
                "transfermarkt_id": transfermarkt_id,
                "full_name": full_name,
                "current_team": current_team,
                "position": position,
                "nationality": nationality,
                "market_value_eur": _parse_market_value_string(market_value_display),
                "photo_url": photo_url,
            }
        )

        if len(results) >= MAX_SEARCH_RESULTS:
            break

    return results


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
