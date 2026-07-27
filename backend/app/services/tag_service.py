"""Servizio per il sistema di tag colorati (evidenziazione riga dashboard).

Distinto dai `watchlist.tags` (etichette libere testuali gia' esistenti):
qui un Tag e' un'entita' con nome+colore, definita una volta e riutilizzata
su piu' giocatori; ogni riga in watchlist ne ha al massimo uno assegnato.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.models.watchlist import Watchlist
from app.services.player_service import invalidate_watchlist_cache


def list_tags(db: Session, user_id: int) -> list[Tag]:
    stmt = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    return list(db.execute(stmt).scalars().all())


def create_tag(db: Session, user_id: int, name: str, color: str) -> Tag | None:
    """None se un tag con lo stesso nome esiste gia' per questo utente."""
    tag = Tag(user_id=user_id, name=name, color=color)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(tag)
    return tag


def update_tag(db: Session, user_id: int, tag_id: int, name: str | None, color: str | None) -> Tag | None:
    tag = db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)).scalar_one_or_none()
    if tag is None:
        return None

    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(tag)
    invalidate_watchlist_cache(user_id)
    return tag


def delete_tag(db: Session, user_id: int, tag_id: int) -> bool:
    """Elimina il tag; i giocatori a cui era assegnato restano in watchlist,
    solo senza piu' quel tag (ON DELETE SET NULL)."""
    tag = db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)).scalar_one_or_none()
    if tag is None:
        return False

    db.delete(tag)
    db.commit()
    invalidate_watchlist_cache(user_id)
    return True


def assign_player_tag(db: Session, user_id: int, player_id: int, tag_id: int | None) -> Watchlist | None:
    """None se il giocatore non e' in watchlist, o se tag_id non e' None e
    non esiste (o appartiene a un altro utente)."""
    entry = db.execute(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.player_id == player_id)
    ).scalar_one_or_none()
    if entry is None:
        return None

    if tag_id is not None:
        tag = db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)).scalar_one_or_none()
        if tag is None:
            return None

    entry.tag_id = tag_id
    db.commit()
    db.refresh(entry)
    invalidate_watchlist_cache(user_id)
    return entry
