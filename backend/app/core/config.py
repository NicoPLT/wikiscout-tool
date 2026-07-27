from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "WikiScout Tool API"
    ENV: str = "development"
    SECRET_KEY: str = "change-me-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Single-user auth
    AUTH_EMAIL: str = "scout@wikiscout.it"
    AUTH_PASSWORD_HASH: str | None = None

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://wikiscout:wikiscout@localhost:5432/wikiscout"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 60 * 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    NIGHTLY_JOB_HOUR: int = 3
    NIGHTLY_JOB_MINUTE: int = 0

    # External API keys (Fase B - opzionali, se assenti i job restano "spenti")
    API_FOOTBALL_KEY: str | None = None
    APIFY_TOKEN: str | None = None
    API_FOOTBALL_DAILY_LIMIT: int = 100

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
