from unittest.mock import MagicMock, patch

from core.connectors.odoo import OdooConnector
from core.connectors.shopify import ShopifyConnector
from core.connectors.stripe import StripeConnector
from core.connectors.woocommerce import WooCommerceConnector


class TestConnectors:
    def test_shopify_success(self):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "orders": [
                    {
                        "id": 123,
                        "currency": "EUR",
                        "current_total_price": "100.50",
                        "created_at": "2026-01-01T10:00:00+00:00",
                        "financial_status": "paid",
                    }
                ]
            }
            mock_get.return_value = mock_resp

            conn = ShopifyConnector("test_shop", "token")
            sales = conn.fetch_sales()
            assert len(sales) == 1
            assert sales[0].currency == "EUR"
            assert sales[0].amount == 100.50

            est = conn.estimate_annual_revenue()
            assert "EUR" in est
            assert est["EUR"] > 1000

    def test_woocommerce_success(self):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = [
                {
                    "id": 456,
                    "currency": "USD",
                    "total": "50.00",
                    "date_created_gmt": "2026-01-01T10:00:00",
                    "status": "completed",
                }
            ]
            mock_get.return_value = mock_resp

            conn = WooCommerceConnector("http://test.com", "key", "secret")
            sales = conn.fetch_sales()
            assert len(sales) == 1
            assert sales[0].currency == "USD"
            assert sales[0].amount == 50.00

            est = conn.estimate_annual_revenue()
            assert "USD" in est

    def test_stripe_success(self):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [
                    {
                        "id": "ch_123",
                        "currency": "gbp",
                        "amount": 1500,
                        "created": 1672531200,
                        "status": "succeeded",
                    }
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            conn = StripeConnector("sk_test_123")
            sales = conn.fetch_sales()
            assert len(sales) == 1
            assert sales[0].currency == "GBP"
            assert sales[0].amount == 15.00

            est = conn.estimate_annual_revenue()
            assert "GBP" in est

    def test_odoo_success(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_server = MagicMock()
            mock_server.authenticate.return_value = 1
            mock_server.execute_kw.return_value = [
                {
                    "id": 1,
                    "name": "PO001",
                    "currency_id": [2, "USD"],
                    "amount_total": 5000.0,
                    "date_order": "2026-01-01 10:00:00",
                    "state": "purchase",
                }
            ]
            mock_proxy.return_value = mock_server

            conn = OdooConnector("http://odoo.test", "db", "user", "pass")
            purchases = conn.fetch_purchases()
            assert len(purchases) == 1
            assert purchases[0].currency == "USD"
            assert purchases[0].amount == 5000.0
