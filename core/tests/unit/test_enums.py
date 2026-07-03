from __future__ import annotations

import pytest

from core.models.enums import RiskLevel, SamplingMethod


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, RiskLevel.LOW),
        (25, RiskLevel.LOW),
        (26, RiskLevel.MODERATE),
        (50, RiskLevel.MODERATE),
        (51, RiskLevel.HIGH),
        (75, RiskLevel.HIGH),
        (76, RiskLevel.CRITICAL),
        (100, RiskLevel.CRITICAL),
        (1000, RiskLevel.CRITICAL),
    ],
)
def test_risk_level_from_score_boundaries(score, expected):
    assert RiskLevel.from_score(score) is expected


def test_risk_level_has_french_labels():
    assert RiskLevel.LOW.value == "Faible"
    assert RiskLevel.CRITICAL.value == "Critique"


def test_sampling_method_values():
    assert SamplingMethod.PSEUDO_RANDOM.value == "pseudo_random"
    assert SamplingMethod("sobol") is SamplingMethod.SOBOL
