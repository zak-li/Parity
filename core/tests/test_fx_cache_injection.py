"""Regression tests: an injected cache / rate limiter must be used even when it
is "falsy" (e.g. a Redis-backed one whose __len__ is 0)."""

from __future__ import annotations

from core.io.fx.frankfurter import FrankfurterFxDataProvider


class _FalsyCache:
    def __len__(self) -> int:  # makes the instance falsy
        return 0

    def get_or_set(self, key, factory):
        return factory()


class _FalsyRateLimiter:
    def __len__(self) -> int:
        return 0

    def try_acquire(self) -> bool:
        return True


def test_injected_cache_retained_even_if_falsy():
    cache = _FalsyCache()
    provider = FrankfurterFxDataProvider(cache=cache)  # type: ignore[arg-type]
    assert provider._cache is cache


def test_injected_rate_limiter_retained_even_if_falsy():
    limiter = _FalsyRateLimiter()
    provider = FrankfurterFxDataProvider(rate_limiter=limiter)  # type: ignore[arg-type]
    assert provider._rate_limiter is limiter
