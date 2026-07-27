"""Scraping Sofascore per statistiche stagionali, rating e xG/xA, via Playwright.

Sofascore blocca le chiamate HTTP dirette alle sue API interne (verificato:
sia `api.sofascore.com` sia `www.sofascore.com/api/...` rispondono 403 anche
con header realistici, sia via httpx sia via il request-context "leggero" di
Playwright). L'unico modo verificato funzionante e' aprire una pagina vera
con un browser (che supera qualunque controllo anti-bot lato client) e da
LI' dentro eseguire `fetch()` verso le API interne: sono richieste
"in-pagina" indistinguibili da quelle che farebbe il sito stesso, e
rispondono correttamente (200) con JSON pulito — niente parsing HTML.

Endpoint usati (scoperti intercettando il traffico reale del sito):
  - /api/v1/search/all?q=...            -> ricerca giocatori/squadre
  - /api/v1/player/{id}/statistics/seasons
                                          -> tornei/stagioni disponibili per il giocatore
  - /api/v1/player/{id}/unique-tournament/{t}/season/{s}/statistics/overall
                                          -> aggregati stagionali (goal, assist, presenze, minuti, rating, xG, xA)
  - /api/v1/player/{id}/events/last/0    -> ultime partite giocate
  - /api/v1/event/{eventId}/player/{id}/statistics
                                          -> statistiche del giocatore in UNA partita (rating, xG, xA inclusi)

Una singola sessione browser (`SofascoreSession`) va aperta una volta e
riutilizzata per piu' chiamate (una per giocatore in fase di import, una per
tutta la watchlist nel job notturno), per non pagare il costo di
avvio/consenso ad ogni richiesta. Applica inoltre un rate limiting prudente
(pausa minima configurabile tra una richiesta e l'altra) per non
sovraccaricare il sito e ridurre il rischio di blocchi IP.
"""

import logging
import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from app.core.config import get_settings
from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "sofascore"
BASE_URL = "https://www.sofascore.com"

# Usato per scegliere il "campionato principale" quando un giocatore ha piu'
# competizioni nella stessa stagione (es. campionato + coppa nazionale):
# preferisce le 5 leghe europee top, poi la piu' popolare (userCount) tra le
# rimanenti.
TOP_LEAGUE_CATEGORY_SLUGS = ["england", "spain", "italy", "germany", "france"]
CUP_NAME_MARKERS = ("cup", "coppa", "copa", "supercoppa", "shield", "trophy", "playoff")
NON_DOMESTIC_CATEGORY_SLUGS = {"world", "europe", "international"}


def is_configured() -> bool:
    """Non serve nessuna chiave: e' scraping diretto via browser."""
    return True


class SofascoreSession:
    """Sessione browser Playwright riutilizzabile per piu' chiamate.

    Uso:
        with SofascoreSession() as session:
            candidates = search_players(session, "Erling Haaland")
            stats = get_season_stats(session, candidates[0]["id"])
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None
        self._last_request_monotonic = 0.0
        self._ok = False

    def __enter__(self) -> "SofascoreSession":
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch()
            self._page = self._browser.new_page()
            self._page.goto(BASE_URL, wait_until="load", timeout=30000)
            self._dismiss_consent()
            self._ok = True
        except Exception:
            logger.exception("Errore apertura sessione Sofascore (Playwright/Chromium non disponibile?)")
            self._ok = False
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()

    @property
    def ok(self) -> bool:
        return self._ok

    def _dismiss_consent(self) -> None:
        for label in ("Consent", "I Accept", "Accept All", "AGREE"):
            try:
                self._page.get_by_role("button", name=label, exact=True).click(timeout=2000)
                return
            except Exception:
                continue

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        wait = settings.SOFASCORE_REQUEST_DELAY_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_monotonic = time.monotonic()

    def fetch_json(self, path: str) -> dict | None:
        if not self._ok or self._page is None:
            return None

        self._throttle()
        register_call(SOURCE)
        url = f"{BASE_URL}{path}"
        try:
            result = self._page.evaluate(
                """async (url) => {
                    const res = await fetch(url);
                    return { status: res.status, body: await res.text() };
                }""",
                url,
            )
        except Exception as exc:
            logger.error("Errore Sofascore fetch %s: %s", path, exc)
            return None

        if result.get("status") != 200:
            logger.warning("Sofascore ha risposto %s per %s", result.get("status"), path)
            return None

        try:
            import json

            return json.loads(result["body"])
        except (ValueError, KeyError, TypeError):
            logger.warning("Sofascore: corpo non-JSON per %s", path)
            return None


def search_players(session: SofascoreSession, query: str, limit: int = 10) -> list[dict]:
    """Cerca giocatori DI CALCIO (esclude i ritirati e gli omonimi di altri
    sport, es. tennisti/cestisti con lo stesso nome) per il mapping verso
    Sofascore. Ogni candidato: {id, name, slug, team, country, position}.
    """
    data = session.fetch_json(f"/api/v1/search/all?q={query}&page=0")
    if not data:
        return []

    candidates = []
    for item in data.get("results", []):
        if item.get("type") != "player":
            continue
        entity = item.get("entity", {})
        if entity.get("retired"):
            continue

        team = entity.get("team") or {}
        sport_slug = (team.get("sport") or {}).get("slug")
        if sport_slug and sport_slug != "football":
            continue  # omonimo di un altro sport, non e' un calciatore

        candidates.append(
            {
                "id": entity.get("id"),
                "name": entity.get("name"),
                "slug": entity.get("slug"),
                "team": team.get("name"),
                "country": (entity.get("country") or {}).get("name"),
                "position": entity.get("position"),
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def _is_domestic_league(entry: dict) -> bool:
    tournament = entry.get("uniqueTournament", {})
    category_slug = (tournament.get("category", {}) or {}).get("slug", "")
    name = (tournament.get("name") or "").lower()
    if category_slug in NON_DOMESTIC_CATEGORY_SLUGS:
        return False
    return not any(marker in name for marker in CUP_NAME_MARKERS)


def _season_recency_key(season: dict) -> int:
    """Converte lo 'year' di una stagione (es. '25/26', o '2025') in un intero
    confrontabile, per poter scegliere la stagione/il torneo piu' recente."""
    year_str = str(season.get("year") or season.get("name") or "")
    match = re.search(r"(\d{2,4})", year_str)
    if not match:
        return 0
    year_num = int(match.group(1))
    if year_num < 100:
        year_num += 2000
    return year_num


def _pick_main_tournament(seasons_data: dict) -> tuple[dict, dict] | None:
    entries = seasons_data.get("uniqueTournamentSeasons", [])
    if not entries:
        return None

    league_entries = [e for e in entries if _is_domestic_league(e)] or entries

    def sort_key(entry: dict) -> tuple[int, int, int]:
        seasons = entry.get("seasons", [])
        recency = _season_recency_key(seasons[0]) if seasons else 0

        category_slug = (entry.get("uniqueTournament", {}).get("category", {}) or {}).get("slug", "")
        try:
            prestige_rank = TOP_LEAGUE_CATEGORY_SLUGS.index(category_slug)
        except ValueError:
            prestige_rank = len(TOP_LEAGUE_CATEGORY_SLUGS)
        user_count = entry.get("uniqueTournament", {}).get("userCount") or 0

        # La stagione piu' recente vince SEMPRE (altrimenti si rischia di
        # prendere il campionato di una squadra passata solo perche' piu'
        # blasonato, es. Premier League di anni fa invece della Serie A
        # attuale). Prestigio/popolarita' fanno solo da spareggio tra
        # campionati con la stessa recency (es. due big-5 nella stessa stagione).
        return (-recency, prestige_rank, -user_count)

    best = min(league_entries, key=sort_key)
    seasons = best.get("seasons", [])
    if not seasons:
        return None
    return best["uniqueTournament"], seasons[0]  # seasons[0] = la piu' recente per quel torneo


def get_season_stats(session: SofascoreSession, sofascore_id: int) -> dict | None:
    """Statistiche stagionali reali per il campionato principale del
    giocatore. Ritorna None se non disponibile (es. giocatore senza
    statistiche registrate)."""
    seasons_data = session.fetch_json(f"/api/v1/player/{sofascore_id}/statistics/seasons")
    if not seasons_data:
        return None

    picked = _pick_main_tournament(seasons_data)
    if picked is None:
        return None
    tournament, season = picked

    overall = session.fetch_json(
        f"/api/v1/player/{sofascore_id}/unique-tournament/{tournament['id']}/season/{season['id']}/statistics/overall"
    )
    if not overall:
        return None

    stats = overall.get("statistics", {}) or {}
    team = overall.get("team", {}) or {}

    return {
        "league": tournament.get("name"),
        "current_team": team.get("name"),
        "goals_season": stats.get("goals") or 0,
        "assists_season": stats.get("assists") or 0,
        "appearances_season": stats.get("appearances") or 0,
        "minutes_season": stats.get("minutesPlayed") or 0,
        "rating_avg": stats.get("rating"),
        "xg_season": stats.get("expectedGoals"),
        "xa_season": stats.get("expectedAssists"),
    }


def get_recent_matches(session: SofascoreSession, sofascore_id: int, limit: int = 5) -> list[dict]:
    """Ultime `limit` partite reali giocate, con rating/xG/xA per partita
    quando disponibili (xG/xA restano None per i campionati che Sofascore
    non copre: e' un dato mancante legittimo, non un errore)."""
    events_data = session.fetch_json(f"/api/v1/player/{sofascore_id}/events/last/0")
    if not events_data:
        return []

    events = events_data.get("events", [])

    def is_finished(event: dict) -> bool:
        status = event.get("status") or {}
        status_type = status.get("type")
        return status_type in (None, "finished")

    finished = [e for e in events if is_finished(e)]
    finished.sort(key=lambda e: e.get("startTimestamp") or 0, reverse=True)

    matches: list[dict] = []
    for event in finished[:limit]:
        event_id = event.get("id")
        if event_id is None:
            continue

        stats = session.fetch_json(f"/api/v1/event/{event_id}/player/{sofascore_id}/statistics")
        if not stats:
            continue

        s = stats.get("statistics", {}) or {}
        home_team = (event.get("homeTeam") or {}).get("name")
        away_team = (event.get("awayTeam") or {}).get("name")
        player_team = (stats.get("team") or {}).get("name")
        is_home = player_team == home_team

        timestamp = event.get("startTimestamp")
        match_date = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc).date() if timestamp else None
        )
        if match_date is None:
            continue

        matches.append(
            {
                "external_ref": str(event_id),
                "match_date": match_date,
                "competition": (event.get("tournament") or {}).get("name") or "N/D",
                "opponent": away_team if is_home else home_team,
                "is_home": is_home,
                "minutes_played": s.get("minutesPlayed") or 0,
                "goals": s.get("goals") or 0,
                "assists": s.get("goalAssist") or 0,
                "rating": s.get("rating"),
                "xg": s.get("expectedGoals"),
                "xa": s.get("expectedAssists"),
            }
        )

    return matches
