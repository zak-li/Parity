import datetime as dt

import requests

from .base import ConnectorError, SalesConnector, SalesRecord


class ShopifyConnector(SalesConnector):
    def __init__(self, shop_name: str, access_token: str):
        self.shop_name = shop_name
        self.access_token = access_token
        self.base_url = f"https://{self.shop_name}.myshopify.com/admin/api/2024-01"

    def fetch_sales(self, days_lookback: int = 30) -> list[SalesRecord]:
        start_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_lookback)
        url = f"{self.base_url}/orders.json"

        headers = {"X-Shopify-Access-Token": self.access_token, "Content-Type": "application/json"}

        params: dict[str, str | int] = {
            "status": "any",
            "created_at_min": start_date.isoformat(),
            "limit": 250,
            "fields": "id,currency,current_total_price,created_at,financial_status",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            records = []
            for order in data.get("orders", []):
                records.append(
                    SalesRecord(
                        id=str(order["id"]),
                        currency=order["currency"],
                        amount=float(order["current_total_price"]),
                        created_at=dt.datetime.fromisoformat(order["created_at"]),
                        status=order["financial_status"] or "unknown",
                    )
                )
            return records

        except requests.RequestException as exc:
            raise ConnectorError(f"Shopify API error: {exc}") from exc

    def estimate_annual_revenue(self) -> dict[str, float]:
        """Estimate annual revenue based on the last 30 days of sales."""
        sales = self.fetch_sales(30)
        revenue_by_currency: dict[str, float] = {}
        for sale in sales:
            if sale.status in ("paid", "partially_refunded"):
                revenue_by_currency[sale.currency] = (
                    revenue_by_currency.get(sale.currency, 0.0) + sale.amount
                )

        # Annualize the 30-day run rate
        return {k: v * 12.16 for k, v in revenue_by_currency.items()}
