"""Client diretto verso l'API interna di Transfermarkt
(tmapi.transfermarkt.technology), per statistiche partita-per-partita reali.

Scoperta intercettando il traffico di rete della pagina pubblica
`/leistungsdaten/spieler/{id}` (verificato dal vivo: NESSUN paywall
ContentPass, a differenza di `/leistungsdatendetails/...` usata da
transfermarkt-api, che invece e' bloccata). Quella pagina renderizza la
tabella riepilogativa via un componente JS (Svelte) che chiama questa
stessa API; chiamandola direttamente otteniamo dati partita-per-partita
completi (goal, assist, minuti, competizione, avversario, presenze) senza
eseguire JavaScript e senza alcuna autenticazione.

Endpoint usati (verificati con richieste HTTP dirette, risposta 200 pulita):
  - /player/{player_id}/performance-game   -> tutte le partite in carriera
    (l'endpoint NON supporta filtro lato server per stagione: si scarica
    sempre tutto e si filtra lato nostro)
  - /competitions?ids[]=...                -> risolve id competizione -> nome
  - /clubs?ids[]=...                       -> risolve id club -> nome,
    include anche baseDetails.primaryCompetitionId (il campionato
    domestico principale del club, usato per scegliere la competizione
    "principale" del giocatore in modo affidabile invece di indovinare
    per nome/popolarita').

NOTA: e' un'API interna non documentata di Transfermarkt (diversa dal
servizio open source self-hosted `transfermarkt-api`), quindi piu'
soggetta a cambiare senza preavviso rispetto a un'API pubblica dichiarata.
Nessuna chiave/token richiesto.
"""

import logging
import time
from datetime import date, datetime, timezone

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.scrapers.rate_limit import register_call

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "transfermarkt-performance"
BASE_URL = "https://tmapi.transfermarkt.technology"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

_last_request_monotonic = 0.0


class MatchPerformance(BaseModel):
    external_ref: str
    match_date: date
    competition_id: str
    competition_name: str | None = None
    opponent_id: str | None = None
    opponent_name: str | None = None
    is_home: bool
    is_national_game: bool
    season_id: int
    minutes_played: int
    goals: int
    assists: int


class SeasonSummary(BaseModel):
    season_id: int
    season_label: str
    competition_id: str
    competition_name: str | None = None
    club_id: str | None = None
    appearances: int
    goals: int
    assists: int
    minutes_played: int


def is_configured() -> bool:
    """Nessuna chiave richiesta: e' un endpoint pubblico non autenticato."""
    return True


def _throttle() -> None:
    global _last_request_monotonic
    elapsed = time.monotonic() - _last_request_monotonic
    wait = settings.TRANSFERMARKT_PERFORMANCE_REQUEST_DELAY_SECONDS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_monotonic = time.monotonic()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _get(path: str, params: dict | None = None) -> dict:
    _throttle()
    register_call(SOURCE)
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        data = response.json()

    if not data.get("success", True):
        logger.warning(
            "tmapi.transfermarkt.technology ha risposto success=false per %s: %s",
            path,
            data.get("message"),
        )
    return data


def get_all_games(player_id: str) -> list[dict]:
    """Tutte le partite in carriera del giocatore (grezze). L'endpoint non
    supporta filtro lato server per stagione, quindi filtriamo lato nostro
    nelle funzioni piu' in alto (`get_recent_matches`/`get_season_summary`).
    """
    try:
        data = _get(f"/player/{player_id}/performance-game")
    except httpx.HTTPError as exc:
        logger.error("Errore fetch performance-game per player_id=%s: %s", player_id, exc)
        return []
    return data.get("data", {}).get("performance", [])


def resolve_competition_names(competition_ids: set[str]) -> dict[str, str]:
    if not competition_ids:
        return {}
    try:
        data = _get("/competitions", params={"ids[]": sorted(competition_ids)})
    except httpx.HTTPError as exc:
        logger.error("Errore risoluzione nomi competizioni %s: %s", competition_ids, exc)
        return {}
    return {c["id"]: c["name"] for c in data.get("data", [])}


def resolve_club_names(club_ids: set[str]) -> dict[str, str]:
    if not club_ids:
        return {}
    try:
        data = _get("/clubs", params={"ids[]": sorted(club_ids)})
    except httpx.HTTPError as exc:
        logger.error("Errore risoluzione nomi club %s: %s", club_ids, exc)
        return {}
    return {c["id"]: c["name"] for c in data.get("data", [])}


def get_club_primary_competition(club_id: str) -> str | None:
    """Campionato domestico principale del club (dato ufficiale Transfermarkt,
    non una euristica): usato per scegliere la competizione 'principale' del
    giocatore in modo affidabile."""
    try:
        data = _get("/clubs", params={"ids[]": [club_id]})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch club_id=%s: %s", club_id, exc)
        return None
    clubs = data.get("data", [])
    if not clubs:
        return None
    return clubs[0].get("baseDetails", {}).get("primaryCompetitionId")


def _was_played(game: dict) -> bool:
    state = game.get("statistics", {}).get("generalStatistics", {}).get("participationState")
    return state == "played" and not game.get("gameInformation", {}).get("isGamePostponed", False)


def get_recent_matches(player_id: str, limit: int = 5) -> list[MatchPerformance]:
    """Ultime `limit` partite realmente giocate (qualunque competizione,
    inclusa nazionale: per la 'forma recente' e' corretto includerle)."""
    games = [g for g in get_all_games(player_id) if _was_played(g)]
    if not games:
        return []

    games.sort(key=lambda g: g["gameInformation"]["date"]["dateTimeUTC"], reverse=True)
    top = games[:limit]

    competition_ids = {g["gameInformation"]["competitionId"] for g in top}
    club_ids = set()
    for g in top:
        club_ids.add(g["clubsInformation"]["club"]["clubId"])
        club_ids.add(g["clubsInformation"]["opponent"]["clubId"])

    comp_names = resolve_competition_names(competition_ids)
    club_names = resolve_club_names(club_ids)

    matches = []
    for g in top:
        info = g["gameInformation"]
        clubs = g["clubsInformation"]
        stats = g["statistics"]
        is_home = clubs["club"]["venue"] == "home"
        opponent_id = clubs["opponent"]["clubId"]

        matches.append(
            MatchPerformance(
                external_ref=info["gameId"],
                match_date=info["date"]["dateTimeUTC"][:10],
                competition_id=info["competitionId"],
                competition_name=comp_names.get(info["competitionId"]),
                opponent_id=opponent_id,
                opponent_name=club_names.get(opponent_id),
                is_home=is_home,
                is_national_game=bool(info.get("isNationalGame")),
                season_id=info["seasonId"],
                minutes_played=stats["playingTimeStatistics"].get("playedMinutes") or 0,
                goals=stats["goalStatistics"].get("goalsScoredTotal") or 0,
                assists=stats["goalStatistics"].get("assists") or 0,
            )
        )
    return matches


def _pick_competition_for_season(season_games: list[dict], primary_competition_id: str | None) -> str:
    if primary_competition_id and any(
        g["gameInformation"]["competitionId"] == primary_competition_id for g in season_games
    ):
        return primary_competition_id
    # fallback: nessun dato ufficiale sul campionato principale (o il
    # giocatore non ha ancora giocato quella competizione in questa
    # stagione) -> usa la competizione con piu' presenze tra quelle
    # giocate con la squadra in questa stagione.
    counts: dict[str, int] = {}
    for g in season_games:
        cid = g["gameInformation"]["competitionId"]
        counts[cid] = counts.get(cid, 0) + 1
    return max(counts, key=counts.get)


def list_season_options(player_id: str, current_club_id: str, max_seasons: int = 6) -> list[SeasonSummary]:
    """Elenco delle ultime `max_seasons` stagioni per cui il giocatore ha
    davvero giocato con `current_club_id` (piu' recente prima), ciascuna con
    il campionato domestico principale gia' scelto. Usato sia per
    l'aggregato 'stagione corrente' (get_season_summary = il primo elemento)
    sia per il selettore stagioni in UI, cosi' lo scout puo' vedere anche
    l'ultima stagione con dati reali quando quella in corso non ne ha ancora
    (giocatore appena trasferito, stagione appena iniziata, infortunio, ecc.),
    esattamente come mostrano Sofascore/Transfermarkt stessi con il loro
    menu a tendina delle stagioni.
    """
    games = [
        g
        for g in get_all_games(player_id)
        if _was_played(g)
        and not g["gameInformation"].get("isNationalGame")
        and g["clubsInformation"]["club"]["clubId"] == current_club_id
    ]
    if not games:
        return []

    primary_competition_id = get_club_primary_competition(current_club_id)

    by_season: dict[int, list[dict]] = {}
    season_labels: dict[int, str] = {}
    for g in games:
        season_id = g["gameInformation"]["seasonId"]
        by_season.setdefault(season_id, []).append(g)
        season_labels[season_id] = g["gameInformation"]["season"].get("nonCyclicalName") or str(season_id)

    ordered_season_ids = sorted(by_season.keys(), reverse=True)[:max_seasons]

    picked: list[tuple[int, str, list[dict]]] = []
    for season_id in ordered_season_ids:
        season_games = by_season[season_id]
        competition_id = _pick_competition_for_season(season_games, primary_competition_id)
        comp_games = [g for g in season_games if g["gameInformation"]["competitionId"] == competition_id]
        picked.append((season_id, competition_id, comp_games))

    comp_names = resolve_competition_names({competition_id for _, competition_id, _ in picked})

    return [
        SeasonSummary(
            season_id=season_id,
            season_label=season_labels[season_id],
            competition_id=competition_id,
            competition_name=comp_names.get(competition_id),
            club_id=current_club_id,
            appearances=len(comp_games),
            goals=sum(g["statistics"]["goalStatistics"].get("goalsScoredTotal") or 0 for g in comp_games),
            assists=sum(g["statistics"]["goalStatistics"].get("assists") or 0 for g in comp_games),
            minutes_played=sum(
                g["statistics"]["playingTimeStatistics"].get("playedMinutes") or 0 for g in comp_games
            ),
        )
        for season_id, competition_id, comp_games in picked
    ]


def get_season_summary(player_id: str, current_club_id: str) -> SeasonSummary | None:
    """Aggregato per la stagione PIU' RECENTE in cui il giocatore ha
    realmente giocato con il club attuale (campionato domestico
    principale). Se la stagione in corso non ha ancora partite (appena
    iniziata, trasferimento recente senza ancora un esordio, infortunio),
    ricade automaticamente sull'ultima stagione con dati reali — stesso
    comportamento del selettore stagioni, di cui questa funzione prende
    semplicemente la prima voce."""
    options = list_season_options(player_id, current_club_id, max_seasons=1)
    return options[0] if options else None


def get_current_club_id(player_id: str) -> str | None:
    """Id del CLUB (non la nazionale) con cui il giocatore ha giocato
    l'ultima partita reale, usato per determinare la stagione/competizione
    principale corrente senza dover chiamare anche il profilo giocatore.

    Esclude le partite in nazionale: se le ultime partite disputate sono
    impegni internazionali (es. Mondiale), l'ultima partita in assoluto
    avrebbe come 'club' la nazionale stessa, facendo fallire la ricerca
    del campionato di club in corso.
    """
    games = [g for g in get_all_games(player_id) if _was_played(g) and not g["gameInformation"].get("isNationalGame")]
    if not games:
        return None
    latest = max(games, key=lambda g: g["gameInformation"]["date"]["dateTimeUTC"])
    return latest["clubsInformation"]["club"]["clubId"]
