"""Parity module alias."""

from __future__ import annotations

import sys

import sdk

# Re-export all public symbols from sdk
__all__ = list(sdk.__all__)
for _name in __all__:
    globals()[_name] = getattr(sdk, _name)

# Register in sys.modules
sys.modules["Parity"] = sdk
sys.modules["parity"] = sdk
