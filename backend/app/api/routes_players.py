from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.player import (
    PlayerDetail,
    PlayerRow,
    PlayerSearchResult,
    PlayerSeasonOption,
    PlayerTransfer,
    SofascoreLinkRequest,
    WatchlistAddRequest,
    WatchlistImportRequest,
    WatchlistSummary,
    WatchlistUpdateRequest,
)
from app.services import player_service

router = APIRouter(prefix="/api", tags=["players"])


@router.get("/watchlist", response_model=list[PlayerRow])
def get_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlayerRow]:
    return player_service.get_watchlist_rows(db, current_user.id)


@router.get("/watchlist/summary", response_model=WatchlistSummary)
def get_watchlist_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistSummary:
    return player_service.get_watchlist_summary(db, current_user.id)


@router.post("/watchlist", response_model=PlayerRow, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    payload: WatchlistAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerRow:
    player_service.add_to_watchlist(db, current_user.id, payload.player_id, payload.notes, payload.tags)
    row = player_service.get_player_detail(db, current_user.id, payload.player_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")
    return row


@router.post("/watchlist/import", response_model=PlayerRow, status_code=status.HTTP_201_CREATED)
def import_from_transfermarkt(
    payload: WatchlistImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerRow:
    """Importa un giocatore reale trovato via Transfermarkt (non ancora nel
    nostro DB) e lo aggiunge subito alla watchlist, provando anche a
    collegare Sofascore per rating/xG/xA/statistiche stagionali.
    """
    player = player_service.import_player_from_transfermarkt(
        db,
        current_user.id,
        payload.transfermarkt_id,
        payload.full_name,
        payload.current_team,
        payload.position,
        payload.nationality,
        payload.market_value_eur,
        payload.photo_url,
    )
    if player is None:
        raise HTTPException(
            status_code=502,
            detail="Impossibile importare il giocatore da Transfermarkt (giocatore non trovato)",
        )
    row = player_service.get_player_detail(db, current_user.id, player.id)
    assert row is not None
    return row


@router.post("/players/{player_id}/sofascore-link", response_model=PlayerRow)
def link_sofascore(
    player_id: int,
    payload: SofascoreLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerRow:
    """Collegamento manuale al profilo Sofascore corretto, per i casi in cui
    il matching automatico per nome+squadra fallisce o e' ambiguo (omonimie).
    """
    player = player_service.link_sofascore_manual(
        db, current_user.id, player_id, payload.sofascore_url_or_id
    )
    if player is None:
        raise HTTPException(
            status_code=422,
            detail="URL/id Sofascore non valido o profilo senza statistiche disponibili",
        )
    row = player_service.get_player_detail(db, current_user.id, player.id)
    assert row is not None
    return row


@router.patch("/watchlist/{player_id}", response_model=PlayerRow)
def update_watchlist(
    player_id: int,
    payload: WatchlistUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerRow:
    entry = player_service.update_watchlist_entry(db, current_user.id, player_id, payload.notes, payload.tags)
    if entry is None:
        raise HTTPException(status_code=404, detail="Il giocatore non e' in watchlist")
    row = player_service.get_player_detail(db, current_user.id, player_id)
    assert row is not None
    return row


@router.delete("/watchlist/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_from_watchlist(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    removed = player_service.remove_from_watchlist(db, current_user.id, player_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Il giocatore non e' in watchlist")


@router.get("/players/search", response_model=list[PlayerSearchResult])
def search_players(
    q: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlayerSearchResult]:
    return player_service.search_all_players(db, current_user.id, q)


@router.get("/players/{player_id}/seasons", response_model=list[PlayerSeasonOption])
def get_player_seasons(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlayerSeasonOption]:
    """Ultime stagioni con dati reali per il club attuale del giocatore
    (piu' recente prima), per il selettore stagioni nella pagina di
    dettaglio. Sola lettura: non modifica i dati 'correnti' del giocatore.
    """
    options = player_service.get_player_season_options(db, player_id)
    return [
        PlayerSeasonOption(
            season_id=o.season_id,
            season_label=o.season_label,
            competition_name=o.competition_name,
            appearances=o.appearances,
            goals=o.goals,
            assists=o.assists,
            minutes_played=o.minutes_played,
        )
        for o in options
    ]


@router.get("/players/{player_id}/transfers", response_model=list[PlayerTransfer])
def get_player_transfers(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlayerTransfer]:
    """Storico trasferimenti di carriera (piu' recente prima), per la
    sezione dedicata nella pagina di dettaglio.
    """
    transfers = player_service.get_player_transfer_history(db, player_id)
    return [
        PlayerTransfer(
            transfer_id=t.transfer_id,
            transfer_date=t.transfer_date,
            club_from_id=t.club_from_id,
            club_from_name=t.club_from_name,
            club_to_id=t.club_to_id,
            club_to_name=t.club_to_name,
            fee_eur=t.fee_eur,
            market_value_eur=t.market_value_eur,
            is_loan=t.is_loan,
            is_free_transfer=t.is_free_transfer,
            season_label=t.season_label,
        )
        for t in transfers
    ]


@router.get("/players/{player_id}", response_model=PlayerDetail)
def get_player(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerDetail:
    detail = player_service.get_player_detail(db, current_user.id, player_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")
    return detail
