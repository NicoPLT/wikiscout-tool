import json
import logging
from typing import Any

import redis as redis_lib

from app.core.config import get_settings
from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


def cache_get(key: str) -> Any | None:
    """None sia per cache-miss che per Redis irraggiungibile: la cache e'
    solo un'ottimizzazione, un blip di Redis non deve mai far fallire una
    lettura che altrimenti funzionerebbe leggendo direttamente dal DB."""
    try:
        raw = redis_client.get(key)
    except redis_lib.RedisError:
        logger.warning("Redis non raggiungibile: cache_get('%s') ignorata", key)
        return None
    if raw is None:
        return None
    return json.loads(raw)


def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    try:
        redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds or settings.CACHE_TTL_SECONDS)
    except redis_lib.RedisError:
        logger.warning("Redis non raggiungibile: cache_set('%s') ignorata", key)


def cache_delete_prefix(prefix: str) -> None:
    try:
        for key in redis_client.scan_iter(f"{prefix}*"):
            redis_client.delete(key)
    except redis_lib.RedisError:
        logger.warning("Redis non raggiungibile: cache_delete_prefix('%s') ignorata", prefix)
