import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_players import router as players_router
from app.api.routes_tags import router as tags_router
from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db import base  # noqa: F401  # registra tutti i modelli per SQLAlchemy (relationship string lookups)

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(players_router)
app.include_router(tags_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
