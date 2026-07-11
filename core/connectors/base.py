from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SalesRecord:
    id: str
    currency: str
    amount: float
    created_at: dt.datetime
    status: str


@dataclass(frozen=True, slots=True)
class PurchaseRecord:
    id: str
    currency: str
    amount: float
    created_at: dt.datetime
    expected_delivery_date: dt.date | None
    status: str


class ConnectorError(Exception):
    pass


class SalesConnector(Protocol):
    def fetch_sales(self, days_lookback: int = 30) -> list[SalesRecord]:
        """Fetch sales records from the e-commerce/payment platform."""
        ...

    def estimate_annual_revenue(self) -> dict[str, float]:
        """Estimate annual revenue per currency based on historical sales."""
        ...


class PurchaseConnector(Protocol):
    def fetch_purchases(self, days_lookback: int = 90) -> list[PurchaseRecord]:
        """Fetch purchase orders from the ERP/accounting platform."""
        ...
