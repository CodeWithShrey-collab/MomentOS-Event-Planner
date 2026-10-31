from __future__ import annotations

import logging
import os
import secrets
import uuid
from pathlib import Path
from werkzeug.exceptions import HTTPException

from flask import Flask, abort, g, jsonify, request, send_from_directory
from pydantic import ValidationError
from redis import Redis
from sqlalchemy import event as sqlalchemy_event, text
from sqlalchemy.engine import Engine
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Settings, load_settings
from .errors import ApiError, error_payload
from .extensions import db, limiter, migrate


def create_app(overrides: dict[str, object] | None = None) -> Flask:
    settings = load_settings(overrides)
    app = Flask(__name__)
    app.extensions["momentos_settings"] = settings
    app.config.update(
        SECRET_KEY=settings.secret_key.get_secret_value() if settings.secret_key else secrets.token_urlsafe(48),
        DEBUG=False,
        SQLALCHEMY_DATABASE_URI=settings.database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=settings.max_content_length,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        SESSION_COOKIE_SAMESITE=settings.session_cookie_samesite,
        RATELIMIT_STORAGE_URI=settings.rate_limit_storage_uri,
        RATELIMIT_HEADERS_ENABLED=True,
        JSON_SORT_KEYS=False,
    )
    if settings.database_uri.startswith("postgresql+psycopg://"):
        # Keep a small per-worker pool for the free Render instance and recover
        # stale sockets after Neon autosuspends an idle compute.
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 2,
            "max_overflow": 0,
            "pool_timeout": 10,
        }
    if settings.is_production:
        # Separate health client: Flask-Limiter still owns its own Redis pool.
        # TLS verification and hostname checking are explicit for Upstash.
        app.extensions["momentos_rate_limit_redis"] = Redis.from_url(
            settings.rate_limit_storage_uri,
            socket_connect_timeout=3,
            socket_timeout=3,
            ssl_cert_reqs="required",
            ssl_check_hostname=True,
            health_check_interval=30,
        )
    if settings.proxy_fix_x_for or settings.proxy_fix_x_proto or settings.proxy_fix_x_host:
        # Non-production deployments may opt in only after documenting their
        # own exact proxy chain. Production Render settings reject nonzero
        # counts and use a validated Cloudflare client-IP header for limits.
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=settings.proxy_fix_x_for,
            x_proto=settings.proxy_fix_x_proto,
            x_host=settings.proxy_fix_x_host,
        )
    frontend_dist_dir = settings.frontend_dist_dir
    if frontend_dist_dir is None and settings.is_production:
        candidate = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        if candidate.is_dir():
            frontend_dist_dir = candidate
    if frontend_dist_dir is not None:
        frontend_dist_dir = Path(frontend_dist_dir).resolve()
        app.config["FRONTEND_DIST_DIR"] = str(frontend_dist_dir)

        @app.get("/", endpoint="frontend_index")
        def frontend_index():
            return send_from_directory(frontend_dist_dir, "index.html")

        @app.get("/<path:frontend_path>", endpoint="frontend_asset_or_spa")
        def frontend_asset_or_spa(frontend_path: str):
            # Keep unknown API paths as API 404s; they must never return the
            # SPA document with a misleading 200 status.
            if frontend_path == "api" or frontend_path.startswith("api/"):
                abort(404)
            if any(part.startswith(".") for part in Path(frontend_path).parts):
                abort(404)
            try:
                return send_from_directory(frontend_dist_dir, frontend_path)
            except NotFound:
                # Client-side routes have no filename extension. Missing
                # assets stay 404 instead of receiving index.html.
                if Path(frontend_path).suffix:
                    abort(404)
                return send_from_directory(frontend_dist_dir, "index.html")
    if settings.database_uri.startswith("sqlite:///"):
        db_path = settings.database_uri.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(__file__).resolve().parents[1] / "migrations"))
    limiter.init_app(app)

    if settings.database_uri.startswith("sqlite"):
        @sqlalchemy_event.listens_for(Engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            module = dbapi_connection.__class__.__module__
            if "sqlite3" not in module:
                return
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    with app.app_context():
        from . import models  # noqa: F401

        if os.environ.get("MOMENTOS_CREATE_SCHEMA", "").lower() == "true" or settings.app_env == "testing":
            db.create_all()

    @app.before_request
    def request_setup():
        g.request_id = str(uuid.uuid4())
        if request.method in {"POST", "PUT", "PATCH"} and request.endpoint not in {"api.create_session"}:
            if request.content_length and not request.is_json:
                raise ApiError(415, "unsupported_media_type", "Send this request as JSON.")

    @app.after_request
    def request_teardown(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache"
        if request.path.startswith("/api/"):
            try:
                db.session.commit()
            except Exception as error:
                db.session.rollback()
                app.logger.error("request_commit_failed request_id=%s error_type=%s", getattr(g, "request_id", ""), type(error).__name__)
                if response.status_code < 400:
                    body, status = error_payload(
                        ApiError(500, "internal_error", "Something went wrong. Please try again."),
                        getattr(g, "request_id", str(uuid.uuid4())),
                    )
                    response = jsonify(body)
                    response.status_code = status
        return response

    @app.teardown_request
    def rollback_if_needed(_error):
        if db.session.is_active:
            db.session.rollback()

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        db.session.rollback()
        body, status = error_payload(error, getattr(g, "request_id", str(uuid.uuid4())))
        response = jsonify(body)
        response.status_code = status
        if status == 429:
            response.headers["Retry-After"] = str(error.retry_after_seconds or 60)
        return response

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        db.session.rollback()
        from .errors import validation_fields

        return jsonify({
            "error": {
                "code": "validation_failed",
                "message": "Check the highlighted fields and try again.",
                "fields": validation_fields(error.errors()),
            },
            "request_id": getattr(g, "request_id", ""),
        }), 422

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({
            "error": {"code": "request_too_large", "message": "This request is larger than the allowed limit."},
            "request_id": getattr(g, "request_id", ""),
        }), 413

    @app.errorhandler(400)
    def bad_request(_error):
        return jsonify({
            "error": {"code": "invalid_json", "message": "Send a valid JSON request."},
            "request_id": getattr(g, "request_id", ""),
        }), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        db.session.rollback()
        status = error.code or 500
        code = "rate_limited" if status == 429 else ("not_found" if status == 404 else "invalid_request")
        message = "Please wait before trying again." if status == 429 else ("The requested resource was not found." if status == 404 else "The request could not be completed.")
        body, _ = error_payload(ApiError(status, code, message), getattr(g, "request_id", ""))
        response = jsonify(body)
        response.status_code = status
        if status == 429:
            response.headers["Retry-After"] = error.get_response().headers.get("Retry-After", "60")
        return response

    @app.errorhandler(Exception)
    def internal_error(error: Exception):
        db.session.rollback()
        app.logger.error("request_failed request_id=%s error_type=%s", getattr(g, "request_id", ""), type(error).__name__)
        body, status = error_payload(
            ApiError(500, "internal_error", "Something went wrong. Please try again."),
            getattr(g, "request_id", str(uuid.uuid4())),
        )
        return jsonify(body), status

    from .api import api

    app.register_blueprint(api, url_prefix="/api/v1")
    from .cli import register_commands

    register_commands(app)
    logging.getLogger("openai").setLevel(logging.WARNING)
    return app
