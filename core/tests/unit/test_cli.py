from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from core.cli import build_parser, main
from core.models.enums import RiskLevel
from core.models.models import SimulationResult


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(
        [
            "simulate",
            "--amount",
            "100000",
            "--foreign",
            "USD",
            "--domestic",
            "EUR",
            "--delivery",
            "2026-10-01",
        ]
    )
    assert args.amount == 100000.0
    assert args.foreign == "USD"
    assert args.domestic == "EUR"
    assert args.delivery == "2026-10-01"
    assert args.target_margin == 0.15
    assert args.simulations == 10000


@patch("core.cli.MarginRiskEngine")
def test_cli_simulate_run(mock_engine_cls, capsys):
    mock_engine = MagicMock()
    mock_result = MagicMock(spec=SimulationResult)
    mock_result.vulnerability_score = 35
    mock_result.risk_level = RiskLevel.MODERATE
    mock_result.expected_terminal_rate = 1.0850
    mock_result.probability_margin_below_threshold = 0.12
    mock_result.expected_shortfall_margin_pct = 0.08
    mock_result.hedge = MagicMock(optimal_hedge_ratio=1.0, hedged_margin_pct=0.14)

    mock_engine.run.return_value = mock_result
    mock_engine_cls.return_value = mock_engine

    code = main(
        [
            "simulate",
            "-a",
            "50000",
            "-f",
            "USD",
            "-d",
            "EUR",
            "--delivery",
            "2026-12-01",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "Parity Currency Risk Analysis" in captured.out
    assert "Vulnerability Score: 35/100" in captured.out


@patch("core.cli.MarginRiskEngine")
def test_cli_simulate_json(mock_engine_cls, capsys):
    mock_engine = MagicMock()
    mock_result = MagicMock(spec=SimulationResult)
    mock_result.vulnerability_score = 25
    mock_result.risk_level = RiskLevel.LOW
    mock_result.expected_terminal_rate = 1.0850
    mock_result.probability_margin_below_threshold = 0.05
    mock_result.expected_shortfall_margin_pct = 0.02
    mock_result.hedge = MagicMock(optimal_hedge_ratio=0.5, hedged_margin_pct=0.15)

    mock_engine.run.return_value = mock_result
    mock_engine_cls.return_value = mock_engine

    code = main(
        [
            "simulate",
            "-a",
            "50000",
            "-f",
            "USD",
            "-d",
            "EUR",
            "--delivery",
            "2026-12-01",
            "--json",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["vulnerability_score"] == 25
    assert data["risk_level"] == "Low"


def test_cli_simulate_invalid_date(capsys):
    code = main(
        [
            "simulate",
            "-a",
            "50000",
            "-f",
            "USD",
            "-d",
            "EUR",
            "--delivery",
            "invalid-date",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "invalid delivery date" in err


@patch("core.cli.MarginRiskEngine")
def test_cli_simulate_engine_error(mock_engine_cls, capsys):
    mock_engine = MagicMock()
    mock_engine.run.side_effect = RuntimeError("Market connection failed")
    mock_engine_cls.return_value = mock_engine

    code = main(
        [
            "simulate",
            "-a",
            "50000",
            "-f",
            "USD",
            "-d",
            "EUR",
            "--delivery",
            "2026-12-01",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "Simulation failed" in err


def test_cli_health(capsys):
    code = main(["health"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Parity" in captured.out


def test_cli_no_args():
    code = main([])
    assert code == 0
