from __future__ import annotations

RULESET_VERSION = "2024.1-indicative"

DISCLAIMER = (
    "Indicative analysis based on common practice under the Instruction Générale des "
    "Opérations de Change. It does not constitute regulatory advice: confirm eligibility, "
    "deadlines, and required documents with your bank and the Office des Changes."
)

REGULATED_DOMESTIC_CURRENCY = "MAD"

MAX_FORWARD_HORIZON_DAYS = 360
MAX_REPATRIATION_DAYS = 90
MIN_HEDGE_AMOUNT_FOREIGN = 0.0

ELIGIBLE_OPERATIONS: tuple[str, ...] = (
    "import_goods",
    "import_services",
    "export_goods",
    "export_services",
)

REQUIRED_DOCUMENTS: dict[str, tuple[str, ...]] = {
    "import_goods": (
        "Proforma invoice or commercial contract",
        "Domiciled import license",
        "Import commitment registered with the bank",
    ),
    "import_services": (
        "Service agreement",
        "Final or proforma invoice",
    ),
    "export_goods": (
        "Commercial contract or purchase order",
        "Domiciled export license",
        "Currency repatriation commitment",
    ),
    "export_services": (
        "Service contract",
        "Currency repatriation commitment",
    ),
}

DEFAULT_OPERATION = "import_goods"
