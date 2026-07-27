"""Contatore giornaliero delle chiamate ad API esterne, salvato su Redis.

Ogni scraper deve chiamare `register_call(source)` prima di una richiesta e
`is_near_limit(source, daily_limit)` per decidere se fermarsi con un warning
invece di continuare a consumare la quota gratuita.

Il conteggio e' solo un aiuto per non sforare le quote: se Redis non e'
raggiungibile (es. in locale senza docker-compose up) le funzioni non
sollevano eccezioni, cosi' uno scraper non si rompe per un problema non
legato alla fonte dati che sta interrogando.
"""

import logging
from datetime import datetime, timezone

import redis as redis_lib

from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)

_KEY_PREFIX = "api_calls:"


def _today_key(source: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{_KEY_PREFIX}{source}:{day}"


def register_call(source: str) -> int:
    key = _today_key(source)
    try:
        count = redis_client.incr(key)
        redis_client.expire(key, 60 * 60 * 26)  # scade poco dopo la fine della giornata UTC
        return count
    except redis_lib.RedisError:
        logger.warning("Redis non raggiungibile: salto il conteggio chiamate per '%s'", source)
        return 0


def get_call_count(source: str) -> int:
    try:
        raw = redis_client.get(_today_key(source))
        return int(raw) if raw else 0
    except redis_lib.RedisError:
        return 0


def is_near_limit(source: str, daily_limit: int, threshold: float = 0.9) -> bool:
    return get_call_count(source) >= daily_limit * threshold
