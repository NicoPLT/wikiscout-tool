import re

from pydantic import BaseModel, ConfigDict, field_validator

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class TagCreate(BaseModel):
    name: str
    color: str

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Il nome del tag non puo' essere vuoto")
        return v

    @field_validator("color")
    @classmethod
    def _color_is_hex(cls, v: str) -> str:
        if not HEX_COLOR_RE.match(v):
            raise ValueError("Il colore deve essere in formato esadecimale, es. #6bec68")
        return v


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Il nome del tag non puo' essere vuoto")
        return v

    @field_validator("color")
    @classmethod
    def _color_is_hex(cls, v: str | None) -> str | None:
        if v is not None and not HEX_COLOR_RE.match(v):
            raise ValueError("Il colore deve essere in formato esadecimale, es. #6bec68")
        return v


class PlayerTagAssignRequest(BaseModel):
    tag_id: int | None
