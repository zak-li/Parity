from __future__ import annotations

from enum import StrEnum

from ..config import settings


class RiskLevel(StrEnum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"

    @classmethod
    def from_score(cls, score: int) -> RiskLevel:
        if score <= settings.RISK_LOW_MAX_SCORE:
            return cls.LOW
        if score <= settings.RISK_MODERATE_MAX_SCORE:
            return cls.MODERATE
        if score <= settings.RISK_HIGH_MAX_SCORE:
            return cls.HIGH
        return cls.CRITICAL


class SamplingMethod(StrEnum):
    PSEUDO_RANDOM = "pseudo_random"
    SOBOL = "sobol"


class VolatilityModel(StrEnum):
    HISTORICAL = "historical"
    EWMA = "ewma"
    GARCH = "garch"


class ReturnDistribution(StrEnum):
    NORMAL = "normal"
    STUDENT_T = "student_t"


class MarketModel(StrEnum):
    GBM = "gbm"
    HESTON = "heston"


class HedgeInstrument(StrEnum):
    NONE = "none"
    FORWARD = "forward"
    OPTION = "option"
    COLLAR = "collar"
    PARTICIPATING_FORWARD = "participating_forward"


class CopulaType(StrEnum):
    GAUSSIAN = "gaussian"
    STUDENT_T = "student_t"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
