from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

from core.config import RuntimeConfig
from core.io.fx.exchangerate_api import ExchangeRateApiFxDataProvider
from core.models.exceptions import FxDataError, InvalidOrderError


def test_exchangerate_api_parse_response():
    provider = ExchangeRateApiFxDataProvider()
    payload = {
        "result": "success",
        "rates": {"USD": 1.0, "EUR": 0.85},
    }
    start = dt.date(2026, 10, 1)
    end = dt.date(2026, 10, 5)
    series = provider._parse_response(payload, "USD", "EUR", start, end)

    assert isinstance(series, pd.Series)
    assert len(series) == 5
    assert (series == 0.85).all()


def test_exchangerate_api_raises_on_invalid_dates():
    provider = ExchangeRateApiFxDataProvider()
    start = dt.date(2026, 10, 5)
    end = dt.date(2026, 10, 1)
    with pytest.raises(InvalidOrderError):
        provider.get_historical_series("USD", "EUR", start, end)


def test_exchangerate_api_raises_on_error_result():
    provider = ExchangeRateApiFxDataProvider()
    payload = {"result": "error", "error-type": "invalid-key"}
    start = dt.date(2026, 10, 1)
    end = dt.date(2026, 10, 2)
    with pytest.raises(FxDataError, match="ExchangeRate-API error"):
        provider._parse_response(payload, "USD", "EUR", start, end)


def test_exchangerate_api_with_mock_session():
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.iter_content.return_value = [
        b'{"result": "success", "conversion_rates": {"EUR": 0.92}}'
    ]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.get.return_value.__enter__.return_value = mock_response

    config = RuntimeConfig(allowed_fx_hosts=frozenset({"open.er-api.com"}))
    provider = ExchangeRateApiFxDataProvider(session=mock_session, config=config)

    start = dt.date(2026, 10, 1)
    end = dt.date(2026, 10, 3)
    series = provider.get_historical_series("USD", "EUR", start, end)

    assert isinstance(series, pd.Series)
    assert series.iloc[0] == 0.92
