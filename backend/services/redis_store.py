import json
import logging
import os
import time

import redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client = None
_disabled_until = 0


def get_redis_client():
    global _client, _disabled_until

    if not REDIS_URL:
        return None
    if _disabled_until > time.time():
        return None
    if _client is not None:
        return _client

    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _client = client
        return _client
    except RedisError as exc:
        _disabled_until = time.time() + 30
        logger.warning("Redis unavailable: %s", exc)
        return None


def redis_set_json(key, value, ttl=None):
    client = get_redis_client()
    if client is None:
        return False
    payload = json.dumps(value, separators=(",", ":"))
    try:
        if ttl:
            client.set(key, payload, ex=int(ttl))
        else:
            client.set(key, payload)
        return True
    except RedisError as exc:
        logger.warning("Redis set failed for %s: %s", key, exc)
        return False


def redis_get_json(key):
    client = get_redis_client()
    if client is None:
        return None
    try:
        payload = client.get(key)
        if payload is None:
            return None
        return json.loads(payload)
    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning("Redis get failed for %s: %s", key, exc)
        return None


def redis_set_value(key, value, ttl=None):
    client = get_redis_client()
    if client is None:
        return False
    try:
        if ttl:
            client.set(key, value, ex=int(ttl))
        else:
            client.set(key, value)
        return True
    except RedisError as exc:
        logger.warning("Redis set failed for %s: %s", key, exc)
        return False


def redis_delete(*keys):
    client = get_redis_client()
    if client is None or not keys:
        return 0
    try:
        return client.delete(*keys)
    except RedisError as exc:
        logger.warning("Redis delete failed: %s", exc)
        return 0


def redis_exists(key):
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.exists(key))
    except RedisError as exc:
        logger.warning("Redis exists failed for %s: %s", key, exc)
        return False


def redis_ttl(key):
    client = get_redis_client()
    if client is None:
        return None
    try:
        ttl = client.ttl(key)
        return ttl if ttl and ttl > 0 else None
    except RedisError as exc:
        logger.warning("Redis ttl failed for %s: %s", key, exc)
        return None
