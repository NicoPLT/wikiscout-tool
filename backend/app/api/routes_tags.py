from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import PlayerTagAssignRequest, TagCreate, TagOut, TagUpdate
from app.services import tag_service

router = APIRouter(prefix="/api", tags=["tags"])


@router.get("/tags", response_model=list[TagOut])
def get_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TagOut]:
    return [TagOut.model_validate(t) for t in tag_service.list_tags(db, current_user.id)]


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagOut:
    tag = tag_service.create_tag(db, current_user.id, payload.name, payload.color)
    if tag is None:
        raise HTTPException(status_code=409, detail="Esiste gia' un tag con questo nome")
    return TagOut.model_validate(tag)


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagOut:
    tag = tag_service.update_tag(db, current_user.id, tag_id, payload.name, payload.color)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag non trovato, o nome gia' in uso")
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    removed = tag_service.delete_tag(db, current_user.id, tag_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Tag non trovato")


@router.patch("/players/{player_id}/tag", status_code=status.HTTP_204_NO_CONTENT)
def assign_player_tag(
    player_id: int,
    payload: PlayerTagAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    entry = tag_service.assign_player_tag(db, current_user.id, player_id, payload.tag_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Giocatore non in watchlist, o tag non trovato",
        )
