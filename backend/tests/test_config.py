"""Environment source and model-lock configuration tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos.config import PROJECT_ROOT, Settings  # noqa: E402


def test_settings_use_project_root_env_file_and_safe_example(monkeypatch):
    for name in ("AI_MODE", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=PROJECT_ROOT / ".env.example", app_env="testing")

    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env"
    assert settings.ai_mode == "demo"
    assert settings.openai_model == "gpt-6-luna"
    assert settings.openai_reasoning_effort == "low"
    assert settings.openai_key is None


def test_settings_reject_any_live_model_substitution():
    with pytest.raises(ValueError, match="exactly gpt-6-luna"):
        Settings(_env_file=None, app_env="testing", openai_model="another-model")


def production_values(**updates):
    values = {
        "app_env": "production",
        "app_base_url": "https://momentos.example",
        "secret_key": "a-safe-test-secret-that-is-not-a-real-credential",
        "database_url": "postgresql://db.example/momentos",
        "ai_mode": "live",
        "openai_api_key": "test-only-not-a-provider-key",
        "session_cookie_secure": True,
        "trusted_origins": "https://momentos.example",
        "rate_limit_storage_uri": "redis://ratelimit.example:6379/0",
        "proxy_fix_x_for": 2,
        "proxy_fix_x_proto": 1,
    }
    values.update(updates)
    return values


def test_production_settings_require_live_ai_postgres_https_redis_and_trusted_proxy():
    settings = Settings(_env_file=None, **production_values())
    assert settings.database_uri.startswith("postgresql+psycopg://")
    assert settings.cookie_secure is True

    invalid = [
        ({"ai_mode": "demo"}, "AI_MODE=live"),
        ({"openai_api_key": None}, "OPENAI_API_KEY"),
        ({"database_url": "sqlite:///momentos.sqlite3"}, "PostgreSQL DATABASE_URL"),
        ({"app_base_url": "http://momentos.example"}, "HTTPS origin"),
        ({"trusted_origins": "https://momentos.example,http://localhost:5000"}, "only HTTPS origins"),
        ({"rate_limit_storage_uri": "memory://"}, "shared RATE_LIMIT_STORAGE_URI"),
        ({"proxy_fix_x_for": 0}, "trusted proxy counts"),
        ({"proxy_fix_x_proto": 0}, "trusted proxy counts"),
    ]
    for overrides, message in invalid:
        with pytest.raises(ValueError, match=message):
            Settings(_env_file=None, **production_values(**overrides))


def test_proxy_fix_uses_only_configured_rightmost_forwarded_client_ip():
    from flask import jsonify, request

    from momentos import create_app

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite://",
        "proxy_fix_x_for": 1,
    })

    @app.get("/__test__/remote-address")
    def remote_address():
        return jsonify(remote_addr=request.remote_addr)

    response = app.test_client().get(
        "/__test__/remote-address",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={"X-Forwarded-For": "203.0.113.99, 198.51.100.23"},
    )
    assert response.json == {"remote_addr": "198.51.100.23"}


def test_proxy_fix_render_two_proxy_chain_ignores_leftmost_untrusted_value():
    from flask import jsonify, request

    from momentos import create_app

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite://",
        "proxy_fix_x_for": 2,
    })

    @app.get("/__test__/remote-address")
    def remote_address():
        return jsonify(remote_addr=request.remote_addr)

    response = app.test_client().get(
        "/__test__/remote-address",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={"X-Forwarded-For": "203.0.113.99, 198.51.100.23, 192.0.2.10"},
    )
    assert response.json == {"remote_addr": "198.51.100.23"}
