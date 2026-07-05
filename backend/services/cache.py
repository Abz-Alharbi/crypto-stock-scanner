from collections import OrderedDict
import os
import time

from redis.exceptions import RedisError

from backend.services.redis_store import get_redis_client, redis_delete, redis_get_json, redis_set_json

CACHE_TTL = 300
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
CACHE_KEY_PREFIX = os.getenv("REDIS_CACHE_PREFIX", "api_cache:")
CACHE_LRU_KEY = f"{CACHE_KEY_PREFIX}lru"
_cache = OrderedDict()


def _redis_cache_key(key):
    return f"{CACHE_KEY_PREFIX}{key}"


def _evict_memory_cache():
    while len(_cache) > CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


def _evict_redis_cache(client):
    try:
        overflow = client.zcard(CACHE_LRU_KEY) - CACHE_MAX_ENTRIES
        if overflow <= 0:
            return
        stale_keys = client.zrange(CACHE_LRU_KEY, 0, overflow - 1)
        if stale_keys:
            client.delete(*stale_keys)
            client.zrem(CACHE_LRU_KEY, *stale_keys)
    except RedisError:
        return


def cache_get(key):
    redis_key = _redis_cache_key(key)
    client = get_redis_client()
    if client is not None:
        entry = redis_get_json(redis_key)
        if not entry:
            try:
                client.zrem(CACHE_LRU_KEY, redis_key)
            except RedisError:
                pass
            return None
        ttl = int(entry.get("ttl", CACHE_TTL))
        if time.time() - float(entry.get("time", 0)) >= ttl:
            redis_delete(redis_key)
            try:
                client.zrem(CACHE_LRU_KEY, redis_key)
            except RedisError:
                pass
            return None
        try:
            client.zadd(CACHE_LRU_KEY, {redis_key: time.time()})
        except RedisError:
            pass
        return entry.get("data")

    if key in _cache:
        entry = _cache.pop(key)
        ttl = int(entry.get("ttl", CACHE_TTL))
        if time.time() - float(entry.get("time", 0)) < ttl:
            _cache[key] = entry
            return entry.get("data")
    return None


def cache_set(key, data, ttl=None):
    entry = {"data": data, "time": time.time(), "ttl": int(ttl or CACHE_TTL)}
    redis_key = _redis_cache_key(key)
    client = get_redis_client()
    if client is not None:
        if redis_set_json(redis_key, entry, ttl=entry["ttl"]):
            try:
                client.zadd(CACHE_LRU_KEY, {redis_key: time.time()})
                _evict_redis_cache(client)
            except RedisError:
                pass
            return

    _cache[key] = entry
    _cache.move_to_end(key)
    _evict_memory_cache()


def cache_size():
    client = get_redis_client()
    if client is not None:
        try:
            return client.zcard(CACHE_LRU_KEY)
        except RedisError:
            pass
    return len(_cache)
