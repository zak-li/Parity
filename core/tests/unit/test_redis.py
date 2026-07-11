import pickle
from unittest.mock import MagicMock

from core.io.redis_cache import RedisTTLCache
from core.io.redis_rate_limiter import RedisTokenBucketRateLimiter


def test_redis_ttl_cache():
    mock_redis = MagicMock()
    # Test cache miss
    mock_redis.get.return_value = None
    cache = RedisTTLCache(mock_redis, "prefix", 60)

    value = cache.get_or_set("key1", lambda: "value1")
    assert value == "value1"
    mock_redis.setex.assert_called_once()

    # Test cache hit
    mock_redis.get.return_value = pickle.dumps("value2")
    value2 = cache.get_or_set("key2", lambda: "value3")
    assert value2 == "value2"


def test_redis_rate_limiter():
    mock_redis = MagicMock()
    mock_script = MagicMock()
    mock_redis.register_script.return_value = mock_script

    limiter = RedisTokenBucketRateLimiter(mock_redis, "limit", 10.0, 10)

    # allow token consumption
    mock_script.return_value = 1
    allowed = limiter.try_acquire(1.0)
    assert allowed is True

    # deny token consumption
    mock_script.return_value = 0
    allowed2 = limiter.try_acquire(1.0)
    assert allowed2 is False
