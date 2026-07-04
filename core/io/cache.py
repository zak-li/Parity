from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be strictly positive.")
        if max_entries <= 0:
            raise ValueError("max_entries must be strictly positive.")
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._store: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            cached = self._store.get(key)
            if cached is not None and now - cached[0] < self._ttl:
                self._store.move_to_end(key)
                return cached[1]

        value = factory()

        with self._lock:
            self._store[key] = (self._clock(), value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
