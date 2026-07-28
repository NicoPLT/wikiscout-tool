from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.watch_alert import ManualWatchAlertCreate, WatchAlertOut
from app.services import watch_alert_service

router = APIRouter(prefix="/api", tags=["watch-alerts"])


@router.get("/watch-alerts", response_model=list[WatchAlertOut])
def get_watch_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WatchAlertOut]:
    """Alert 'One to Watch' attivi (non scartati) per i giocatori nella
    watchlist di questo utente, piu' recenti prima."""
    alerts = watch_alert_service.list_active_alerts(db, current_user.id)
    return [WatchAlertOut.model_validate(a) for a in alerts]


@router.post("/watch-alerts", response_model=WatchAlertOut, status_code=status.HTTP_201_CREATED)
def create_manual_watch_alert(
    payload: ManualWatchAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchAlertOut:
    """Segnalazione manuale (punto 5): il giocatore deve gia' esistere
    localmente (il frontend lo importa prima se necessario, riusando lo
    stesso componente di ricerca dell'header). Se non e' ancora nella
    watchlist di questo utente, ce lo aggiunge."""
    from app.models.player import Player

    if db.get(Player, payload.player_id) is None:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")

    alert = watch_alert_service.create_manual_alert(db, current_user.id, payload.player_id, payload.clean_note)
    return WatchAlertOut.model_validate(alert)


@router.post("/watch-alerts/{alert_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_watch_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ok = watch_alert_service.dismiss_alert(db, current_user.id, alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert non trovato")
