from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def ensure_single_user_exists(db: Session) -> None:
    """Crea l'unico account scout da env var se non esiste ancora (bootstrap)."""
    existing = db.execute(select(User).where(User.email == settings.AUTH_EMAIL)).scalar_one_or_none()
    if existing is not None:
        return

    if not settings.AUTH_PASSWORD_HASH:
        return

    user = User(email=settings.AUTH_EMAIL, hashed_password=settings.AUTH_PASSWORD_HASH)
    db.add(user)
    db.commit()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    ensure_single_user_exists(db)

    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o password errati")

    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(email=current_user.email)
