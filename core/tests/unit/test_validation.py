from __future__ import annotations

import pytest

from core.models.exceptions import InvalidOrderError
from core.models.validation import normalize_currency_code, validate_currency_code


def test_normalizes_lowercase_and_whitespace():
    assert normalize_currency_code(" usd ") == "USD"


def test_accepts_valid_iso_code():
    assert normalize_currency_code("MAD") == "MAD"


@pytest.mark.parametrize("bad_code", ["US", "USDD", "12A", "", "US1", None, 123])
def test_normalize_rejects_invalid_codes_with_value_error(bad_code):
    with pytest.raises(ValueError):
        normalize_currency_code(bad_code)


def test_domain_wrapper_maps_to_invalid_order_error():
    with pytest.raises(InvalidOrderError):
        validate_currency_code("US")


def test_domain_wrapper_returns_normalized_code():
    assert validate_currency_code(" eur ") == "EUR"
