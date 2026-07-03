from __future__ import annotations


class MarginProtectorError(Exception):
    pass


class InvalidOrderError(MarginProtectorError):
    pass


class SecurityError(MarginProtectorError):
    pass


class DisallowedHostError(SecurityError):
    pass


class FxDataError(MarginProtectorError):
    pass


class RateLimitError(FxDataError):
    pass


class InsufficientDataError(FxDataError):
    pass


class SimulationError(MarginProtectorError):
    pass
