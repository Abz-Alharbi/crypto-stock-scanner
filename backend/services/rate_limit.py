import logging
import time

from redis.exceptions import RedisError

from backend.services.redis_store import get_redis_client


logger = logging.getLogger(__name__)


def wait_for_rate_limit(name, limit, window_seconds):
    """Use a Redis fixed-window counter to coordinate limits across workers."""
    client = get_redis_client()
    if client is None:
        logger.warning("Redis unavailable; skipping distributed rate limit for %s", name)
        return

    key = f"rate_limit:{name}:{int(time.time() // window_seconds)}"
    while True:
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, int(window_seconds))
            if count <= limit:
                return

            wait_seconds = client.ttl(key)
            if wait_seconds is None or wait_seconds < 1:
                wait_seconds = int(window_seconds)
            logger.info(
                "rate_limit_wait",
                extra={"name": name, "wait_seconds": wait_seconds, "window_seconds": window_seconds},
            )
            time.sleep(wait_seconds)
        except RedisError as exc:
            logger.warning("Redis rate limit failed for %s: %s", name, exc)
            return
