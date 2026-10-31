from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from flask import current_app, request
from sqlalchemy import select

from ..errors import ApiError
from ..extensions import db
from ..models import IdempotencyRecord
from ..security import now_utc, utc_datetime


def begin_idempotent_write(*, session_id: str, route_scope: str, event_id: str | None = None) -> tuple[IdempotencyRecord | None, tuple[dict[str, Any], int, str | None] | None]:
    """Reserve or replay one bounded mutation using a canonical body digest."""
    key = request.headers.get("Idempotency-Key", "").strip()
    if not (16 <= len(key) <= 128) or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ApiError(400, "invalid_idempotency_key", "Send an Idempotency-Key between 16 and 128 visible characters.")
    body = request.get_json(silent=True) or {}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    settings = current_app.extensions["momentos_settings"]
    now = now_utc()
    existing = db.session.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.session_id == session_id,
        IdempotencyRecord.route_scope == route_scope,
        IdempotencyRecord.idempotency_key == key,
    ))
    if existing and utc_datetime(existing.expires_at) <= now:
        db.session.delete(existing)
        db.session.flush()
        existing = None
    if existing:
        if existing.event_id != event_id or existing.request_digest != digest:
            raise ApiError(409, "idempotency_conflict", "This idempotency key was already used for a different request.")
        if existing.state != "completed" or existing.response_json is None or existing.response_status is None:
            raise ApiError(409, "domain_conflict", "This request is already being processed. Retry after it completes.")
        body_json = existing.response_json
        return None, (body_json["body"], existing.response_status, body_json.get("etag"))

    row = IdempotencyRecord(
        session_id=session_id,
        event_id=event_id,
        route_scope=route_scope,
        idempotency_key=key,
        request_digest=digest,
        state="pending",
        created_at=now,
        expires_at=now + timedelta(days=settings.idempotency_ttl_days),
    )
    db.session.add(row)
    db.session.flush()
    return row, None


def finish_idempotent_write(row: IdempotencyRecord | None, *, body: dict[str, Any], status: int, etag: str | None = None) -> None:
    if row is None:
        return
    row.state = "completed"
    row.response_status = status
    row.response_json = {"body": body, "etag": etag}
