from __future__ import annotations

from enum import Enum

from ..config import settings


class RiskLevel(str, Enum):
    LOW = "Faible"
    MODERATE = "Modéré"
    HIGH = "Élevé"
    CRITICAL = "Critique"

    @classmethod
    def from_score(cls, score: int) -> "RiskLevel":
        if score <= settings.RISK_LOW_MAX_SCORE:
            return cls.LOW
        if score <= settings.RISK_MODERATE_MAX_SCORE:
            return cls.MODERATE
        if score <= settings.RISK_HIGH_MAX_SCORE:
            return cls.HIGH
        return cls.CRITICAL


class SamplingMethod(str, Enum):
    PSEUDO_RANDOM = "pseudo_random"
    SOBOL = "sobol"


class VolatilityModel(str, Enum):
    HISTORICAL = "historical"
    EWMA = "ewma"
    GARCH = "garch"


class ReturnDistribution(str, Enum):
    NORMAL = "normal"
    STUDENT_T = "student_t"


class MarketModel(str, Enum):
    GBM = "gbm"
    HESTON = "heston"


class HedgeInstrument(str, Enum):
    NONE = "none"
    FORWARD = "forward"
    OPTION = "option"
    COLLAR = "collar"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
