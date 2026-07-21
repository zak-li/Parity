from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.dependencies import require_api_key
from core.connectors.base import ConnectorError
from core.connectors.odoo import OdooConnector
from core.connectors.shopify import ShopifyConnector
from core.connectors.stripe import StripeConnector
from core.connectors.woocommerce import WooCommerceConnector
from db.records import ApiKeyRecord

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


class ShopifyCredentials(BaseModel):
    shop_name: str
    access_token: str


class WooCommerceCredentials(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str


class StripeCredentials(BaseModel):
    api_key: str


class OdooCredentials(BaseModel):
    url: str
    db: str
    username: str
    password: str


class ConnectorResponse(BaseModel):
    source: str
    record_count: int
    annual_revenue_estimate: dict[str, float] | None = None
    currency_totals: dict[str, float] | None = None


@router.post("/shopify/import", response_model=ConnectorResponse)
def import_shopify(
    creds: ShopifyCredentials, lookback_days: int = 30, _: ApiKeyRecord = Depends(require_api_key)
):
    try:
        connector = ShopifyConnector(creds.shop_name, creds.access_token)
        sales = connector.fetch_sales(lookback_days)
        revenue = connector.estimate_annual_revenue()

        return ConnectorResponse(
            source="shopify", record_count=len(sales), annual_revenue_estimate=revenue
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/woocommerce/import", response_model=ConnectorResponse)
def import_woocommerce(
    creds: WooCommerceCredentials,
    lookback_days: int = 30,
    _: ApiKeyRecord = Depends(require_api_key),
):
    try:
        connector = WooCommerceConnector(creds.store_url, creds.consumer_key, creds.consumer_secret)
        sales = connector.fetch_sales(lookback_days)
        revenue = connector.estimate_annual_revenue()

        return ConnectorResponse(
            source="woocommerce", record_count=len(sales), annual_revenue_estimate=revenue
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/stripe/import", response_model=ConnectorResponse)
def import_stripe(
    creds: StripeCredentials, lookback_days: int = 30, _: ApiKeyRecord = Depends(require_api_key)
):
    try:
        connector = StripeConnector(creds.api_key)
        sales = connector.fetch_sales(lookback_days)
        revenue = connector.estimate_annual_revenue()

        return ConnectorResponse(
            source="stripe", record_count=len(sales), annual_revenue_estimate=revenue
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/odoo/import", response_model=ConnectorResponse)
def import_odoo(
    creds: OdooCredentials, lookback_days: int = 90, _: ApiKeyRecord = Depends(require_api_key)
):
    try:
        connector = OdooConnector(creds.url, creds.db, creds.username, creds.password)
        purchases = connector.fetch_purchases(lookback_days)

        totals: dict[str, float] = {}
        for p in purchases:
            totals[p.currency] = totals.get(p.currency, 0.0) + p.amount

        return ConnectorResponse(source="odoo", record_count=len(purchases), currency_totals=totals)
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
