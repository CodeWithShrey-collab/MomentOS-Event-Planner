"""Safe Flask CLI smoke-test behavior without network access."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos import create_app  # noqa: E402
from momentos.ai_provider import OpenAIProvider  # noqa: E402
from momentos.extensions import db  # noqa: E402


def _app(*, api_key: str | None):
    application = create_app(
        {
            "app_env": "testing",
            "database_url": "sqlite:///:memory:",
            "secret_key": "cli-tests-use-a-long-random-looking-test-secret",
            "ai_mode": "live",
            "openai_api_key": api_key,
            "openai_model": "gpt-6-luna",
            "session_cookie_secure": False,
        }
    )
    application.config.update(TESTING=True)
    return application


def test_smoke_command_reports_success_without_disclosing_configuration(monkeypatch):
    monkeypatch.setattr(
        OpenAIProvider,
        "connectivity_check",
        lambda _provider: SimpleNamespace(
            status="completed",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            has_visible_output=True,
            incomplete_reason=None,
        ),
    )
    application = _app(api_key="sk-test-only")
    try:
        result = application.test_cli_runner().invoke(args=["openai-smoke"])
        assert result.exit_code == 0
        assert "gpt-6-luna returned a completed response with visible output" in result.output
        assert "input=unavailable" in result.output
        assert "sk-test-only" not in result.output
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_smoke_command_without_key_does_not_call_provider(monkeypatch):
    def fail_if_called(_provider):
        raise AssertionError("provider must not be called without a configured key")

    monkeypatch.setattr(OpenAIProvider, "connectivity_check", fail_if_called)
    application = _app(api_key=None)
    try:
        result = application.test_cli_runner().invoke(args=["openai-smoke"])
        assert result.exit_code == 2
        assert "OPENAI_API_KEY is not configured" in result.output
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()
