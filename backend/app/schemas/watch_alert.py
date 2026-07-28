from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchAlertPlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    photo_url: str | None
    current_team: str | None
    league: str | None


class WatchAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: int
    player: WatchAlertPlayerOut
    # None = segnalazione manuale (vedi is_manual).
    trigger_type: str | None
    trigger_detail: str
    detected_at: datetime
    is_dismissed: bool
    is_manual: bool
    is_seen: bool


class ManualWatchAlertCreate(BaseModel):
    player_id: int
    note: str = Field(min_length=1, max_length=1000)

    @property
    def clean_note(self) -> str:
        return self.note.strip()


class WatchAlertUnseenCount(BaseModel):
    count: int
