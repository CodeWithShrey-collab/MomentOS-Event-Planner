"""Safe dependency classification and Render startup ordering tests."""

from __future__ import annotations

import socket
import ssl
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos.preflight import classify_preflight_error, verify_dependency  # noqa: E402


class DriverError(Exception):
    def __init__(self, message: str, sqlstate: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    ("dependency", "error", "expected"),
    [
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("could not translate host name 'private-db.invalid'")),
            "PREFLIGHT_DATABASE_DNS_FAILED",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("root certificate file '/private/root.crt' does not exist")),
            "PREFLIGHT_DATABASE_TLS_FAILED",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("connection timed out")),
            "PREFLIGHT_DATABASE_TIMEOUT",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("password authentication failed for user 'private-user'", "28P01")),
            "PREFLIGHT_DATABASE_AUTH_FAILED sqlstate=28P01",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("database 'private-db' does not exist", "3D000")),
            "PREFLIGHT_DATABASE_DATABASE_NOT_FOUND sqlstate=3D000",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("connection refused")),
            "PREFLIGHT_DATABASE_TCP_FAILED",
        ),
        (
            "DATABASE",
            OperationalError("SELECT 1", {}, DriverError("unclassified driver failure")),
            "PREFLIGHT_DATABASE_CONNECTION_FAILED",
        ),
        (
            "DATABASE",
            ssl.SSLCertVerificationError("certificate verify failed: private-host"),
            "PREFLIGHT_DATABASE_TLS_FAILED",
        ),
        (
            "DATABASE",
            socket.gaierror(socket.EAI_NONAME, "private host not found"),
            "PREFLIGHT_DATABASE_DNS_FAILED",
        ),
        (
            "REDIS",
            ssl.SSLCertVerificationError("certificate verify failed: private-host"),
            "PREFLIGHT_REDIS_TLS_FAILED",
        ),
        (
            "REDIS",
            TimeoutError("timed out connecting to private-host"),
            "PREFLIGHT_REDIS_TIMEOUT",
        ),
        (
            "REDIS",
            type("AuthenticationError", (Exception,), {})("WRONGPASS private-user"),
            "PREFLIGHT_REDIS_AUTH_FAILED",
        ),
        (
            "REDIS",
            socket.gaierror(socket.EAI_NONAME, "private host not found"),
            "PREFLIGHT_REDIS_DNS_FAILED",
        ),
        (
            "REDIS",
            ConnectionError("connection refused at private-host"),
            "PREFLIGHT_REDIS_CONNECTION_FAILED",
        ),
    ],
)
def test_preflight_classifier_emits_only_allowlisted_diagnostics(dependency, error, expected):
    failure = classify_preflight_error(error, dependency)

    assert failure.diagnostic == expected
    assert "private" not in failure.diagnostic
    assert "password" not in failure.diagnostic
    assert "postgres" not in failure.diagnostic
    assert "redis://" not in failure.diagnostic


def test_preflight_classifies_nested_timeout_and_preserves_only_sqlstate():
    error = OperationalError(
        "SELECT 1",
        {},
        DriverError("connection timed out for private-host, password=private-secret", "08001"),
    )

    failure = classify_preflight_error(error, "DATABASE")

    assert failure.diagnostic == "PREFLIGHT_DATABASE_TIMEOUT sqlstate=08001"
    assert "private-host" not in failure.diagnostic
    assert "private-secret" not in failure.diagnostic


def test_verify_dependency_retries_safely_and_stops_on_final_category():
    calls = {"check": 0, "sleep": []}

    def unavailable():
        calls["check"] += 1
        raise TimeoutError("private endpoint timed out")

    failure = verify_dependency(
        unavailable,
        "REDIS",
        sleep=lambda delay: calls["sleep"].append(delay),
    )

    assert failure is not None
    assert failure.diagnostic == "PREFLIGHT_REDIS_TIMEOUT"
    assert calls == {"check": 3, "sleep": [2, 2]}


def test_free_render_startup_script_is_fail_closed_and_orders_migrations_before_gunicorn():
    script = (PROJECT_ROOT / "backend" / "start-free-render.sh").read_text(encoding="utf-8")
    preflight = script.index("production-preflight")
    migration = script.index("db upgrade")
    server = script.index("exec gunicorn")

    assert "set -eu" in script
    assert preflight < migration < server
    assert "db.create_all" not in script
