"""WSGI entry point for Flask/Gunicorn and Flask-Migrate commands."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos import create_app  # noqa: E402

app = create_app()
