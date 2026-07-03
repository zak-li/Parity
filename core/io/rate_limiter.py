from __future__ import annotations

import threading
import time
from typing import Callable


class TokenBucketRateLimiter:
    def __init__(
        self,
        rate_per_second: float,
        capacity: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second doit être strictement positif.")
        if capacity <= 0:
            raise ValueError("capacity doit être strictement positif.")
        self._rate = rate_per_second
        self._capacity = float(capacity)
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()
        self._lock = threading.Lock()

    def try_acquire(self, tokens: float = 1.0) -> bool:
        if tokens <= 0:
            raise ValueError("tokens doit être strictement positif.")
        with self._lock:
            now = self._clock()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        with self._lock:
            now = self._clock()
            return min(self._capacity, self._tokens + (now - self._last) * self._rate)
