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

    # Apify (usato per il valore di mercato Transfermarkt - non toccato)
    APIFY_TOKEN: str | None = None

    # API-Football: NON e' piu' una dipendenza primaria (ricerca/statistiche
    # ora vengono da Transfermarkt/Sofascore). Il modulo resta disponibile in
    # app/services/providers/api_football.py come fonte legacy/opzionale,
    # spenta di default: va accesa esplicitamente se in futuro serve per dati
    # che Transfermarkt/Sofascore non coprono bene (es. formazioni).
    ENABLE_API_FOOTBALL: bool = False
    API_FOOTBALL_KEY: str | None = None
    API_FOOTBALL_DAILY_LIMIT: int = 100

    # Scraping Sofascore (via Playwright): pausa minima tra una richiesta e
    # l'altra per non sovraccaricare il sito ed evitare blocchi IP.
    SOFASCORE_REQUEST_DELAY_SECONDS: float = 1.5

    # Client diretto verso l'API interna di Transfermarkt
    # (tmapi.transfermarkt.technology): stessa logica di pausa prudente,
    # anche se qui non c'e' un browser di mezzo.
    TRANSFERMARKT_PERFORMANCE_REQUEST_DELAY_SECONDS: float = 1.0

    # "One to Watch": soglie di rilevamento automatico (vedi
    # app/services/watch_alert_service.py). Configurabili via env senza
    # toccare il codice, per poterle affinare nel tempo.
    WATCH_ALERT_RATING_THRESHOLD: float = 7.5
    WATCH_ALERT_STREAK_MATCHES: int = 2
    WATCH_ALERT_RECENT_TRANSFER_DAYS: int = 30
    WATCH_ALERT_MARKET_VALUE_SPIKE_PCT: float = 20.0
    WATCH_ALERT_MARKET_VALUE_WINDOW_DAYS: int = 60

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
