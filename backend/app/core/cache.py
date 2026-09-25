from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger("commerceflow.cache")
settings = get_settings()


class _InMemoryFallbackCache:
    """Used automatically if Redis is unreachable, so the app still runs
    (single-process only -- not shared across replicas, unlike real Redis).
    """

    def __init__(self):
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._store[key] = (time.monotonic() + ttl, value)

    async def delete_prefix(self, prefix: str) -> None:
        for k in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(k, None)


class Cache:
    """Thin JSON cache wrapper. Tries Redis first; falls back to in-memory
    so local dev / CI never hard-fails just because Redis isn't running.
    """

    def __init__(self):
        self._redis = None
        self._fallback = _InMemoryFallbackCache()
        self._tried_connect = False

    async def _get_client(self):
        if self._redis is not None:
            return self._redis
        if self._tried_connect:
            return None
        self._tried_connect = True
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            await client.ping()
            self._redis = client
            logger.info("Connected to Redis at %s", settings.redis_url)
            return client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable (%s) -- using in-memory cache fallback", exc)
            return None

    async def get_json(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(key) if client else await self._fallback.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl if ttl is not None else settings.cache_ttl_seconds
        raw = json.dumps(value)
        client = await self._get_client()
        if client:
            await client.set(key, raw, ex=ttl)
        else:
            await self._fallback.set(key, raw, ttl)

    async def invalidate_prefix(self, prefix: str) -> None:
        client = await self._get_client()
        if client:
            async for key in client.scan_iter(match=f"{prefix}*"):
                await client.delete(key)
        else:
            await self._fallback.delete_prefix(prefix)


_cache_singleton: Cache | None = None


def get_cache() -> Cache:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = Cache()
    return _cache_singleton
