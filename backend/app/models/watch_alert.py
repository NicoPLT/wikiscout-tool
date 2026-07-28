import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class WatchAlertTriggerType(str, enum.Enum):
    """Criteri di rilevamento automatico per 'One to Watch'. None (nessun
    valore, vedi PlayerWatchAlert.trigger_type) identifica invece una
    segnalazione aggiunta manualmente dallo scout."""

    rating_streak = "rating_streak"
    goal_streak = "goal_streak"
    assist_streak = "assist_streak"
    recent_transfer = "recent_transfer"
    market_value_spike = "market_value_spike"


class PlayerWatchAlert(Base):
    """Segnalazione 'One to Watch': un giocatore in watchlist che sta
    performando meglio del solito (o segnalato a mano dallo scout). Un
    giocatore puo' avere piu' alert attivi contemporaneamente: non si
    deduplica a livello di giocatore, ogni criterio soddisfatto e' una riga
    distinta (vedi watch_alert_service.detect_alerts_for_player)."""

    __tablename__ = "player_watch_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)

    # None = segnalazione manuale (vedi is_manual). Non nullable solo per le
    # segnalazioni automatiche.
    trigger_type: Mapped[WatchAlertTriggerType | None] = mapped_column(
        Enum(WatchAlertTriggerType, name="watch_alert_trigger_type"), nullable=True
    )
    trigger_detail: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    # Distingue "non ancora visto" da "visto ma non scartato", per il badge
    # numerico sull'icona sidebar (vedi routes_watch_alerts.mark_seen).
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False)

    player: Mapped["Player"] = relationship()
