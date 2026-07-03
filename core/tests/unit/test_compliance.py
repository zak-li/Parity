from __future__ import annotations

import datetime as dt

import pytest

from core.models.compliance import ComplianceConfig, evaluate_compliance
from core.models.models import OrderInput


def _order(domestic="MAD", horizon_days=90):
    return OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency=domestic,
        order_date=dt.date(2026, 1, 1),
        delivery_date=dt.date(2026, 1, 1) + dt.timedelta(days=horizon_days),
        target_margin_pct=0.2,
    )


def test_mad_order_is_applicable_and_lists_documents():
    report = evaluate_compliance(_order("MAD"))
    assert report.applicable
    assert report.eligible
    assert len(report.required_documents) >= 1
    assert any(c.code == "documentation" for c in report.checks)


def test_non_mad_order_is_not_applicable():
    report = evaluate_compliance(_order("EUR"))
    assert not report.applicable
    assert report.eligible
    assert report.required_documents == ()
    assert report.checks[0].code == "not_applicable"


def test_horizon_beyond_limit_flags_check():
    report = evaluate_compliance(_order("MAD", horizon_days=500))
    horizon_check = next(c for c in report.checks if c.code == "forward_horizon")
    assert not horizon_check.passed
    assert not report.eligible


def test_horizon_within_limit_passes():
    report = evaluate_compliance(_order("MAD", horizon_days=200))
    horizon_check = next(c for c in report.checks if c.code == "forward_horizon")
    assert horizon_check.passed


def test_custom_config_changes_limit():
    config = ComplianceConfig(max_forward_horizon_days=30)
    report = evaluate_compliance(_order("MAD", horizon_days=90), config)
    horizon_check = next(c for c in report.checks if c.code == "forward_horizon")
    assert not horizon_check.passed


def test_report_carries_disclaimer():
    report = evaluate_compliance(_order("MAD"))
    assert "Office des Changes" in report.disclaimer


def test_report_carries_ruleset_version():
    report = evaluate_compliance(_order("MAD"))
    assert report.ruleset_version
    assert report.operation == "import_biens"


def test_unknown_operation_is_flagged():
    report = evaluate_compliance(_order("MAD"), operation="blanchiment")
    check = next(c for c in report.checks if c.code == "operation_eligibility")
    assert not check.passed
    assert not report.eligible


def test_export_operation_adds_repatriation_check_and_documents():
    report = evaluate_compliance(_order("MAD"), operation="export_biens")
    codes = {c.code for c in report.checks}
    assert "repatriation_delay" in codes
    assert any("rapatriement" in d.lower() for d in report.required_documents)


def test_documents_depend_on_operation():
    imp = evaluate_compliance(_order("MAD"), operation="import_biens")
    svc = evaluate_compliance(_order("MAD"), operation="import_services")
    assert imp.required_documents != svc.required_documents
