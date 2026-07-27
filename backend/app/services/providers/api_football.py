"""Integrazione API-Football — fonte LEGACY/OPZIONALE, spenta di default.

Storia: questo modulo era la fonte primaria di ricerca/statistiche, ma il
piano gratuito di API-Football rifiuta le stagioni 2025/2026 ("Free plans do
not have access to this season"), rendendo la ricerca giocatori inaffidabile
per chiunque non fosse gia' nei dati mock. Ricerca e statistiche di base sono
state spostate su Transfermarkt (`app/scrapers/transfermarkt.py`) e Sofascore
(`app/scrapers/sofascore.py`), che non hanno questo limite.

Questo modulo resta disponibile per eventuali usi futuri (es. formazioni,
dati che Transfermarkt/Sofascore non strutturano bene) ma NON e' piu' nel
percorso critico: e' attivo solo se ENABLE_API_FOOTBALL=true in .env, oltre
alla chiave. Di default e' spento e nessuna funzione qui viene chiamata dal
job notturno ne' dall'autocomplete.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.db.redis_client import redis_client
from app.scrapers.rate_limit import is_near_limit, register_call

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = "https://v3.football.api-sports.io"
SOURCE = "api_football"
SEARCH_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 ore

# I piani gratuiti di API-Football non hanno accesso alla stagione in corso
# ne' a quella appena passata (solo 2022-2024 al momento in cui e' stato
# scritto questo modulo): ogni richiesta con season >= 2025 torna una risposta
# HTTP 200 ma con errors.plan valorizzato e response vuoto. Se succede,
# ripieghiamo sull'ultima stagione che il piano free copre di sicuro.
FREE_PLAN_MAX_SEASON = 2024

# Campionati coperti da Understat per xG/xA (Top 5 europei)
XG_COVERED_LEAGUES = {"premier league", "la liga", "bundesliga", "serie a", "ligue 1"}

POSITION_MAP = {
    "Goalkeeper": "Portiere",
    "Defender": "Difensore",
    "Midfielder": "Centrocampista",
    "Attacker": "Attaccante",
}


def is_configured() -> bool:
    """True solo se ENABLE_API_FOOTBALL=true E la chiave e' impostata:
    questa fonte e' legacy/opzionale e va accesa esplicitamente."""
    return settings.ENABLE_API_FOOTBALL and bool(settings.API_FOOTBALL_KEY)


def current_season() -> int:
    """Stagione europea corrente (es. luglio 2026 -> 2026, aprile 2026 -> 2025)."""
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def is_covered_league(league_name: str | None) -> bool:
    if not league_name:
        return False
    return league_name.strip().lower() in XG_COVERED_LEAGUES


def map_position(position: str | None) -> str | None:
    if not position:
        return None
    return POSITION_MAP.get(position, position)


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
        data = response.json()

    # API-Football risponde quasi sempre con HTTP 200 anche quando i parametri
    # sono invalidi/non permessi dal piano: l'errore vero e proprio e' dentro
    # al campo "errors" del corpo, non nello status code.
    errors = data.get("errors")
    if errors:
        logger.warning("API-Football ha risposto con errori per %s %s: %s", path, params, errors)

    return data


def pick_primary_statistics(statistics: list[dict]) -> dict | None:
    """Sceglie la voce statistics[] piu' rilevante (piu' presenze in un campionato)."""
    if not statistics:
        return None

    league_entries = [s for s in statistics if s.get("league", {}).get("type") == "League"] or statistics
    return max(league_entries, key=lambda s: (s.get("games", {}) or {}).get("appearences") or 0)


MAX_SEARCH_CANDIDATES = 5


def search_players(query: str) -> list[dict]:
    """Cerca giocatori reali per nome, con squadra/campionato attuali.

    NOTA: l'endpoint /players (statistiche) richiede sempre league o team
    insieme a search, quindi non e' utilizzabile per un autocomplete libero.
    Usiamo invece /players/profiles?search=..., che cerca per nome senza
    questo vincolo ma non include squadra/campionato; per ognuno dei primi
    risultati facciamo percio' una chiamata aggiuntiva (get_player_by_id) per
    risolvere la squadra attuale, scartando i profili senza stagione corrente
    (probabilmente ritirati o inattivi). Costo per una query NUOVA (non in
    cache): 1 + fino a MAX_SEARCH_CANDIDATES chiamate.
    """
    if not is_configured():
        logger.warning("API_FOOTBALL_KEY non configurata: salto ricerca giocatori")
        return []

    cache_key = f"af_search:{query.strip().lower()}"
    cached = redis_client.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    if is_near_limit(SOURCE, settings.API_FOOTBALL_DAILY_LIMIT):
        logger.warning("Vicini al limite giornaliero API-Football: salto ricerca per '%s'", query)
        return []

    try:
        data = _get("/players/profiles", {"search": query})
    except httpx.HTTPError as exc:
        logger.error("Errore ricerca profili API-Football per '%s': %s", query, exc)
        return []

    profiles = data.get("response", [])[:MAX_SEARCH_CANDIDATES]
    results: list[dict] = []

    for item in profiles:
        player_info = item.get("player", {})
        player_id = player_info.get("id")
        if player_id is None:
            continue

        entry = get_player_by_id(player_id)
        if entry is None:
            continue

        snapshot = build_player_snapshot(entry)
        if not snapshot.get("current_team"):
            continue  # niente squadra in stagione corrente: probabilmente non attivo

        results.append(
            {
                "id": player_id,
                "name": snapshot["full_name"] or player_info.get("name"),
                "photo": snapshot["photo_url"] or player_info.get("photo"),
                "team": snapshot["current_team"],
                "league": snapshot["league"],
            }
        )

    redis_client.set(cache_key, json.dumps(results), ex=SEARCH_CACHE_TTL_SECONDS)
    return results


def build_player_snapshot(entry: dict) -> dict:
    """Normalizza una entry {player, statistics} (da /players) nei campi Player."""
    player_info = entry.get("player", {})
    primary = pick_primary_statistics(entry.get("statistics", [])) or {}
    team = primary.get("team", {}) or {}
    league = primary.get("league", {}) or {}
    games = primary.get("games", {}) or {}
    goals = primary.get("goals", {}) or {}

    full_name = player_info.get("name") or (
        f"{player_info.get('firstname', '')} {player_info.get('lastname', '')}".strip()
    )

    return {
        "full_name": full_name,
        "date_of_birth": (player_info.get("birth") or {}).get("date"),
        "nationality": player_info.get("nationality"),
        "position": map_position(games.get("position")),
        "photo_url": player_info.get("photo"),
        "current_team": team.get("name"),
        "team_id": team.get("id"),
        "league": league.get("name"),
        "is_xg_covered": is_covered_league(league.get("name")),
        "goals_season": goals.get("total") or 0,
        "assists_season": goals.get("assists") or 0,
        "appearances_season": games.get("appearences") or 0,
        "minutes_season": games.get("minutes") or 0,
    }


def get_player_by_id(api_football_id: int, season: int | None = None) -> dict | None:
    """Rifetch di un giocatore specifico (season stats + team/league correnti)."""
    if not is_configured():
        logger.warning("API_FOOTBALL_KEY non configurata: salto fetch player_id=%s", api_football_id)
        return None

    season = season or current_season()

    if is_near_limit(SOURCE, settings.API_FOOTBALL_DAILY_LIMIT):
        logger.warning("Vicini al limite giornaliero API-Football: salto fetch player_id=%s", api_football_id)
        return None

    try:
        data = _get("/players", {"id": api_football_id, "season": season})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch API-Football per player_id=%s: %s", api_football_id, exc)
        return None

    response = data.get("response", [])
    if response:
        return response[0]

    if "plan" in (data.get("errors") or {}) and season != FREE_PLAN_MAX_SEASON:
        return get_player_by_id(api_football_id, FREE_PLAN_MAX_SEASON)

    return None


def get_team_recent_fixtures(team_id: int, last: int = 5) -> list[dict]:
    if not is_configured():
        return []

    if is_near_limit(SOURCE, settings.API_FOOTBALL_DAILY_LIMIT):
        logger.warning("Vicini al limite giornaliero API-Football: salto fixtures team_id=%s", team_id)
        return []

    try:
        data = _get("/fixtures", {"team": team_id, "last": last})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch fixtures API-Football per team_id=%s: %s", team_id, exc)
        return []

    return data.get("response", [])


def get_fixture_player_stats(fixture_id: int, api_football_id: int) -> dict | None:
    """Statistiche di UN giocatore in UNA specifica partita (goal, assist, minuti, rating, ecc.)."""
    if not is_configured():
        return None

    if is_near_limit(SOURCE, settings.API_FOOTBALL_DAILY_LIMIT):
        logger.warning("Vicini al limite giornaliero API-Football: salto fixture_id=%s", fixture_id)
        return None

    try:
        data = _get("/fixtures/players", {"fixture": fixture_id})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch fixtures/players per fixture_id=%s: %s", fixture_id, exc)
        return None

    for team_block in data.get("response", []):
        for player_block in team_block.get("players", []):
            if str(player_block.get("player", {}).get("id")) == str(api_football_id):
                return player_block
    return None


def is_recently_finished(fixture: dict, within_hours: int = 48) -> bool:
    status_short = fixture.get("fixture", {}).get("status", {}).get("short")
    if status_short != "FT":
        return False

    fixture_date_str = fixture.get("fixture", {}).get("date")
    if not fixture_date_str:
        return False

    try:
        fixture_dt = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00"))
    except ValueError:
        return False

    return datetime.now(timezone.utc) - fixture_dt <= timedelta(hours=within_hours)


def fixture_match_date(fixture: dict) -> date | None:
    fixture_date_str = fixture.get("fixture", {}).get("date")
    if not fixture_date_str:
        return None
    try:
        return datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00")).date()
    except ValueError:
        return None
