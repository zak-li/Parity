from __future__ import annotations

import re

from ..config import settings
from .exceptions import InvalidOrderError

_CURRENCY_REGEX = re.compile(rf"^{settings.CURRENCY_CODE_PATTERN}$")


def normalize_currency_code(code: str) -> str:
    if not isinstance(code, str):
        raise ValueError("Le code devise doit être une chaîne de caractères.")
    normalized = code.strip().upper()
    if not _CURRENCY_REGEX.fullmatch(normalized):
        raise ValueError(
            f"Code devise invalide: {code!r}. Format attendu: ISO 4217 (ex: USD, EUR, MAD)."
        )
    return normalized


def validate_currency_code(code: str) -> str:
    try:
        return normalize_currency_code(code)
    except ValueError as exc:
        raise InvalidOrderError(str(exc)) from exc
