from __future__ import annotations

from dataclasses import dataclass

from ..config import office_des_changes as oc
from .models import OrderInput


@dataclass(frozen=True, slots=True)
class ComplianceConfig:
    regulated_domestic_currency: str = oc.REGULATED_DOMESTIC_CURRENCY
    max_forward_horizon_days: int = oc.MAX_FORWARD_HORIZON_DAYS
    max_repatriation_days: int = oc.MAX_REPATRIATION_DAYS
    ruleset_version: str = oc.RULESET_VERSION
    required_documents: tuple[str, ...] = oc.REQUIRED_DOCUMENTS[oc.DEFAULT_OPERATION]


@dataclass(frozen=True, slots=True)
class ComplianceCheck:
    code: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    applicable: bool
    eligible: bool
    operation: str
    checks: tuple[ComplianceCheck, ...]
    required_documents: tuple[str, ...]
    ruleset_version: str
    disclaimer: str = oc.DISCLAIMER


def evaluate_compliance(
    order: OrderInput,
    config: ComplianceConfig | None = None,
    operation: str = oc.DEFAULT_OPERATION,
) -> ComplianceReport:
    config = config or ComplianceConfig()

    if order.domestic_currency != config.regulated_domestic_currency:
        return ComplianceReport(
            applicable=False,
            eligible=True,
            operation=operation,
            checks=(
                ComplianceCheck(
                    "not_applicable",
                    True,
                    f"Réglementation Office des Changes non applicable "
                    f"(devise locale {order.domestic_currency} ≠ {config.regulated_domestic_currency}).",
                ),
            ),
            required_documents=(),
            ruleset_version=config.ruleset_version,
        )

    checks: list[ComplianceCheck] = []

    operation_ok = operation in oc.ELIGIBLE_OPERATIONS
    checks.append(
        ComplianceCheck(
            "operation_eligibility",
            operation_ok,
            f"Type d'opération '{operation}' "
            + ("éligible à la couverture de change." if operation_ok else "non reconnu."),
        )
    )

    horizon_ok = order.horizon_days <= config.max_forward_horizon_days
    checks.append(
        ComplianceCheck(
            "forward_horizon",
            horizon_ok,
            f"Échéance de couverture ({order.horizon_days} j) "
            f"{'dans' if horizon_ok else 'au-delà de'} la limite usuelle "
            f"de {config.max_forward_horizon_days} j.",
        )
    )

    checks.append(
        ComplianceCheck(
            "commercial_operation",
            order.amount_foreign > oc.MIN_HEDGE_AMOUNT_FOREIGN,
            "Opération commerciale avec montant en devise justifiable.",
        )
    )

    if operation.startswith("export"):
        checks.append(
            ComplianceCheck(
                "repatriation_delay",
                True,
                f"Rapatriement des devises exigé sous {config.max_repatriation_days} j "
                f"après encaissement.",
            )
        )

    documents = oc.REQUIRED_DOCUMENTS.get(operation, config.required_documents)
    checks.append(
        ComplianceCheck(
            "documentation",
            True,
            "Pièces justificatives à réunir avant la mise en place de la couverture.",
        )
    )

    eligible = all(check.passed for check in checks)
    return ComplianceReport(
        applicable=True,
        eligible=eligible,
        operation=operation,
        checks=tuple(checks),
        required_documents=documents,
        ruleset_version=config.ruleset_version,
    )
