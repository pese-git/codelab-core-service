"""Redis client configuration."""

from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

# Global Redis client instance
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            str(settings.redis_url),
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


class RedisCache:
    """Redis cache helper."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> Any:
        """Get value from cache."""
        return await self.redis.get(key)

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> None:
        """Set value in cache with optional TTL."""
        if ttl:
            await self.redis.setex(key, ttl, value)
        else:
            await self.redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return bool(await self.redis.exists(key))

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL for key."""
        await self.redis.expire(key, ttl)

    async def hget(self, name: str, key: str) -> Any:
        """Get hash field value."""
        return await self.redis.hget(name, key)

    async def hset(
        self, name: str, key: str | None = None, value: Any = None, mapping: dict[str, Any] | None = None
    ) -> None:
        """Set hash field value."""
        if mapping:
            await self.redis.hset(name, mapping=mapping)
        elif key is not None:
            await self.redis.hset(name, key, value)

    async def hdel(self, name: str, *keys: str) -> None:
        """Delete hash fields."""
        await self.redis.hdel(name, *keys)

    async def hgetall(self, name: str) -> dict[str, Any]:
        """Get all hash fields."""
        return await self.redis.hgetall(name)

    async def lpush(self, key: str, *values: Any) -> None:
        """Push values to list (left)."""
        await self.redis.lpush(key, *values)

    async def rpush(self, key: str, *values: Any) -> None:
        """Push values to list (right)."""
        await self.redis.rpush(key, *values)

    async def lpop(self, key: str) -> Any:
        """Pop value from list (left)."""
        return await self.redis.lpop(key)

    async def rpop(self, key: str) -> Any:
        """Pop value from list (right)."""
        return await self.redis.rpop(key)

    async def lrange(self, key: str, start: int, end: int) -> list[Any]:
        """Get list range."""
        return await self.redis.lrange(key, start, end)

    async def llen(self, key: str) -> int:
        """Get list length."""
        return await self.redis.llen(key)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        """Trim list to range."""
        await self.redis.ltrim(key, start, end)
