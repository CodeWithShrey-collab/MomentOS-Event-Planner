from __future__ import annotations

from ipaddress import ip_address

from flask import current_app, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
migrate = Migrate()


def rate_limit_client_address() -> str:
    """Return a bounded rate-limit identity without trusting X-Forwarded-*.

    On the public Render topology, Cloudflare overwrites CF-Connecting-IP
    before forwarding to the Render web service. If that expected edge header
    is absent or malformed, fall back to the socket peer; this may coalesce
    callers behind the Render proxy but cannot be bypassed by rotating XFF.
    """
    settings = current_app.extensions.get("momentos_settings")
    if settings and settings.rate_limit_client_ip_source == "render_cf_connecting_ip":
        candidate = request.headers.get("CF-Connecting-IP", "").strip()
        if candidate and len(candidate) <= 45:
            try:
                return ip_address(candidate).compressed
            except ValueError:
                pass
    return get_remote_address() or "unknown"


limiter = Limiter(key_func=rate_limit_client_address, default_limits=[])
