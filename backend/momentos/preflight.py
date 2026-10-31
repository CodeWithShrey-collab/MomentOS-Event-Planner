"""Bounded dependency checks with safe, dependency-specific diagnostics."""

from __future__ import annotations

import re
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Callable, Literal


Dependency = Literal["DATABASE", "REDIS"]


@dataclass(frozen=True)
class PreflightFailure:
    dependency: Dependency
    category: str
    sqlstate: str | None = None

    @property
    def diagnostic(self) -> str:
        line = f"PREFLIGHT_{self.dependency}_{self.category}"
        if self.sqlstate:
            line += f" sqlstate={self.sqlstate}"
        return line


def _exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    """Return wrapped driver errors without formatting them for logs."""
    pending = [error]
    seen: set[int] = set()
    chain: list[BaseException] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(current)
        for wrapped in (
            getattr(current, "orig", None),
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
        ):
            if isinstance(wrapped, BaseException):
                pending.append(wrapped)
    return tuple(chain)


def _safe_sqlstate(chain: tuple[BaseException, ...]) -> str | None:
    for error in chain:
        for attribute in ("sqlstate", "pgcode"):
            value = getattr(error, attribute, None)
            if isinstance(value, str) and re.fullmatch(r"[0-9A-Z]{5}", value.upper()):
                return value.upper()
    return None


def _error_text(chain: tuple[BaseException, ...]) -> str:
    # Used only for matching known categories in memory. Never return or log it:
    # database and Redis driver messages can contain hostnames or user names.
    messages: list[str] = []
    for error in chain:
        try:
            messages.append(str(error).lower()[:4096])
        except Exception:
            continue
    return " ".join(messages)


def classify_preflight_error(error: BaseException, dependency: Dependency) -> PreflightFailure:
    """Map driver errors to an allowlisted category, never to raw text."""
    chain = _exception_chain(error)
    sqlstate = _safe_sqlstate(chain) if dependency == "DATABASE" else None
    text = _error_text(chain)
    type_names = {type(item).__name__.lower() for item in chain}

    if dependency == "DATABASE":
        if sqlstate and sqlstate.startswith("28"):
            category = "AUTH_FAILED"
        elif sqlstate == "3D000" or re.search(r"\bdatabase\b.*\bdoes not exist\b", text):
            category = "DATABASE_NOT_FOUND"
        elif isinstance(error, socket.gaierror) or any(
            marker in text
            for marker in (
                "could not translate host name",
                "name or service not known",
                "temporary failure in name resolution",
                "nodename nor servname provided",
                "no such host",
                "getaddrinfo",
            )
        ):
            category = "DNS_FAILED"
        elif isinstance(error, (ssl.SSLError, ssl.CertificateError)) or any(
            marker in text
            for marker in (
                "ssl error",
                "ssl syscall",
                "tls alert",
                "certificate verify failed",
                "certificate validation failed",
                "root certificate",
                "server certificate",
                "hostname mismatch",
                "sslmode",
            )
        ):
            category = "TLS_FAILED"
        elif isinstance(error, (TimeoutError, socket.timeout)) or any(
            marker in text
            for marker in ("timeout expired", "connection timed out", "operation timed out", "timed out")
        ):
            category = "TIMEOUT"
        elif any(
            marker in text
            for marker in (
                "password authentication failed",
                "authentication failed",
                "no password supplied",
                "role does not exist",
            )
        ):
            category = "AUTH_FAILED"
        elif any(
            marker in text
            for marker in (
                "connection refused",
                "network is unreachable",
                "no route to host",
                "connection reset by peer",
                "could not connect to server",
                "server closed the connection",
            )
        ):
            category = "TCP_FAILED"
        else:
            category = "CONNECTION_FAILED"
    elif dependency == "REDIS":
        if isinstance(error, (ssl.SSLError, ssl.CertificateError)) or any(
            marker in text for marker in ("certificate verify failed", "ssl:", "tls alert", "hostname mismatch")
        ):
            category = "TLS_FAILED"
        elif isinstance(error, (TimeoutError, socket.timeout)) or "timeout" in text or "timed out" in text:
            category = "TIMEOUT"
        elif "authenticationerror" in type_names or any(
            marker in text for marker in ("noauth", "wrongpass", "authentication required", "invalid username-password")
        ):
            category = "AUTH_FAILED"
        elif isinstance(error, socket.gaierror) or any(
            marker in text
            for marker in ("name or service not known", "temporary failure in name resolution", "getaddrinfo", "no such host")
        ):
            category = "DNS_FAILED"
        else:
            category = "CONNECTION_FAILED"
    else:
        raise ValueError("Unknown preflight dependency")

    return PreflightFailure(dependency, category, sqlstate)


def verify_dependency(
    check: Callable[[], object],
    dependency: Dependency,
    *,
    attempts: int = 3,
    retry_delay_seconds: float = 2,
    sleep: Callable[[float], object] = time.sleep,
) -> PreflightFailure | None:
    """Run one idempotent dependency probe with bounded retries."""
    failure: PreflightFailure | None = None
    for attempt in range(attempts):
        try:
            check()
            return None
        except Exception as error:
            failure = classify_preflight_error(error, dependency)
            if attempt + 1 < attempts:
                sleep(retry_delay_seconds)
    return failure
