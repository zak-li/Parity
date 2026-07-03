from __future__ import annotations

import pytest

from core.io.rate_limiter import TokenBucketRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_capacity_immediately():
    limiter = TokenBucketRateLimiter(rate_per_second=1.0, capacity=3, clock=FakeClock())
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()


def test_refills_over_time():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate_per_second=2.0, capacity=2, clock=clock)
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()

    clock.now = 1.0
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()


def test_does_not_exceed_capacity_when_idle():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(rate_per_second=5.0, capacity=2, clock=clock)
    clock.now = 100.0
    assert limiter.available_tokens == pytest.approx(2.0)


@pytest.mark.parametrize("rate,capacity", [(0, 5), (-1, 5), (5, 0), (5, -1)])
def test_rejects_invalid_construction(rate, capacity):
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(rate_per_second=rate, capacity=capacity)


def test_rejects_non_positive_token_request():
    limiter = TokenBucketRateLimiter(rate_per_second=1.0, capacity=1)
    with pytest.raises(ValueError):
        limiter.try_acquire(0)
