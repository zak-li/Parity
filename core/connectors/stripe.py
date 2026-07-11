import datetime as dt

import requests

from .base import ConnectorError, SalesConnector, SalesRecord


class StripeConnector(SalesConnector):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.stripe.com/v1"

    def fetch_sales(self, days_lookback: int = 30) -> list[SalesRecord]:
        start_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_lookback)
        start_timestamp = int(start_date.timestamp())

        url = f"{self.base_url}/charges"
        headers = {"Authorization": f"Bearer {self.api_key}", "Stripe-Version": "2023-10-16"}
        params = {"created[gte]": start_timestamp, "limit": 100}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            records = []
            for charge in data.get("data", []):
                # Stripe amounts are in cents/smallest currency unit
                # We do a basic division by 100 for standard currencies.
                amount = float(charge["amount"]) / 100.0

                records.append(
                    SalesRecord(
                        id=charge["id"],
                        currency=charge["currency"].upper(),
                        amount=amount,
                        created_at=dt.datetime.fromtimestamp(charge["created"], dt.UTC),
                        status=charge["status"],
                    )
                )
            return records

        except requests.RequestException as exc:
            raise ConnectorError(f"Stripe API error: {exc}") from exc

    def estimate_annual_revenue(self) -> dict[str, float]:
        sales = self.fetch_sales(30)
        revenue_by_currency: dict[str, float] = {}
        for sale in sales:
            if sale.status == "succeeded":
                revenue_by_currency[sale.currency] = (
                    revenue_by_currency.get(sale.currency, 0.0) + sale.amount
                )
        return {k: v * 12.16 for k, v in revenue_by_currency.items()}
