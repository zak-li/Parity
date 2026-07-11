from __future__ import annotations

import time

try:
    from redis import Redis
except ImportError:
    Redis = None  # type: ignore

LUA_SCRIPT = """
local tokens_key = KEYS[1]
local timestamp_key = KEYS[2]

local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local fill_time = capacity / rate
local ttl = math.floor(fill_time * 2)
if ttl < 10 then
    ttl = 10
end

local last_tokens = tonumber(redis.call("get", tokens_key))
if last_tokens == nil then
    last_tokens = capacity
end

local last_refreshed = tonumber(redis.call("get", timestamp_key))
if last_refreshed == nil then
    last_refreshed = 0
end

local delta = math.max(0, now - last_refreshed)
local filled_tokens = math.min(capacity, last_tokens + (delta * rate))
local allowed = filled_tokens >= requested
local new_tokens = filled_tokens

if allowed then
    new_tokens = filled_tokens - requested
end

redis.call("setex", tokens_key, ttl, new_tokens)
redis.call("setex", timestamp_key, ttl, now)

return allowed and 1 or 0
"""


class RedisTokenBucketRateLimiter:
    def __init__(
        self,
        redis_client: Redis,
        key_prefix: str,
        rate_per_second: float,
        capacity: int,
    ) -> None:
        if redis_client is None:
            raise RuntimeError("redis package is not installed")
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be strictly positive.")
        if capacity <= 0:
            raise ValueError("capacity must be strictly positive.")

        self._redis = redis_client
        self._prefix = key_prefix
        self._rate = rate_per_second
        self._capacity = float(capacity)
        self._script = self._redis.register_script(LUA_SCRIPT)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        if tokens <= 0:
            raise ValueError("tokens must be strictly positive.")

        now = time.time()
        res = self._script(
            keys=[f"{self._prefix}:tokens", f"{self._prefix}:ts"],
            args=[float(self._rate), float(self._capacity), float(now), float(tokens)],
        )
        return bool(res)

    @property
    def available_tokens(self) -> float:
        now = time.time()
        tokens_val = self._redis.get(f"{self._prefix}:tokens")
        ts_val = self._redis.get(f"{self._prefix}:ts")

        from typing import cast

        last_tokens = float(cast(bytes, tokens_val)) if tokens_val is not None else self._capacity
        last_ts = float(cast(bytes, ts_val)) if ts_val is not None else 0.0

        delta = max(0.0, now - last_ts)
        return min(self._capacity, last_tokens + (delta * self._rate))
