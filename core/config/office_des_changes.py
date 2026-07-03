from __future__ import annotations

RULESET_VERSION = "2024.1-indicative"

DISCLAIMER = (
    "Analyse indicative fondée sur les usages de l'Instruction Générale des Opérations de "
    "Change. Elle ne constitue pas un avis réglementaire: confirmez l'éligibilité, les délais "
    "et les pièces exigées auprès de votre banque et de l'Office des Changes."
)

REGULATED_DOMESTIC_CURRENCY = "MAD"

MAX_FORWARD_HORIZON_DAYS = 360
MAX_REPATRIATION_DAYS = 90
MIN_HEDGE_AMOUNT_FOREIGN = 0.0

ELIGIBLE_OPERATIONS: tuple[str, ...] = (
    "import_biens",
    "import_services",
    "export_biens",
    "export_services",
)

REQUIRED_DOCUMENTS: dict[str, tuple[str, ...]] = {
    "import_biens": (
        "Facture proforma ou contrat commercial",
        "Titre d'importation domicilié",
        "Engagement d'importation auprès de la banque",
    ),
    "import_services": (
        "Contrat de prestation de services",
        "Facture définitive ou proforma",
    ),
    "export_biens": (
        "Contrat commercial ou bon de commande",
        "Titre d'exportation domicilié",
        "Engagement de rapatriement des devises",
    ),
    "export_services": (
        "Contrat de prestation",
        "Engagement de rapatriement des devises",
    ),
}

DEFAULT_OPERATION = "import_biens"
