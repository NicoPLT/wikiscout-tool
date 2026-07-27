import json
from typing import Any

from app.core.config import get_settings
from app.db.redis_client import redis_client

settings = get_settings()


def cache_get(key: str) -> Any | None:
    raw = redis_client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds or settings.CACHE_TTL_SECONDS)


def cache_delete_prefix(prefix: str) -> None:
    for key in redis_client.scan_iter(f"{prefix}*"):
        redis_client.delete(key)
