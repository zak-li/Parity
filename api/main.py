from __future__ import annotations

from . import create_app
from .observability import configure_logging

configure_logging()
app = create_app()
