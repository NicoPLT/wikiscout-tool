"""Contatore giornaliero delle chiamate ad API esterne, salvato su Redis.

Ogni scraper deve chiamare `register_call(source)` prima di una richiesta e
`is_near_limit(source, daily_limit)` per decidere se fermarsi con un warning
invece di continuare a consumare la quota gratuita.
"""

from datetime import datetime, timezone

from app.db.redis_client import redis_client

_KEY_PREFIX = "api_calls:"


def _today_key(source: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{_KEY_PREFIX}{source}:{day}"


def register_call(source: str) -> int:
    key = _today_key(source)
    count = redis_client.incr(key)
    redis_client.expire(key, 60 * 60 * 26)  # scade poco dopo la fine della giornata UTC
    return count


def get_call_count(source: str) -> int:
    raw = redis_client.get(_today_key(source))
    return int(raw) if raw else 0


def is_near_limit(source: str, daily_limit: int, threshold: float = 0.9) -> bool:
    return get_call_count(source) >= daily_limit * threshold
