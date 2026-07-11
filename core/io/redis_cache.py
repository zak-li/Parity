from __future__ import annotations

import pickle
from collections.abc import Callable, Hashable
from typing import Any

try:
    from redis import Redis
except ImportError:
    Redis = None  # type: ignore


class RedisTTLCache:
    def __init__(
        self,
        redis_client: Redis,
        key_prefix: str,
        ttl_seconds: float,
    ) -> None:
        if redis_client is None:
            raise RuntimeError("redis package is not installed")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be strictly positive.")

        self._redis = redis_client
        self._prefix = key_prefix
        self._ttl = int(ttl_seconds)

    def _make_key(self, key: Hashable) -> str:
        # Create a stable string representation for the key
        key_str = ":".join(str(k) for k in key) if isinstance(key, tuple) else str(key)
        return f"{self._prefix}:{key_str}"

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        r_key = self._make_key(key)
        cached = self._redis.get(r_key)
        if cached is not None:
            # Type casting to appease mypy since redis might return Awaitable
            from typing import cast

            return pickle.loads(cast(bytes, cached))

        value = factory()

        # Cache the value
        serialized = pickle.dumps(value)
        self._redis.setex(r_key, self._ttl, serialized)

        return value

    def clear(self) -> None:
        # Not easily implementable in Redis without KEYS (which is bad for performance)
        # We could use a Redis set to track keys, but TTL handles eviction anyway.
        pass

    def __len__(self) -> int:
        return 0
