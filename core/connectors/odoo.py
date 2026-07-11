import datetime as dt
from xmlrpc import client as xmlrpclib

from .base import ConnectorError, PurchaseConnector, PurchaseRecord


class OdooConnector(PurchaseConnector):
    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self._authenticate()

    def _authenticate(self):
        try:
            common = xmlrpclib.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            if not self.uid:
                raise ConnectorError("Odoo authentication failed: Invalid credentials.")
            self.models = xmlrpclib.ServerProxy(f"{self.url}/xmlrpc/2/object")
        except Exception as exc:
            raise ConnectorError(f"Odoo connection error: {exc}") from exc

    def fetch_purchases(self, days_lookback: int = 90) -> list[PurchaseRecord]:
        if not self.uid:
            raise ConnectorError("Not authenticated")

        start_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_lookback)

        try:
            # Search for purchase orders
            domain = [
                ["date_order", ">=", start_date.strftime("%Y-%m-%d %H:%M:%S")],
                ["state", "in", ["purchase", "done"]],
            ]

            fields = ["name", "amount_total", "currency_id", "date_order", "date_planned", "state"]

            orders = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                "purchase.order",
                "search_read",
                [domain],
                {"fields": fields, "limit": 200},
            )

            records = []
            for order in orders:
                # Odoo returns currency_id as [id, "EUR"]
                currency = "UNK"
                if isinstance(order.get("currency_id"), list) and len(order["currency_id"]) == 2:
                    currency = order["currency_id"][1]

                planned = order.get("date_planned")
                expected_date = (
                    dt.datetime.strptime(planned.split(" ")[0], "%Y-%m-%d").date()
                    if planned
                    else None
                )

                records.append(
                    PurchaseRecord(
                        id=str(order["id"]),
                        currency=currency,
                        amount=float(order.get("amount_total", 0.0)),
                        created_at=dt.datetime.strptime(
                            order["date_order"], "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=dt.UTC),
                        expected_delivery_date=expected_date,
                        status=order["state"],
                    )
                )
            return records

        except Exception as exc:
            raise ConnectorError(f"Odoo API error: {exc}") from exc
