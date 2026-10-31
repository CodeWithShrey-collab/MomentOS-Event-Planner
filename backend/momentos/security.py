from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from flask import current_app, g, make_response, request
from sqlalchemy import select

from .errors import ApiError
from .extensions import db


def now_utc() -> datetime:
    return datetime.now(UTC)


def utc_datetime(value: datetime) -> datetime:
    """Normalize database datetimes; SQLite drops tzinfo despite the schema."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_utc(value: datetime | None) -> str | None:
    return utc_datetime(value).isoformat().replace("+00:00", "Z") if value is not None else None


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_token_for(session) -> str:
    """Return a stable, secret-keyed CSRF token for this session generation."""
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    message = f"momentos-csrf:{session.id}:{session.schema_version}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def set_session_cookie(response, token: str | None, max_age: int = 0):
    settings = current_app.extensions["momentos_settings"]
    response.set_cookie(
        settings.session_cookie_name,
        token or "",
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return response


def live_session(required: bool = True):
    """Resolve session from hashed cookie token; ownership is never client supplied."""
    from .models import GuestSession

    settings = current_app.extensions["momentos_settings"]
    cookie = request.cookies.get(settings.session_cookie_name)
    session = None
    if cookie:
        session = db.session.scalar(
            select(GuestSession).where(GuestSession.token_hash == token_digest(cookie))
        )
    now = now_utc()
    if not session or session.revoked_at or utc_datetime(session.expires_at) <= now or utc_datetime(session.absolute_expires_at) <= now:
        if required:
            raise ApiError(401, "session_required", "A valid planning session is required.")
        return None
    g.session = session
    session.last_seen_at = now
    session.expires_at = min(now + timedelta(days=settings.session_ttl_days), utc_datetime(session.absolute_expires_at))
    return session


def rotate_if_near_expiry(session) -> tuple[str | None, str | None]:
    settings = current_app.extensions["momentos_settings"]
    if utc_datetime(session.expires_at) - now_utc() > timedelta(days=settings.session_rotation_window_days):
        return None, None
    new_session_token = new_token()
    session.token_hash = token_digest(new_session_token)
    session.schema_version += 1
    new_csrf_token = csrf_token_for(session)
    session.csrf_hash = token_digest(new_csrf_token)
    return new_session_token, new_csrf_token


def require_csrf() -> None:
    session = live_session(required=True)
    settings = current_app.extensions["momentos_settings"]
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(token_digest(supplied), session.csrf_hash):
        raise ApiError(403, "csrf_failed", "Refresh your session security token and try again.")
    origin = request.headers.get("Origin")
    if not origin and request.headers.get("Referer"):
        ref = urlsplit(request.headers["Referer"])
        origin = f"{ref.scheme}://{ref.netloc}"
    if not origin or origin.rstrip("/") not in settings.trusted_origin_set:
        raise ApiError(403, "origin_rejected", "This request origin is not allowed.")


def create_session_pair():
    from .models import GuestSession

    settings = current_app.extensions["momentos_settings"]
    session_token = new_token()
    session_id = str(uuid.uuid4())
    now = now_utc()
    session = GuestSession(
        id=session_id,
        token_hash=token_digest(session_token),
        csrf_hash="",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.session_ttl_days),
        absolute_expires_at=now + timedelta(days=settings.session_absolute_ttl_days),
        schema_version=1,
    )
    csrf_token = csrf_token_for(session)
    session.csrf_hash = token_digest(csrf_token)
    db.session.add(session)
    db.session.flush()
    return session, session_token, csrf_token


def owned_event(event_id):
    from .models import Event

    session = live_session(required=True)
    event = db.session.scalar(
        select(Event).where(
            Event.id == event_id,
            Event.owner_session_id == session.id,
            Event.deleted_at.is_(None),
        )
    )
    if not event:
        raise ApiError(404, "not_found", "The requested event was not found.")
    return event


def etag_for(event) -> str:
    version = str(event.current_plan_version_no) if event.current_plan_version_no is not None else "none"
    return f'"event:{event.id}:r{event.revision}:v{version}"'


def require_if_match(event) -> None:
    value = request.headers.get("If-Match")
    if not value:
        raise ApiError(428, "precondition_required", "Reload this event before saving changes.")
    if not hmac.compare_digest(value, etag_for(event)):
        raise ApiError(412, "stale_event_version", "This event changed elsewhere. Reload and review it.")


def api_response(data, status: int = 200, *, event=None):
    request_id = getattr(g, "request_id", "")
    response = make_response({"data": data, "request_id": request_id}, status)
    if event is not None:
        response.headers["ETag"] = etag_for(event)
    return response
