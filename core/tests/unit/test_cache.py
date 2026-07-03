from __future__ import annotations

import pytest

from core.io.cache import TTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_returns_cached_value_within_ttl():
    cache = TTLCache(ttl_seconds=100, max_entries=10)
    calls = []

    def factory():
        calls.append(1)
        return "value"

    assert cache.get_or_set("k", factory) == "value"
    assert cache.get_or_set("k", factory) == "value"
    assert len(calls) == 1


def test_recomputes_after_ttl_expiry():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=10, max_entries=10, clock=clock)
    calls = []

    def factory():
        calls.append(1)
        return len(calls)

    cache.get_or_set("k", factory)
    clock.now = 20.0
    result = cache.get_or_set("k", factory)

    assert result == 2
    assert len(calls) == 2


def test_evicts_least_recently_used_entry_when_full():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=1000, max_entries=2, clock=clock)
    cache.get_or_set("a", lambda: "a")
    clock.now = 1.0
    cache.get_or_set("b", lambda: "b")
    clock.now = 2.0
    cache.get_or_set("a", lambda: "should-not-run")
    clock.now = 3.0
    cache.get_or_set("c", lambda: "c")

    assert len(cache) == 2
    recomputed = []
    cache.get_or_set("b", lambda: recomputed.append(1) or "b2")
    assert recomputed == [1]


def test_clear_empties_the_store():
    cache = TTLCache(ttl_seconds=100, max_entries=10)
    cache.get_or_set("k", lambda: "value")
    assert len(cache) == 1

    cache.clear()

    assert len(cache) == 0


@pytest.mark.parametrize("ttl,max_entries", [(0, 10), (-1, 10), (10, 0), (10, -1)])
def test_rejects_invalid_construction_params(ttl, max_entries):
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=ttl, max_entries=max_entries)
