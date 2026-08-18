from __future__ import annotations

from core.config import RuntimeConfig
from core.io.fx.exchangerate_api import ExchangeRateApiFxDataProvider
from core.io.fx.factory import build_default_fx_provider
from core.io.fx.fallback import FallbackFxDataProvider
from core.io.fx.frankfurter import FrankfurterFxDataProvider


def test_build_default_fx_provider_single():
    cfg = RuntimeConfig(fx_providers=("frankfurter",))
    provider = build_default_fx_provider(cfg)
    assert isinstance(provider, FrankfurterFxDataProvider)


def test_build_default_fx_provider_fallback():
    cfg = RuntimeConfig(fx_providers=("frankfurter", "exchangerate_api"))
    provider = build_default_fx_provider(cfg)
    assert isinstance(provider, FallbackFxDataProvider)


def test_build_default_fx_provider_unknown_skips():
    cfg = RuntimeConfig(fx_providers=("unknown_provider", "exchangerate_api"))
    provider = build_default_fx_provider(cfg)
    assert isinstance(provider, ExchangeRateApiFxDataProvider)
