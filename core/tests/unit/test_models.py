from __future__ import annotations

import datetime as dt

import pytest

from core.models.exceptions import InvalidOrderError
from core.models.models import OrderInput


def _base_kwargs(**overrides):
    kwargs = {
        "amount_foreign": 100_000.0,
        "foreign_currency": "USD",
        "domestic_currency": "MAD",
        "order_date": dt.date(2026, 1, 1),
        "delivery_date": dt.date(2026, 3, 1),
        "target_margin_pct": 0.30,
    }
    kwargs.update(overrides)
    return kwargs


def test_valid_order_normalizes_currency_codes():
    order = OrderInput(**_base_kwargs(foreign_currency="usd", domestic_currency="mad"))
    assert order.foreign_currency == "USD"
    assert order.domestic_currency == "MAD"


def test_horizon_days_computed_correctly():
    order = OrderInput(**_base_kwargs())
    assert order.horizon_days == (dt.date(2026, 3, 1) - dt.date(2026, 1, 1)).days


def test_order_is_immutable():
    order = OrderInput(**_base_kwargs())
    with pytest.raises(Exception):
        order.amount_foreign = 5.0  # type: ignore[misc]


def test_expected_revenue_takes_priority_over_target_margin():
    order = OrderInput(**_base_kwargs(target_margin_pct=0.5, expected_revenue_domestic=1_200_000.0))
    assert order.expected_revenue_domestic == 1_200_000.0


def test_rejects_identical_currencies():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(foreign_currency="MAD", domestic_currency="MAD"))


def test_rejects_non_positive_amount():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(amount_foreign=0))


def test_rejects_non_finite_amount():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(amount_foreign=float("inf")))


def test_rejects_delivery_before_order():
    with pytest.raises(InvalidOrderError):
        OrderInput(
            **_base_kwargs(order_date=dt.date(2026, 3, 1), delivery_date=dt.date(2026, 1, 1))
        )


def test_rejects_horizon_exceeding_maximum():
    with pytest.raises(InvalidOrderError):
        OrderInput(
            **_base_kwargs(order_date=dt.date(2020, 1, 1), delivery_date=dt.date(2030, 1, 1))
        )


def test_rejects_missing_revenue_and_margin():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(target_margin_pct=None))


def test_rejects_margin_below_negative_one():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(target_margin_pct=-1.5))


def test_rejects_n_simulations_out_of_bounds():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(n_simulations=10))


def test_rejects_lookback_out_of_bounds():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(lookback_days=1))


def test_rejects_invalid_currency_format():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(foreign_currency="US"))


def test_rejects_non_date_objects():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(order_date="2026-01-01"))


def test_rejects_non_positive_expected_revenue():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(target_margin_pct=None, expected_revenue_domestic=-1.0))


def test_rejects_non_finite_min_acceptable_margin_pct():
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(min_acceptable_margin_pct=float("nan")))


def test_accepts_valid_interest_rates():
    order = OrderInput(**_base_kwargs(domestic_rate=0.03, foreign_rate=0.05))
    assert order.domestic_rate == pytest.approx(0.03)
    assert order.foreign_rate == pytest.approx(0.05)


def test_interest_rates_default_to_zero():
    order = OrderInput(**_base_kwargs())
    assert order.domestic_rate == 0.0
    assert order.foreign_rate == 0.0


@pytest.mark.parametrize("field", ["domestic_rate", "foreign_rate"])
def test_rejects_out_of_range_interest_rate(field):
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(**{field: 5.0}))


@pytest.mark.parametrize("field", ["domestic_rate", "foreign_rate"])
def test_rejects_non_finite_interest_rate(field):
    with pytest.raises(InvalidOrderError):
        OrderInput(**_base_kwargs(**{field: float("inf")}))
