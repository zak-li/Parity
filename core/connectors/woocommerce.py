import datetime as dt

import requests

from .base import ConnectorError, SalesConnector, SalesRecord


class WooCommerceConnector(SalesConnector):
    def __init__(self, store_url: str, consumer_key: str, consumer_secret: str):
        self.store_url = store_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = f"{self.store_url}/wp-json/wc/v3"

    def fetch_sales(self, days_lookback: int = 30) -> list[SalesRecord]:
        start_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_lookback)
        url = f"{self.base_url}/orders"

        params: dict[str, str | int] = {
            "after": start_date.isoformat(),
            "per_page": 100,
            "status": "completed,processing",
        }

        try:
            response = requests.get(
                url, auth=(self.consumer_key, self.consumer_secret), params=params, timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            records = []
            for order in data:
                records.append(
                    SalesRecord(
                        id=str(order["id"]),
                        currency=order["currency"],
                        amount=float(order["total"]),
                        created_at=dt.datetime.fromisoformat(order["date_created_gmt"] + "+00:00"),
                        status=order["status"],
                    )
                )
            return records

        except requests.RequestException as exc:
            raise ConnectorError(f"WooCommerce API error: {exc}") from exc

    def estimate_annual_revenue(self) -> dict[str, float]:
        sales = self.fetch_sales(30)
        revenue_by_currency: dict[str, float] = {}
        for sale in sales:
            revenue_by_currency[sale.currency] = (
                revenue_by_currency.get(sale.currency, 0.0) + sale.amount
            )
        return {k: v * 12.16 for k, v in revenue_by_currency.items()}
