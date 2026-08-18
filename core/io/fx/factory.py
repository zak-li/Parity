from __future__ import annotations

import logging

from ...config import load_runtime_config
from ...config.settings import RuntimeConfig
from ..cache import TTLCache
from ..rate_limiter import TokenBucketRateLimiter
from .base import FxDataProvider
from .exchangerate_api import ExchangeRateApiFxDataProvider
from .fallback import FallbackFxDataProvider
from .frankfurter import FrankfurterFxDataProvider

logger = logging.getLogger(__name__)


def build_default_fx_provider(
    config: RuntimeConfig | None = None,
    cache: TTLCache | None = None,
    rate_limiter: TokenBucketRateLimiter | None = None,
) -> FxDataProvider:
    """Construct an FxDataProvider based on the configured providers chain.

    Uses `XI_FX_PROVIDERS` (e.g. ('frankfurter', 'exchangerate_api')) and wraps
    them in a `FallbackFxDataProvider` with per-provider circuit breakers.
    """
    cfg = config or load_runtime_config()
    providers: list[FxDataProvider] = []

    for name in cfg.fx_providers:
        provider_key = name.strip().lower()
        if provider_key == "frankfurter":
            providers.append(
                FrankfurterFxDataProvider(config=cfg, cache=cache, rate_limiter=rate_limiter)
            )
        elif provider_key == "exchangerate_api":
            providers.append(
                ExchangeRateApiFxDataProvider(config=cfg, cache=cache, rate_limiter=rate_limiter)
            )
        else:
            logger.warning("Unknown FX provider name %r in XI_FX_PROVIDERS; skipping.", name)

    if not providers:
        # Fall back to default Frankfurter if no valid providers configured
        providers.append(
            FrankfurterFxDataProvider(config=cfg, cache=cache, rate_limiter=rate_limiter)
        )

    if len(providers) == 1:
        return providers[0]

    return FallbackFxDataProvider(providers)
