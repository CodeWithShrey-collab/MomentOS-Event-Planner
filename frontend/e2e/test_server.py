"""Isolated, deterministic Flask server for the Playwright integration flow."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from momentos import create_app  # noqa: E402


port = int(os.environ.get("MOMENTOS_TEST_PORT", "5001"))
app = create_app(
    {
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "momentos-playwright-only-test-secret-32chars",
        "ai_mode": "demo",
        "openai_model": "gpt-6-luna",
        "app_base_url": "http://127.0.0.1:4173",
        "trusted_origins": "http://127.0.0.1:4173",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    }
)
app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
