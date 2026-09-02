import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from api.dependencies import require_api_key
from core.connectors.base import ConnectorError
from core.connectors.iso20022 import (
    Camt053Parser,
    CreditTransferInstruction,
    Pain001Generator,
)
from core.connectors.odoo import OdooConnector
from core.connectors.shopify import ShopifyConnector
from core.connectors.stripe import StripeConnector
from core.connectors.woocommerce import WooCommerceConnector
from db.records import ApiKeyRecord

router = APIRouter(
    prefix="/api/v1/connectors", tags=["connectors"], dependencies=[Depends(require_api_key)]
)


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


class CamtImportRequest(BaseModel):
    xml_content: str


class CamtImportResponse(BaseModel):
    source: str = "camt.053"
    statement_id: str
    iban: str
    currency: str
    creation_date: str
    opening_balance: float | None = None
    closing_balance: float | None = None
    total_transactions: int
    currency_summary: dict[str, dict[str, float]]
    sales_records_count: int
    purchase_records_count: int


class CreditTransferItem(BaseModel):
    end_to_end_id: str
    amount: float
    currency: str
    creditor_name: str
    creditor_iban: str
    creditor_bic: str | None = None
    execution_date: dt.date | None = None
    remittance_info: str | None = None


class Pain001GenerateRequest(BaseModel):
    initiating_party: str
    debtor_name: str
    debtor_iban: str
    debtor_bic: str | None = None
    transfers: list[CreditTransferItem]
    message_id: str | None = None


@router.post("/iso20022/camt053/import", response_model=CamtImportResponse)
def import_camt053(
    request: CamtImportRequest,
    _: ApiKeyRecord = Depends(require_api_key),
) -> CamtImportResponse:
    try:
        stmt = Camt053Parser.parse(request.xml_content)
        sales = stmt.to_sales_records()
        purchases = stmt.to_purchase_records()

        return CamtImportResponse(
            statement_id=stmt.statement_id,
            iban=stmt.iban,
            currency=stmt.currency,
            creation_date=stmt.creation_date.isoformat(),
            opening_balance=stmt.opening_balance,
            closing_balance=stmt.closing_balance,
            total_transactions=len(stmt.entries),
            currency_summary=stmt.currency_summary(),
            sales_records_count=len(sales),
            purchase_records_count=len(purchases),
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/iso20022/pain001/generate")
def generate_pain001(
    request: Pain001GenerateRequest,
    _: ApiKeyRecord = Depends(require_api_key),
) -> Response:
    try:
        transfer_instructions = [
            CreditTransferInstruction(
                end_to_end_id=item.end_to_end_id,
                amount=item.amount,
                currency=item.currency,
                creditor_name=item.creditor_name,
                creditor_iban=item.creditor_iban,
                creditor_bic=item.creditor_bic,
                execution_date=item.execution_date or dt.date.today(),
                remittance_info=item.remittance_info,
            )
            for item in request.transfers
        ]
        xml_output = Pain001Generator.generate(
            initiating_party=request.initiating_party,
            debtor_name=request.debtor_name,
            debtor_iban=request.debtor_iban,
            debtor_bic=request.debtor_bic,
            transfers=transfer_instructions,
            message_id=request.message_id,
        )
        return Response(
            content=xml_output,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=pain001_transfer.xml"},
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
