import redis

from app.core.config import get_settings

settings = get_settings()

redis_client = (
    redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
    if settings.REDIS_URL else None
)
