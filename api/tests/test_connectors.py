from unittest.mock import patch

from fastapi.testclient import TestClient

from api.dependencies import require_api_key
from api.main import app

app.dependency_overrides[require_api_key] = lambda: None
client = TestClient(app)


@patch("core.connectors.shopify.ShopifyConnector.fetch_sales")
@patch("core.connectors.shopify.ShopifyConnector.estimate_annual_revenue")
def test_import_shopify(mock_estimate, mock_fetch):
    mock_fetch.return_value = ["mock_record_1", "mock_record_2"]
    mock_estimate.return_value = {"MAD": 100000.0}

    response = client.post(
        "/connectors/shopify/import",
        json={"shop_name": "test_shop", "access_token": "fake_token"},
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "shopify"
    assert data["record_count"] == 2
    assert data["annual_revenue_estimate"]["MAD"] == 100000.0


@patch("core.connectors.odoo.OdooConnector.fetch_purchases")
@patch("core.connectors.odoo.OdooConnector._authenticate")
def test_import_odoo(mock_auth, mock_fetch):
    class MockPurchase:
        currency = "EUR"
        amount = 1500.0

    mock_fetch.return_value = [MockPurchase(), MockPurchase()]

    response = client.post(
        "/connectors/odoo/import",
        json={"url": "http://test", "db": "test", "username": "user", "password": "pwd"},
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "odoo"
    assert data["record_count"] == 2
    assert data["currency_totals"]["EUR"] == 3000.0


@patch("core.connectors.woocommerce.WooCommerceConnector.fetch_sales")
@patch("core.connectors.woocommerce.WooCommerceConnector.estimate_annual_revenue")
def test_import_woocommerce(mock_estimate, mock_fetch):
    mock_fetch.return_value = ["mock_record_1"]
    mock_estimate.return_value = {"USD": 50000.0}

    response = client.post(
        "/connectors/woocommerce/import",
        json={"store_url": "http://test", "consumer_key": "ck", "consumer_secret": "cs"},
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "woocommerce"
    assert data["annual_revenue_estimate"]["USD"] == 50000.0


@patch("core.connectors.stripe.StripeConnector.fetch_sales")
@patch("core.connectors.stripe.StripeConnector.estimate_annual_revenue")
def test_import_stripe(mock_estimate, mock_fetch):
    mock_fetch.return_value = ["mock_record_1", "mock_record_2", "mock_record_3"]
    mock_estimate.return_value = {"EUR": 25000.0}

    response = client.post(
        "/connectors/stripe/import",
        json={"api_key": "sk_test_fake"},
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "stripe"
    assert data["record_count"] == 3
    assert data["annual_revenue_estimate"]["EUR"] == 25000.0
