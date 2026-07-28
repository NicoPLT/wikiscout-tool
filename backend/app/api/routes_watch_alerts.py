from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.watch_alert import WatchAlertOut
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


@router.post("/watch-alerts/{alert_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_watch_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ok = watch_alert_service.dismiss_alert(db, current_user.id, alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert non trovato")
