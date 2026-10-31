"""Production frontend fallback and asset-path smoke tests."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos import create_app  # noqa: E402
from momentos.extensions import db  # noqa: E402


def _test_app(frontend_dist_dir: Path) -> object:
    app = create_app({
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "frontend-test-secret-with-more-than-thirty-two-characters",
        "ai_mode": "demo",
        "openai_model": "gpt-6-luna",
        "frontend_dist_dir": frontend_dist_dir,
        "app_base_url": "http://localhost",
        "trusted_origins": "http://localhost",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    })
    app.config.update(TESTING=True)
    return app


def test_static_assets_and_spa_routes_use_the_configured_build_directory(tmp_path: Path) -> None:
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>MomentOS test build</title>", encoding="utf-8")
    (build / "assets" / "app.js").write_text("globalThis.momentos = true;", encoding="utf-8")
    app = _test_app(build)

    try:
        client = app.test_client()
        index = client.get("/")
        asset = client.get("/assets/app.js")
        spa_route = client.get("/events/test-event/budget")
        missing_asset = client.get("/assets/missing.js")
        private_env_path = client.get("/.env")
        unknown_api = client.get("/api/v1/not-a-real-route")

        assert index.status_code == 200
        assert b"MomentOS test build" in index.data
        assert asset.status_code == 200
        assert b"globalThis.momentos" in asset.data
        assert spa_route.status_code == 200
        assert b"MomentOS test build" in spa_route.data
        assert missing_asset.status_code == 404
        assert private_env_path.status_code == 404
        assert unknown_api.status_code == 404
        assert b"MomentOS test build" not in unknown_api.data
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def test_built_frontend_assets_api_and_spa_route_are_served() -> None:
    build = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not (build / "index.html").is_file():
        pytest.skip("build the frontend before checking its production asset paths")

    app = _test_app(build)
    try:
        client = app.test_client()
        index = client.get("/")
        script_match = re.search(rb'<script[^>]+src="([^"]+\.js)"', index.data)
        stylesheet_match = re.search(rb'<link[^>]+href="([^"]+\.css)"', index.data)
        assert index.status_code == 200
        assert script_match is not None
        assert stylesheet_match is not None
        assert client.get(script_match.group(1).decode()).status_code == 200
        assert client.get(stylesheet_match.group(1).decode()).status_code == 200

        spa_route = client.get("/events/test-event/ripple")
        assert spa_route.status_code == 200
        assert spa_route.data == index.data
        assert client.get("/api/v1/health/ready").status_code == 200
        assert client.get("/api/v1/route-does-not-exist").status_code == 404
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
