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
  - /transfer/history/player/{player_id}   -> storico trasferimenti completo
    (scoperto intercettando la rete della pagina pubblica
    `/transfers/spieler/{id}`): ogni voce ha club di partenza/arrivo, data,
    costo del cartellino, valore di mercato al momento del trasferimento e
    tipo (STANDARD / prestito / rientro da prestito / free transfer).
  - /player/{player_id}/market-value-history -> storico completo del valore
    di mercato (uno o piu' punti all'anno, da inizio carriera a oggi):
    trovato per tentativi (stesso stile REST di /transfer/history/...),
    NON tramite intercettazione di rete (il componente Svelte che disegna
    il grafico su `/marktwertverlauf/spieler/{id}` vive in uno shadow DOM
    e non e' stato possibile osservarne la chiamata di rete direttamente).
  - /players?ids[]=...                     -> anagrafica completa, incluso
    lifeDates.dateOfBirth (la ricerca Transfermarkt usata per l'import non
    restituisce mai la data di nascita, quindi va recuperata qui).

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


class TransferRecord(BaseModel):
    transfer_id: str
    transfer_date: date
    club_from_id: str | None = None
    club_from_name: str | None = None
    club_to_id: str | None = None
    club_to_name: str | None = None
    fee_eur: float | None = None
    market_value_eur: float | None = None
    is_loan: bool = False
    is_free_transfer: bool = False
    season_label: str | None = None


class MarketValuePoint(BaseModel):
    recorded_at: date
    value_eur: float


class CompetitionStint(BaseModel):
    """Una voce del dettaglio per competizione dentro una stagione: un
    giocatore puo' averne piu' d'una nella stessa stagione (coppe,
    competizioni europee, o un altro club prima di un trasferimento a
    meta' stagione)."""

    competition_id: str
    competition_name: str | None = None
    club_id: str
    club_name: str | None = None
    appearances: int
    goals: int
    assists: int
    minutes_played: int
    starts: int = 0
    yellow_cards: int = 0
    red_cards: int = 0


class SeasonSummary(BaseModel):
    """Aggregato di UNA stagione. I campi numerici sono il TOTALE su tutte
    le competizioni e tutti i club di quella stagione (non solo il
    campionato principale del club attuale): altrimenti si perdono goal/
    assist fatti in coppe/competizioni europee, o con un altro club prima
    di un trasferimento a meta' stagione. competition_id/competition_name
    restano solo un'ETICHETTA (il campionato domestico principale del club
    attuale, se ci ha gia' giocato quella stagione) usata per il titolo
    nella UI; il dettaglio completo e' in `competitions`.
    """

    season_id: int
    season_label: str
    competition_id: str
    competition_name: str | None = None
    club_id: str | None = None
    appearances: int
    goals: int
    assists: int
    minutes_played: int
    starts: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    competitions: list[CompetitionStint] = []


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


_ALL_GAMES_CACHE_TTL_SECONDS = 60.0
_all_games_cache: dict[str, tuple[float, list[dict]]] = {}


def get_all_games(player_id: str) -> list[dict]:
    """Tutte le partite in carriera del giocatore (grezze). L'endpoint non
    supporta filtro lato server per stagione, quindi filtriamo lato nostro
    nelle funzioni piu' in alto (`get_recent_matches`/`get_season_summary`/
    `get_current_club_id`).

    Cache locale a breve TTL: import_player_from_transfermarkt chiama tutte
    e tre queste funzioni sullo stesso player_id nello stesso giro, quindi
    senza cache si rifà 3 volte la stessa richiesta pesante (l'intera
    carriera, anche centinaia di partite) — misurato dal vivo: un singolo
    import poteva superare il minuto, abbastanza da sembrare bloccato o far
    scadere la richiesta lato utente/proxy prima ancora di arrivare al
    salvataggio. 60s basta a coprire un giro di import/job senza rischiare
    di servire dati stantii al giro successivo.
    """
    cached = _all_games_cache.get(player_id)
    if cached is not None and time.monotonic() - cached[0] < _ALL_GAMES_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        data = _get(f"/player/{player_id}/performance-game")
    except httpx.HTTPError as exc:
        logger.error("Errore fetch performance-game per player_id=%s: %s", player_id, exc)
        return []
    games = data.get("data", {}).get("performance", [])

    if len(_all_games_cache) > 500:
        _all_games_cache.clear()
    _all_games_cache[player_id] = (time.monotonic(), games)
    return games


# Nome di una competizione/club non cambia mai durante la vita del processo:
# a differenza della cache sopra (a TTL, per dati che cambiano) questa resta
# valida per sempre e permette di non richiederlo di nuovo per lo stesso id,
# sia nello stesso import (list_season_options e get_recent_matches lo
# risolvono entrambe) sia tra giocatori diversi che condividono campionato/
# squadra (frequente nel job notturno).
_competition_name_cache: dict[str, str] = {}
_club_name_cache: dict[str, str] = {}


def resolve_competition_names(competition_ids: set[str]) -> dict[str, str]:
    if not competition_ids:
        return {}
    missing = competition_ids - _competition_name_cache.keys()
    if missing:
        try:
            data = _get("/competitions", params={"ids[]": sorted(missing)})
            for c in data.get("data", []):
                _competition_name_cache[c["id"]] = c["name"]
        except httpx.HTTPError as exc:
            logger.error("Errore risoluzione nomi competizioni %s: %s", missing, exc)
    return {cid: _competition_name_cache[cid] for cid in competition_ids if cid in _competition_name_cache}


def resolve_club_names(club_ids: set[str]) -> dict[str, str]:
    if not club_ids:
        return {}
    missing = club_ids - _club_name_cache.keys()
    if missing:
        try:
            data = _get("/clubs", params={"ids[]": sorted(missing)})
            for c in data.get("data", []):
                _club_name_cache[c["id"]] = c["name"]
        except httpx.HTTPError as exc:
            logger.error("Errore risoluzione nomi club %s: %s", missing, exc)
    return {cid: _club_name_cache[cid] for cid in club_ids if cid in _club_name_cache}


_club_primary_competition_cache: dict[str, str | None] = {}


def get_club_primary_competition(club_id: str) -> str | None:
    """Campionato domestico principale del club (dato ufficiale Transfermarkt,
    non una euristica): usato per scegliere la competizione 'principale' del
    giocatore in modo affidabile. Cache permanente come per i nomi sopra: non
    cambia durante la stagione, e il job notturno lo richiede per molti
    giocatori dello stesso club."""
    if club_id in _club_primary_competition_cache:
        return _club_primary_competition_cache[club_id]

    try:
        data = _get("/clubs", params={"ids[]": [club_id]})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch club_id=%s: %s", club_id, exc)
        return None
    clubs = data.get("data", [])
    primary_competition_id = clubs[0].get("baseDetails", {}).get("primaryCompetitionId") if clubs else None
    _club_primary_competition_cache[club_id] = primary_competition_id
    return primary_competition_id


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


def _was_starter(game: dict) -> bool:
    return bool(game["statistics"]["playingTimeStatistics"].get("isStarting"))


def _yellow_cards(game: dict) -> int:
    return game["statistics"]["cardStatistics"].get("yellowCardGross") or 0


def _was_sent_off(game: dict) -> bool:
    """Espulsione: cartellino rosso diretto o doppia ammonizione (secondo
    giallo -> rosso), le uniche due chiavi che tmapi usa per rappresentare
    un'espulsione nella singola partita."""
    cards = game["statistics"]["cardStatistics"]
    return bool(cards.get("redCard")) or bool(cards.get("yellowRedCard"))


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


def _aggregate_games(games: list[dict]) -> dict:
    return dict(
        appearances=len(games),
        goals=sum(g["statistics"]["goalStatistics"].get("goalsScoredTotal") or 0 for g in games),
        assists=sum(g["statistics"]["goalStatistics"].get("assists") or 0 for g in games),
        minutes_played=sum(g["statistics"]["playingTimeStatistics"].get("playedMinutes") or 0 for g in games),
        starts=sum(1 for g in games if _was_starter(g)),
        yellow_cards=sum(_yellow_cards(g) for g in games),
        red_cards=sum(1 for g in games if _was_sent_off(g)),
    )


def list_season_options(player_id: str, current_club_id: str, max_seasons: int = 6) -> list[SeasonSummary]:
    """Elenco delle ultime `max_seasons` stagioni giocate (piu' recente
    prima), piu' recente prima. Il totale di ciascuna somma TUTTE le
    competizioni e TUTTI i club di quella stagione (non solo il campionato
    principale del club attuale): un filtro solo sul club attuale perdeva
    silenziosamente le partite giocate con un altro club prima di un
    trasferimento a meta' stagione, e un filtro solo sul campionato
    principale perdeva le coppe/competizioni europee — in un caso reale
    riscontrato, un giocatore con 2 club e 4 competizioni in una stagione
    risultava con 3 goal invece dei ~16 reali. `competitions` porta il
    dettaglio completo per la UI (punto di riferimento restano
    Sofascore/Transfermarkt, che infatti mostrano sempre lo storico
    partite/goal suddiviso per competizione).
    """
    all_games = [g for g in get_all_games(player_id) if _was_played(g) and not g["gameInformation"].get("isNationalGame")]
    if not all_games:
        return []

    primary_competition_id = get_club_primary_competition(current_club_id)

    by_season: dict[int, list[dict]] = {}
    season_labels: dict[int, str] = {}
    for g in all_games:
        season_id = g["gameInformation"]["seasonId"]
        by_season.setdefault(season_id, []).append(g)
        season_labels[season_id] = g["gameInformation"]["season"].get("nonCyclicalName") or str(season_id)

    ordered_season_ids = sorted(by_season.keys(), reverse=True)[:max_seasons]

    all_competition_ids: set[str] = set()
    all_club_ids: set[str] = set()
    for season_id in ordered_season_ids:
        for g in by_season[season_id]:
            all_competition_ids.add(g["gameInformation"]["competitionId"])
            all_club_ids.add(g["clubsInformation"]["club"]["clubId"])
    comp_names = resolve_competition_names(all_competition_ids)
    club_names = resolve_club_names(all_club_ids)

    summaries: list[SeasonSummary] = []
    for season_id in ordered_season_ids:
        season_games = by_season[season_id]

        by_comp_club: dict[tuple[str, str], list[dict]] = {}
        for g in season_games:
            key = (g["gameInformation"]["competitionId"], g["clubsInformation"]["club"]["clubId"])
            by_comp_club.setdefault(key, []).append(g)

        competitions = [
            CompetitionStint(
                competition_id=comp_id,
                competition_name=comp_names.get(comp_id),
                club_id=club_id,
                club_name=club_names.get(club_id),
                **_aggregate_games(comp_club_games),
            )
            for (comp_id, club_id), comp_club_games in sorted(
                by_comp_club.items(), key=lambda kv: len(kv[1]), reverse=True
            )
        ]

        # Etichetta (competition_id/competition_name): il campionato
        # domestico principale del club ATTUALE se ci ha gia' giocato
        # questa stagione, altrimenti la competizione con piu' presenze in
        # assoluto quella stagione — solo per il titolo mostrato in UI, non
        # filtra piu' i numeri (che sono sempre il totale su tutto).
        club_season_games = [g for g in season_games if g["clubsInformation"]["club"]["clubId"] == current_club_id]
        label_source_games = club_season_games or season_games
        label_competition_id = _pick_competition_for_season(label_source_games, primary_competition_id)

        summaries.append(
            SeasonSummary(
                season_id=season_id,
                season_label=season_labels[season_id],
                competition_id=label_competition_id,
                competition_name=comp_names.get(label_competition_id),
                club_id=current_club_id,
                competitions=competitions,
                **_aggregate_games(season_games),
            )
        )

    return summaries


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


def get_date_of_birth(player_id: str) -> date | None:
    """Data di nascita anagrafica, usata per calcolare l'eta' del
    giocatore. La ricerca Transfermarkt usata per l'import (schnellsuche)
    non la restituisce mai, quindi va recuperata qui separatamente.
    """
    try:
        data = _get("/players", params={"ids[]": [player_id]})
    except httpx.HTTPError as exc:
        logger.error("Errore fetch anagrafica per player_id=%s: %s", player_id, exc)
        return None

    players = data.get("data", [])
    if not players:
        return None

    raw_dob = players[0].get("lifeDates", {}).get("dateOfBirth")
    if not raw_dob:
        return None
    return date.fromisoformat(raw_dob[:10])


_LOAN_TYPES = {"ACTIVE_LOAN_TRANSFER", "RETURNED_FROM_PREVIOUS_LOAN"}


def get_transfer_history(player_id: str) -> list[TransferRecord]:
    """Storico completo dei trasferimenti di carriera (piu' recente prima),
    inclusi prestiti e trasferimenti a parametro zero. I giovanili (settore
    giovanile dello stesso club) restano inclusi cosi' come li restituisce
    Transfermarkt: e' lo scout a valutarne la rilevanza.
    """
    try:
        data = _get(f"/transfer/history/player/{player_id}")
    except httpx.HTTPError as exc:
        logger.error("Errore fetch transfer history per player_id=%s: %s", player_id, exc)
        return []

    entries = data.get("data", {}).get("history", {}).get("terminated", [])
    if not entries:
        return []

    club_ids = set()
    for entry in entries:
        source_id = entry.get("transferSource", {}).get("clubId")
        dest_id = entry.get("transferDestination", {}).get("clubId")
        if source_id:
            club_ids.add(source_id)
        if dest_id:
            club_ids.add(dest_id)
    club_names = resolve_club_names(club_ids)

    records = []
    for entry in entries:
        details = entry.get("details", {})
        transfer_type = entry.get("typeDetails", {}).get("type", "")
        fee = details.get("fee") or {}
        fee_compact = fee.get("compact", {}).get("content", "")
        market_value = details.get("marketValue") or {}
        club_from_id = entry.get("transferSource", {}).get("clubId")
        club_to_id = entry.get("transferDestination", {}).get("clubId")

        records.append(
            TransferRecord(
                transfer_id=entry["id"],
                transfer_date=details["date"][:10],
                club_from_id=club_from_id,
                club_from_name=club_names.get(club_from_id),
                club_to_id=club_to_id,
                club_to_name=club_names.get(club_to_id),
                fee_eur=fee.get("value"),
                market_value_eur=market_value.get("value"),
                is_loan=transfer_type in _LOAN_TYPES,
                is_free_transfer="free" in fee_compact.lower(),
                season_label=details.get("season", {}).get("nonCyclicalName"),
            )
        )

    records.sort(key=lambda r: r.transfer_date, reverse=True)
    return records


def get_market_value_history(player_id: str, years: int = 2) -> list[MarketValuePoint]:
    """Storico valore di mercato reale (piu' vecchio prima), limitato agli
    ultimi `years` anni: sufficiente per un grafico di trend utile senza
    scaricare l'intera carriera ogni volta.
    """
    try:
        data = _get(f"/player/{player_id}/market-value-history")
    except httpx.HTTPError as exc:
        logger.error("Errore fetch market-value-history per player_id=%s: %s", player_id, exc)
        return []

    entries = data.get("data", {}).get("history", [])
    if not entries:
        return []

    cutoff = date.today().replace(year=date.today().year - years)
    points = []
    for entry in entries:
        mv = entry.get("marketValue") or {}
        determined = mv.get("determined")
        value = mv.get("value")
        if not determined or value is None:
            continue
        recorded_at = date.fromisoformat(determined[:10])
        if recorded_at < cutoff:
            continue
        points.append(MarketValuePoint(recorded_at=recorded_at, value_eur=float(value)))

    points.sort(key=lambda p: p.recorded_at)
    return points
