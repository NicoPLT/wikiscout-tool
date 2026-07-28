import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base_class import Base
from app.db import base as _base  # noqa: F401  registra tutti i modelli
from app.models.watchlist import Watchlist

# SQLite non supporta il tipo Postgres ARRAY usato da Watchlist.tags: per i
# test in memoria lo si sostituisce con JSON (stesso pattern gia' usato
# altrove in questo progetto per verificare a mano contro SQLite).
Watchlist.__table__.columns["tags"].type = JSON()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_con, con_record):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch):
    """Nessun Redis disponibile nei test: le funzioni di cache diventano
    no-op, come nelle verifiche manuali gia' usate in questo progetto."""
    import app.services.player_service as player_service

    monkeypatch.setattr(player_service, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(player_service, "cache_set", lambda *a, **k: None)
    monkeypatch.setattr(player_service, "invalidate_watchlist_cache", lambda *a, **k: None)
