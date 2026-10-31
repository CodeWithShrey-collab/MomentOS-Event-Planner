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
    assert settings.ai_pricing_config_version == "openai-gpt-6-luna-standard-2026-10-31-v2"
    assert settings.ai_input_usd_per_million == 0.10
    assert settings.ai_cached_input_usd_per_million == 0.01
    assert settings.ai_output_usd_per_million == 0.50


def test_settings_reject_any_live_model_substitution():
    with pytest.raises(ValueError, match="exactly gpt-6-luna"):
        Settings(_env_file=None, app_env="testing", openai_model="another-model")


def production_values(**updates):
    values = {
        "app_env": "production",
        "app_base_url": "https://momentos.example",
        "secret_key": "a-safe-test-secret-that-is-not-a-real-credential",
        "database_url": "postgresql://default:placeholder@ep-neon-pooler.example/neondb?sslmode=require&channel_binding=require",
        "ai_mode": "live",
        "openai_api_key": "test-only-not-a-provider-key",
        "session_cookie_secure": True,
        "trusted_origins": "https://momentos.example",
        "rate_limit_storage_uri": "rediss://default:placeholder@ratelimit.example:6379/0",
        "rate_limit_client_ip_source": "render_cf_connecting_ip",
        "proxy_fix_x_for": 0,
        "proxy_fix_x_proto": 0,
        "proxy_fix_x_host": 0,
    }
    values.update(updates)
    return values


def test_production_settings_require_live_ai_postgres_https_redis_and_safe_render_client_ip():
    settings = Settings(_env_file=None, **production_values())
    assert settings.database_uri.startswith("postgresql+psycopg://")
    from sqlalchemy.engine import make_url

    postgres_url = make_url(settings.database_uri)
    assert postgres_url.password == "placeholder"
    assert postgres_url.query["sslmode"] == "verify-full"
    assert postgres_url.query["channel_binding"] == "require"
    assert postgres_url.query["connect_timeout"] == "10"
    assert settings.cookie_secure is True
    assert settings.session_cookie_samesite == "Lax"
    assert settings.openai_reasoning_effort == "low"
    from urllib.parse import parse_qs, urlsplit

    redis_options = parse_qs(urlsplit(settings.rate_limit_storage_uri).query)
    assert redis_options["ssl_cert_reqs"] == ["required"]
    assert redis_options["ssl_check_hostname"] == ["true"]

    invalid = [
        ({"ai_mode": "demo"}, "AI_MODE=live"),
        ({"openai_api_key": None}, "OPENAI_API_KEY"),
        ({"database_url": "sqlite:///momentos.sqlite3"}, "PostgreSQL DATABASE_URL"),
        ({"app_base_url": "http://momentos.example"}, "HTTPS origin"),
        ({"trusted_origins": "https://momentos.example,http://localhost:5000"}, "only HTTPS origins"),
        ({"rate_limit_storage_uri": "memory://"}, "RATE_LIMIT_STORAGE_URI"),
        ({"rate_limit_storage_uri": "redis://default:token@cache.example:6379"}, "rediss://"),
        ({"rate_limit_client_ip_source": "socket"}, "RATE_LIMIT_CLIENT_IP_SOURCE=render_cf_connecting_ip"),
        ({"proxy_fix_x_for": 1}, "must not trust X-Forwarded"),
        ({"proxy_fix_x_proto": 1}, "must not trust X-Forwarded"),
        ({"proxy_fix_x_host": 1}, "must not trust X-Forwarded"),
        ({"session_cookie_samesite": "Strict"}, "SESSION_COOKIE_SAMESITE=Lax"),
        ({"openai_reasoning_effort": "medium"}, "OPENAI_REASONING_EFFORT=low"),
    ]
    for overrides, message in invalid:
        with pytest.raises(ValueError, match=message):
            Settings(_env_file=None, **production_values(**overrides))


def test_production_database_uri_preserves_encoded_credentials_and_neon_options():
    settings = Settings(
        _env_file=None,
        **production_values(
            database_url=(
                "postgresql://planner%40example:p%2F%40%3Fword@ep-neon-pooler.example/neondb"
                "?sslmode=require&channel_binding=require&options=-c%20statement_timeout%3D5000"
            )
        ),
    )
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_uri)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "planner@example"
    assert url.password == "p/@?word"
    assert url.query["sslmode"] == "verify-full"
    assert url.query["channel_binding"] == "require"
    assert url.query["options"] == "-c statement_timeout=5000"


def test_postgres_pool_is_bounded_and_checks_stale_connections():
    from momentos import create_app
    from momentos.extensions import limiter

    app = create_app(production_values())
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"] == {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 2,
        "max_overflow": 0,
        "pool_timeout": 10,
    }
    redis_client = app.extensions["momentos_rate_limit_redis"]
    redis_options = redis_client.connection_pool.connection_kwargs
    assert redis_client.connection_pool.connection_class.__name__ == "SSLConnection"
    assert redis_options["ssl_cert_reqs"] == "required"
    assert redis_options["ssl_check_hostname"] is True
    with app.app_context():
        limiter_storage = limiter.storage
    assert type(limiter_storage).__name__ == "RedisStorage"
    limiter_redis_options = limiter_storage.storage.connection_pool.connection_kwargs
    assert limiter_storage.storage.connection_pool.connection_class.__name__ == "SSLConnection"
    assert limiter_redis_options["ssl_cert_reqs"] == "required"
    assert limiter_redis_options["ssl_check_hostname"] is True


def test_redis_url_tls_options_override_unsafe_existing_values_and_preserve_other_options():
    from urllib.parse import parse_qs, urlsplit

    settings = Settings(
        _env_file=None,
        **production_values(
            rate_limit_storage_uri=(
                "rediss://default:placeholder@ratelimit.example:6379/0"
                "?ssl_cert_reqs=none&ssl_check_hostname=false&client_name=momentos"
            )
        ),
    )

    parts = urlsplit(settings.rate_limit_storage_uri)
    options = parse_qs(parts.query)
    assert parts.hostname == "ratelimit.example"
    assert parts.path == "/0"
    assert options["client_name"] == ["momentos"]
    assert options["ssl_cert_reqs"] == ["required"]
    assert options["ssl_check_hostname"] == ["true"]


def test_production_settings_errors_do_not_echo_database_credentials():
    marker = "do-not-emit-this-database-secret"
    with pytest.raises(ValueError) as captured:
        Settings(
            _env_file=None,
            **production_values(database_url=f"mysql://planner:{marker}@db.example/momentos"),
        )
    assert marker not in str(captured.value)


def test_startup_dependency_probe_retries_only_idempotent_probes_and_sanitizes_errors():
    from momentos.cli import _verify_production_dependencies

    calls = {"db": 0, "redis": 0, "sleep": 0}

    def database_check():
        calls["db"] += 1

    def redis_check():
        calls["redis"] += 1
        if calls["redis"] < 3:
            raise ConnectionError("private endpoint and token must not escape")

    def sleep(_seconds):
        calls["sleep"] += 1

    assert _verify_production_dependencies(database_check, redis_check, sleep=sleep) is None
    assert calls == {"db": 3, "redis": 3, "sleep": 2}

    def always_fails():
        raise ConnectionError("private endpoint and token must not escape")

    error_type = _verify_production_dependencies(always_fails, lambda: None, sleep=lambda _seconds: None)
    assert error_type == "ConnectionError"
    assert "private endpoint" not in error_type


def test_production_preflight_cli_uses_database_and_shared_store_probes():
    from types import SimpleNamespace

    from momentos import create_app
    from momentos.extensions import db

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "preflight-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "openai_api_key": None,
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    })
    with app.app_context():
        app.extensions["momentos_settings"] = Settings(_env_file=None, **production_values())
        app.extensions["momentos_rate_limit_redis"] = SimpleNamespace(ping=lambda: True)

    result = app.test_cli_runner().invoke(args=["production-preflight"])

    assert result.exit_code == 0
    assert "preflight passed" in result.output
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_alembic_upgrade_is_repeatable_on_disposable_sqlite():
    from momentos import create_app
    from momentos.extensions import db

    app = create_app({
        "app_env": "development",
        "database_url": "sqlite:///:memory:",
        "secret_key": "migration-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "openai_api_key": None,
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    })
    runner = app.test_cli_runner()

    for _ in range(2):
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, "Alembic upgrade failed in isolated in-memory SQLite"

    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_production_readiness_requires_reachable_rate_limit_store():
    from types import SimpleNamespace

    from momentos import create_app
    from momentos.extensions import db

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "readiness-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    })
    app.config.update(TESTING=True)
    with app.app_context():
        production_settings = Settings(_env_file=None, **production_values())
        app.extensions["momentos_settings"] = production_settings

    def unavailable():
        raise ConnectionError("private endpoint and token must not escape")

    app.extensions["momentos_rate_limit_redis"] = SimpleNamespace(ping=unavailable)
    response = app.test_client().get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json["data"]["components"]["rate_limit_store"] == "unavailable"
    assert "private endpoint" not in response.get_data(as_text=True)
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


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


def test_proxy_fix_configured_chain_ignores_leftmost_untrusted_value():
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


def test_render_production_settings_ignore_forged_forwarded_headers():
    from flask import jsonify, request

    from momentos import create_app
    from momentos.extensions import db

    app = create_app(production_values())

    @app.get("/__test__/proxy-context")
    def proxy_context():
        return jsonify(remote_addr=request.remote_addr, scheme=request.scheme, host=request.host)

    response = app.test_client().get(
        "/__test__/proxy-context",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={
            "Host": "momentos.example",
            "X-Forwarded-For": "203.0.113.99, 198.51.100.23",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "attacker.example",
        },
    )
    assert response.status_code == 200
    assert response.json == {"remote_addr": "10.0.0.5", "scheme": "http", "host": "momentos.example"}
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_render_client_ip_source_is_validated_and_ignores_spoofable_xff():
    from flask import jsonify, request

    from momentos import create_app
    from momentos.extensions import db, limiter

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "proxy-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
        "rate_limit_client_ip_source": "render_cf_connecting_ip",
    })

    @app.get("/__test__/limited-by-client-ip")
    @limiter.limit("2 per minute")
    def limited_by_client_ip():
        return jsonify(client_ip=request.remote_addr)

    client = app.test_client()
    statuses = []
    for forged_ip in ("203.0.113.1", "203.0.113.2", "203.0.113.3"):
        response = client.get(
            "/__test__/limited-by-client-ip",
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
            headers={
                "CF-Connecting-IP": "198.51.100.77",
                "X-Forwarded-For": forged_ip,
            },
        )
        statuses.append(response.status_code)
    assert statuses == [200, 200, 429]

    with app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={"CF-Connecting-IP": "not-an-ip", "X-Forwarded-For": "203.0.113.9"},
    ):
        from momentos.extensions import rate_limit_client_address

        assert rate_limit_client_address() == "10.0.0.5"
    with app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={"CF-Connecting-IP": "2001:0db8::1"},
    ):
        from momentos.extensions import rate_limit_client_address

        assert rate_limit_client_address() == "2001:db8::1"

    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_socket_rate_limit_source_ignores_all_forwarded_address_headers():
    from momentos import create_app
    from momentos.extensions import rate_limit_client_address

    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "socket-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
        "rate_limit_client_ip_source": "socket",
    })
    with app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={
            "CF-Connecting-IP": "203.0.113.9",
            "X-Forwarded-For": "203.0.113.8",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "attacker.example",
        },
    ):
        assert rate_limit_client_address() == "10.0.0.5"

    from momentos.extensions import db

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
