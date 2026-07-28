"""Repository/service layer per l'accesso ai dati giocatori.

Questo modulo e' l'unico punto in cui l'API legge/scrive le tabelle players,
player_stats_matches, player_market_value_history e watchlists. Che i dati
in queste tabelle siano stati scritti dal seed di mock (Fase A) o dal job
notturno di scraping reale (Fase B) e' del tutto trasparente qui: cambia solo
chi popola le tabelle, non come vengono lette. Frontend e modello dati non
vanno mai toccati passando da A a B.
"""

import logging
import re
import unicodedata
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.market_value import PlayerMarketValueHistory
from app.models.player import Player
from app.models.stats import PlayerStatsMatch
from app.models.watchlist import Watchlist
from app.schemas.player import (
    MarketValuePoint,
    MarketValueTrendPoint,
    MatchStatLine,
    PlayerDetail,
    PlayerRow,
    PlayerSearchResult,
    RecentUpdateItem,
    WatchlistSummary,
)
from app.schemas.tag import TagOut
from app.scrapers import fotmob, sofascore, transfermarkt, transfermarkt_performance
from app.services.cache_service import cache_delete_prefix, cache_get, cache_set

logger = logging.getLogger(__name__)

WATCHLIST_CACHE_PREFIX = "watchlist:user:"


def _compute_age(date_of_birth: date | None) -> int | None:
    if date_of_birth is None:
        return None
    today = date.today()
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def _player_to_row(player: Player, watchlist_entry: Watchlist | None) -> PlayerRow:
    return PlayerRow(
        id=player.id,
        full_name=player.full_name,
        photo_url=player.photo_url,
        current_team=player.current_team,
        league=player.league,
        position=player.position,
        age=_compute_age(player.date_of_birth),
        market_value_eur=float(player.market_value_eur) if player.market_value_eur is not None else None,
        market_value_change_eur=(
            float(player.market_value_change_eur) if player.market_value_change_eur is not None else None
        ),
        market_value_change_pct=(
            float(player.market_value_change_pct) if player.market_value_change_pct is not None else None
        ),
        goals_last5=player.goals_last5,
        assists_last5=player.assists_last5,
        goals_season=player.goals_season,
        assists_season=player.assists_season,
        appearances_season=player.appearances_season,
        minutes_season=player.minutes_season,
        season_label=player.season_label,
        rating_avg=float(player.rating_avg) if player.rating_avg is not None else None,
        is_xg_covered=player.is_xg_covered,
        xg_season=float(player.xg_season) if player.xg_season is not None else None,
        xa_season=float(player.xa_season) if player.xa_season is not None else None,
        watchlist_notes=watchlist_entry.notes if watchlist_entry else None,
        watchlist_tags=watchlist_entry.tags if watchlist_entry else None,
        tag=(
            TagOut(id=watchlist_entry.tag.id, name=watchlist_entry.tag.name, color=watchlist_entry.tag.color)
            if watchlist_entry and watchlist_entry.tag
            else None
        ),
        last_synced_at=player.last_synced_at,
    )


def get_watchlist_rows(db: Session, user_id: int, use_cache: bool = True) -> list[PlayerRow]:
    cache_key = f"{WATCHLIST_CACHE_PREFIX}{user_id}"
    if use_cache:
        cached = cache_get(cache_key)
        if cached is not None:
            return [PlayerRow.model_validate(row) for row in cached]

    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .options(selectinload(Watchlist.player), selectinload(Watchlist.tag))
    )
    entries = db.execute(stmt).scalars().all()

    # Risolta qui (non solo aprendo la singola scheda) cosi' l'eta' compare
    # in anteprima per tutta la watchlist in dashboard, non solo per i
    # giocatori gia' visitati singolarmente. Costo contenuto: una sola volta
    # per giocatore (persistita), e comunque protetto dalla cache qui sopra.
    changed = False
    for entry in entries:
        changed = resolve_date_of_birth(entry.player) or changed
    if changed:
        db.commit()

    rows = [_player_to_row(entry.player, entry) for entry in entries]

    cache_set(cache_key, [row.model_dump() for row in rows])
    return rows


def invalidate_watchlist_cache(user_id: int) -> None:
    cache_delete_prefix(f"{WATCHLIST_CACHE_PREFIX}{user_id}")


def get_player_detail(db: Session, user_id: int, player_id: int) -> PlayerDetail | None:
    player = db.get(Player, player_id)
    if player is None:
        return None

    # Risolti qui (non solo a import/job notturno) cosi' compaiono alla
    # prima apertura della scheda invece di aspettare il giro notturno,
    # per i giocatori importati prima che questi campi esistessero.
    changed = resolve_fotmob_link(player)
    changed = resolve_date_of_birth(player) or changed
    if changed:
        db.commit()
        # La dashboard legge la watchlist da cache (fino a CACHE_TTL_SECONDS):
        # senza invalidarla qui, un campo risolto al volo aprendo la scheda
        # (eta', link Fotmob) non si vedrebbe in dashboard finche' la cache
        # non scade da sola.
        invalidate_watchlist_cache(user_id)

    watchlist_entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()

    recent_matches = sorted(player.stats_matches, key=lambda m: m.match_date, reverse=True)[:20]
    market_history = sorted(player.market_value_history, key=lambda m: m.recorded_at)

    row = _player_to_row(player, watchlist_entry)
    return PlayerDetail(
        **row.model_dump(),
        starts_season=player.starts_season,
        yellow_cards_season=player.yellow_cards_season,
        red_cards_season=player.red_cards_season,
        date_of_birth=player.date_of_birth,
        nationality=player.nationality,
        transfermarkt_id=player.transfermarkt_id,
        api_football_id=player.api_football_id,
        sofascore_id=player.sofascore_id,
        fotmob_id=player.fotmob_id,
        stats_updated_at=player.stats_updated_at,
        market_value_updated_at=player.market_value_updated_at,
        rating_updated_at=player.rating_updated_at,
        recent_matches=[MatchStatLine.model_validate(m) for m in recent_matches],
        market_value_history=[MarketValuePoint.model_validate(m) for m in market_history],
    )


def search_all_players(db: Session, user_id: int, query: str) -> list[PlayerSearchResult]:
    """Autocomplete: unisce i giocatori gia' nel nostro DB con una ricerca live
    su Transfermarkt, cosi' lo scout puo' trovare e aggiungere QUALSIASI
    giocatore reale, non solo quelli gia' importati. Nessun vincolo di
    stagione (a differenza della vecchia integrazione API-Football).
    """
    stmt = select(Player).where(Player.full_name.ilike(f"%{query}%")).limit(20)
    local_players = db.execute(stmt).scalars().all()

    watchlisted_ids = set(
        db.execute(select(Watchlist.player_id).where(Watchlist.user_id == user_id)).scalars().all()
    )
    known_transfermarkt_ids = set(
        db.execute(select(Player.transfermarkt_id).where(Player.transfermarkt_id.is_not(None))).scalars().all()
    )
    # Nome dei giocatori gia' in watchlist di QUESTO utente: serve per
    # escludere i candidati Transfermarkt che rappresentano lo stesso
    # giocatore reale ma non hanno ancora un transfermarkt_id salvato in
    # locale (es. giocatori del seed mock, o importati prima che questo
    # campo esistesse) — senza questo controllo known_transfermarkt_ids da
    # solo non basta a evitare di re-importarlo come riga duplicata.
    watchlisted_names = {
        name.strip().lower()
        for name in db.execute(
            select(Player.full_name)
            .join(Watchlist, Watchlist.player_id == Player.id)
            .where(Watchlist.user_id == user_id)
        ).scalars()
    }

    results = [
        PlayerSearchResult(
            source="local",
            id=p.id,
            full_name=p.full_name,
            current_team=p.current_team,
            league=p.league,
            photo_url=p.photo_url,
            in_watchlist=p.id in watchlisted_ids,
        )
        for p in local_players
    ]

    if len(query.strip()) >= 2:
        for candidate in transfermarkt.search_players_transfermarkt(query):
            tm_id = candidate["transfermarkt_id"]
            if tm_id in known_transfermarkt_ids:
                continue  # gia' rappresentato tra i risultati locali
            if candidate["full_name"].strip().lower() in watchlisted_names:
                continue  # stesso giocatore gia' in watchlist, solo senza transfermarkt_id risolto

            results.append(
                PlayerSearchResult(
                    source="transfermarkt",
                    transfermarkt_id=tm_id,
                    full_name=candidate["full_name"],
                    current_team=candidate["current_team"],
                    league=None,
                    photo_url=candidate["photo_url"],
                    in_watchlist=False,
                    position=candidate["position"],
                    nationality=candidate["nationality"],
                    market_value_eur=candidate["market_value_eur"],
                )
            )

    return results[:20]


def import_player_from_transfermarkt(
    db: Session,
    user_id: int,
    transfermarkt_id: str,
    full_name: str,
    current_team: str | None,
    position: str | None,
    nationality: str | None,
    market_value_eur: float | None,
    photo_url: str | None,
) -> Player | None:
    """Crea (se non esiste) un giocatore reale a partire dai dati del
    candidato Transfermarkt gia' ottenuti in fase di ricerca (Transfermarkt
    si cerca per NOME, non per id: non ha senso ri-cercare l'id come se
    fosse un nome, per questo il chiamante passa i dati gia' noti invece di
    un semplice id). Prova poi a risolvere il mapping Sofascore per
    nome+squadra e a popolare statistiche stagionali/ultime partite reali.
    Se il mapping Sofascore fallisce o e' ambiguo, il giocatore viene
    comunque aggiunto (con dati Transfermarkt) e lo scout potra' collegare
    Sofascore manualmente in un secondo momento.
    """
    existing = db.execute(
        select(Player).where(Player.transfermarkt_id == transfermarkt_id)
    ).scalar_one_or_none()
    if existing is not None:
        add_to_watchlist(db, user_id, existing.id, None, None)
        return existing

    # Difesa in profondita': se un candidato Transfermarkt duplicato di un
    # giocatore gia' in watchlist di questo utente (stesso nome, ma senza
    # transfermarkt_id risolto in locale) arriva comunque fin qui nonostante
    # il filtro in search_all_players, evita di creare una seconda riga
    # Player per la stessa persona reale.
    duplicate_in_watchlist = db.execute(
        select(Player)
        .join(Watchlist, Watchlist.player_id == Player.id)
        .where(Watchlist.user_id == user_id, func.lower(Player.full_name) == full_name.strip().lower())
    ).scalars().first()
    if duplicate_in_watchlist is not None:
        return duplicate_in_watchlist

    player = Player(
        full_name=full_name,
        nationality=nationality,
        position=position,
        current_team=current_team,
        photo_url=photo_url,
        transfermarkt_id=transfermarkt_id,
        market_value_eur=market_value_eur,
        market_value_updated_at=datetime.now(timezone.utc) if market_value_eur is not None else None,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(player)
    db.flush()

    _apply_transfermarkt_performance(db, player)
    _backfill_market_value_history(db, player)
    resolve_fotmob_link(player)
    resolve_date_of_birth(player)

    with sofascore.SofascoreSession() as session:
        link_sofascore_profile(db, session, player)

    db.commit()
    db.refresh(player)

    add_to_watchlist(db, user_id, player.id, None, None)
    return player


def _apply_transfermarkt_performance(db: Session, player: Player) -> bool:
    """Statistiche stagionali (campionato principale del club attuale) e
    ultime partite reali, dal client diretto verso l'API interna di
    Transfermarkt (vedi app/scrapers/transfermarkt_performance.py). Fonte
    primaria per goal/assist/presenze/minuti: Sofascore resta solo per
    rating/xG/xA, che Transfermarkt non ha mai pubblicato.
    """
    if not player.transfermarkt_id:
        return False

    club_id = transfermarkt_performance.get_current_club_id(player.transfermarkt_id)
    if club_id is None:
        return False

    updated = False

    season_summary = transfermarkt_performance.get_season_summary(player.transfermarkt_id, club_id)
    if season_summary is not None:
        player.league = season_summary.competition_name or player.league
        player.season_label = season_summary.season_label
        player.goals_season = season_summary.goals
        player.assists_season = season_summary.assists
        player.appearances_season = season_summary.appearances
        player.minutes_season = season_summary.minutes_played
        player.starts_season = season_summary.starts
        player.yellow_cards_season = season_summary.yellow_cards
        player.red_cards_season = season_summary.red_cards
        player.stats_updated_at = datetime.now(timezone.utc)
        updated = True

    recent_matches = transfermarkt_performance.get_recent_matches(player.transfermarkt_id, limit=5)
    if recent_matches:
        existing_refs = {
            ref
            for ref in db.execute(
                select(PlayerStatsMatch.external_ref).where(PlayerStatsMatch.player_id == player.id)
            ).scalars()
            if ref
        }
        new_rows = [
            PlayerStatsMatch(
                player_id=player.id,
                match_date=m.match_date,
                competition=m.competition_name or m.competition_id,
                opponent=m.opponent_name or m.opponent_id or "N/D",
                is_home=m.is_home,
                minutes_played=m.minutes_played,
                goals=m.goals,
                assists=m.assists,
                rating=None,
                xg=None,
                xa=None,
                source="transfermarkt-leistungsdaten",
                external_ref=m.external_ref,
            )
            for m in recent_matches
            if m.external_ref not in existing_refs
        ]
        if new_rows:
            db.add_all(new_rows)
            db.flush()

        player.goals_last5 = sum(m.goals for m in recent_matches[:5])
        player.assists_last5 = sum(m.assists for m in recent_matches[:5])
        updated = True

    return updated


def _backfill_market_value_history(db: Session, player: Player) -> bool:
    """Inserisce nello storico i punti di valore di mercato REALI (ultimi ~2
    anni) recuperati da Transfermarkt, cosi' il grafico di trend nella
    scheda giocatore mostra da subito un andamento vero invece di un solo
    punto (quello dell'import) che si arricchirebbe lentamente nel tempo coi
    soli snapshot settimanali del job notturno. Idempotente: salta le date
    gia' presenti, quindi rilanciarla (es. ogni notte) non duplica nulla.
    """
    if not player.transfermarkt_id:
        return False

    points = transfermarkt_performance.get_market_value_history(player.transfermarkt_id, years=2)
    if not points:
        return False

    existing_dates = set(
        db.execute(
            select(PlayerMarketValueHistory.recorded_at).where(PlayerMarketValueHistory.player_id == player.id)
        ).scalars()
    )

    new_rows = [
        PlayerMarketValueHistory(
            player_id=player.id,
            value_eur=point.value_eur,
            recorded_at=point.recorded_at,
            source="transfermarkt-history",
        )
        for point in points
        if point.recorded_at not in existing_dates
    ]
    if not new_rows:
        return False

    db.add_all(new_rows)
    db.flush()
    return True


def resolve_date_of_birth(player: Player) -> bool:
    """Recupera e salva la data di nascita da Transfermarkt se mancante
    (la ricerca usata per l'import non la restituisce mai): serve per
    calcolare l'eta' mostrata in dashboard e nella scheda giocatore."""
    if player.date_of_birth or not player.transfermarkt_id:
        return False
    dob = transfermarkt_performance.get_date_of_birth(player.transfermarkt_id)
    if not dob:
        return False
    player.date_of_birth = dob
    return True


def resolve_fotmob_link(player: Player) -> bool:
    """Prova a risolvere e collegare l'id Fotmob del giocatore, per il link
    diretto nella scheda giocatore (sola identificazione: nessuna
    statistica viene letta da Fotmob). Non fa nulla se gia' collegato o se
    il match e' ambiguo (vedi fotmob.resolve_fotmob_id)."""
    if player.fotmob_id:
        return False
    fotmob_id = fotmob.resolve_fotmob_id(player.full_name, player.current_team)
    if not fotmob_id:
        return False
    player.fotmob_id = fotmob_id
    return True


def get_player_season_options(db: Session, player_id: int) -> list["transfermarkt_performance.SeasonSummary"]:
    """Elenco delle ultime stagioni con dati reali per il club attuale del
    giocatore (piu' recente prima), per il selettore stagioni nella pagina
    di dettaglio — stesso pattern del menu a tendina di Sofascore/Transfermarkt.
    Non scrive nulla sul giocatore: e' solo per la visualizzazione, la
    'stagione corrente' mostrata in tabella resta quella scelta
    automaticamente da _apply_transfermarkt_performance.
    """
    player = db.get(Player, player_id)
    if player is None or not player.transfermarkt_id:
        return []

    club_id = transfermarkt_performance.get_current_club_id(player.transfermarkt_id)
    if club_id is None:
        return []

    return transfermarkt_performance.list_season_options(player.transfermarkt_id, club_id, max_seasons=6)


def get_player_transfer_history(db: Session, player_id: int) -> list["transfermarkt_performance.TransferRecord"]:
    """Storico trasferimenti di carriera (piu' recente prima), per la
    scheda giocatore. Sola lettura, dato live da Transfermarkt: non viene
    persistito sul giocatore.
    """
    player = db.get(Player, player_id)
    if player is None or not player.transfermarkt_id:
        return []

    return transfermarkt_performance.get_transfer_history(player.transfermarkt_id)


def link_sofascore_profile(db: Session, session: "sofascore.SofascoreSession", player: Player) -> bool:
    """Prova a risolvere e collegare il profilo Sofascore di `player` (per
    nome+squadra attuale) e, se riesce, popola subito statistiche stagionali
    e ultime partite reali. Ritorna True se il collegamento e' riuscito.
    Ambiguo/non trovato -> non tocca nulla, il chiamante decide come gestirlo
    (import automatico: lascia N/D; link manuale: segnala allo scout).
    """
    if not session.ok:
        return False

    candidates = sofascore.search_players(session, player.full_name)
    match = _best_sofascore_match(candidates, player.current_team)
    logger.info(
        "Sofascore match per '%s' (squadra Transfermarkt='%s'): %s candidati -> scelto %s",
        player.full_name,
        player.current_team,
        len(candidates),
        match,
    )
    if match is None:
        return False

    return _apply_sofascore_link(db, session, player, match["id"])


_CLUB_NAME_STOPWORDS = {
    "fc", "cf", "ac", "as", "sc", "cd", "sd", "ud", "afc", "cfc", "ssc",
    "calcio", "club",
}
# NOTA: parole come "city"/"united"/"town"/"real" NON vanno mai messe negli
# stopword: sono spesso l'UNICA parola che distingue due squadre diverse
# della stessa citta' (es. Manchester City / Manchester United) — toglierle
# farebbe erroneamente combaciare due club distinti.

_CLUB_NAME_ABBREVIATIONS = {
    "man": "manchester",
    "utd": "united",
    "munchen": "munich",
    "atl": "atletico",
    "inter": "internazionale",
}


def _normalize_club_name(name: str) -> set[str]:
    """Normalizza un nome squadra in un insieme di parole significative
    (minuscole, senza accenti, senza sigle generiche come 'FC', abbreviazioni
    comuni espanse), per confrontare nomi scritti in modo leggermente
    diverso tra Transfermarkt e Sofascore (es. 'Manchester City' vs
    'Man City', 'Atletico Madrid' vs 'Atl. Madrid')."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", without_accents.lower())
    expanded = {_CLUB_NAME_ABBREVIATIONS.get(w, w) for w in words}
    return {w for w in expanded if w not in _CLUB_NAME_STOPWORDS}


def _teams_match(team_a: str, team_b: str) -> bool:
    words_a = _normalize_club_name(team_a)
    words_b = _normalize_club_name(team_b)
    if not words_a or not words_b:
        return False
    # Match se le parole significative di uno sono un sottoinsieme dell'altro
    # (gestisce sia forme abbreviate "Man City" sia nomi completi diversi).
    return words_a <= words_b or words_b <= words_a


def _best_sofascore_match(candidates: list[dict], current_team: str | None) -> dict | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if not current_team:
        return None  # piu' di un omonimo e nessuna squadra per disambiguare: ambiguo

    team_matches = [c for c in candidates if c.get("team") and _teams_match(current_team, c["team"])]
    if len(team_matches) == 1:
        return team_matches[0]
    return None  # 0 o piu' di 1 match per squadra: resta ambiguo, non indoviniamo


def _apply_sofascore_link(db: Session, session: "sofascore.SofascoreSession", player: Player, sofascore_id: int) -> bool:
    """Sofascore resta la fonte SOLO per rating/xG/xA (dati che Transfermarkt
    non ha mai pubblicato): goal/assist/presenze/minuti/campionato vengono
    ormai da Transfermarkt (vedi _apply_transfermarkt_performance)."""
    player.sofascore_id = str(sofascore_id)

    season_stats = sofascore.get_season_stats(session, sofascore_id)
    if season_stats:
        player.is_xg_covered = season_stats["xg_season"] is not None
        if season_stats["rating_avg"] is not None:
            player.rating_avg = season_stats["rating_avg"]
            player.rating_updated_at = datetime.now(timezone.utc)
        if season_stats["xg_season"] is not None:
            player.xg_season = season_stats["xg_season"]
        if season_stats["xa_season"] is not None:
            player.xa_season = season_stats["xa_season"]

    return True


def link_sofascore_manual(db: Session, user_id: int, player_id: int, sofascore_url_or_id: str) -> Player | None:
    """Collegamento manuale (fallback quando l'auto-match fallisce/e' ambiguo):
    lo scout incolla l'URL del profilo Sofascore corretto (o il solo id
    numerico finale), e ricalcoliamo subito statistiche/ultime partite reali.
    """
    player = db.get(Player, player_id)
    if player is None:
        return None

    digits = re.search(r"(\d+)\D*$", sofascore_url_or_id.strip())
    if not digits:
        return None
    sofascore_id = int(digits.group(1))

    with sofascore.SofascoreSession() as session:
        ok = _apply_sofascore_link(db, session, player, sofascore_id)
    if not ok:
        return None

    db.commit()
    db.refresh(player)
    invalidate_watchlist_cache(user_id)
    return player


def add_to_watchlist(db: Session, user_id: int, player_id: int, notes: str | None, tags: list[str] | None) -> Watchlist:
    existing = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if existing:
        return existing

    entry = Watchlist(user_id=user_id, player_id=player_id, notes=notes, tags=tags)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    invalidate_watchlist_cache(user_id)
    return entry


def update_watchlist_entry(
    db: Session, user_id: int, player_id: int, notes: str | None, tags: list[str] | None
) -> Watchlist | None:
    entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if entry is None:
        return None

    if notes is not None:
        entry.notes = notes
    if tags is not None:
        entry.tags = tags
    db.commit()
    db.refresh(entry)
    invalidate_watchlist_cache(user_id)
    return entry


def remove_from_watchlist(db: Session, user_id: int, player_id: int) -> bool:
    """Rimuove il giocatore dalla watchlist. Se nessun altro utente lo ha in
    watchlist, elimina anche la riga players (con cascade su statistiche e
    storico valore di mercato): una volta rimosso, non deve piu' comparire da
    nessuna parte (dashboard, ricerca locale, ecc.), non solo sparire dalla
    lista corrente.
    """
    entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if entry is None:
        return False

    db.delete(entry)
    db.flush()

    other_owner = db.execute(
        select(Watchlist.id).where(Watchlist.player_id == player_id)
    ).first()
    if other_owner is None:
        player = db.get(Player, player_id)
        if player is not None:
            db.delete(player)

    db.commit()
    invalidate_watchlist_cache(user_id)
    return True


def get_watchlist_summary(db: Session, user_id: int) -> WatchlistSummary:
    """Aggrega i dati della watchlist per i widget di sintesi della dashboard
    (gauge rating medio, trend valore di mercato, lista ultimi aggiornamenti).
    """
    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .options(selectinload(Watchlist.player).selectinload(Player.market_value_history))
    )
    entries = db.execute(stmt).scalars().all()
    players = [entry.player for entry in entries]

    ratings = [float(p.rating_avg) for p in players if p.rating_avg is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    total_market_value = sum(float(p.market_value_eur or 0) for p in players)

    # Trend aggregato: allinea gli storici per posizione (i punti del seed sono
    # generati con la stessa cadenza per ogni giocatore); ogni indice diventa
    # un punto del grafico sommando i valori di tutti i giocatori a quell'indice.
    histories = [sorted(p.market_value_history, key=lambda h: h.recorded_at) for p in players]
    max_len = max((len(h) for h in histories), default=0)
    trend: list[MarketValueTrendPoint] = []
    for i in range(max_len):
        total = 0.0
        latest_date = None
        for h in histories:
            if i < len(h):
                total += float(h[i].value_eur)
                if latest_date is None or h[i].recorded_at > latest_date:
                    latest_date = h[i].recorded_at
            elif h:
                total += float(h[-1].value_eur)
        if latest_date is not None:
            trend.append(MarketValueTrendPoint(recorded_at=latest_date, total_value_eur=round(total, 2)))

    recent_updates: list[RecentUpdateItem] = []
    for p in players:
        if p.market_value_updated_at is not None:
            recent_updates.append(
                RecentUpdateItem(
                    player_id=p.id,
                    full_name=p.full_name,
                    photo_url=p.photo_url,
                    kind="market_value",
                    label="Valore di mercato aggiornato",
                    change_pct=float(p.market_value_change_pct) if p.market_value_change_pct is not None else None,
                    at=p.market_value_updated_at,
                )
            )
        if p.rating_updated_at is not None:
            recent_updates.append(
                RecentUpdateItem(
                    player_id=p.id,
                    full_name=p.full_name,
                    photo_url=p.photo_url,
                    kind="rating",
                    label=f"Rating aggiornato a {p.rating_avg}",
                    change_pct=None,
                    at=p.rating_updated_at,
                )
            )
    recent_updates.sort(key=lambda item: item.at, reverse=True)

    return WatchlistSummary(
        players_count=len(players),
        avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
        total_market_value_eur=round(total_market_value, 2),
        market_value_trend=trend,
        recent_updates=recent_updates[:8],
    )
