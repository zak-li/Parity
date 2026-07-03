from __future__ import annotations

from .base import FxDataProvider
from .frankfurter import FrankfurterFxDataProvider
from .static import StaticFxDataProvider

__all__ = ["FrankfurterFxDataProvider", "FxDataProvider", "StaticFxDataProvider"]
