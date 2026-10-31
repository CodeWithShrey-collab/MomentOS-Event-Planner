from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Environment settings, with only the project-root .env as a local fallback."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "testing", "production"] = "development"
    app_base_url: str = "http://127.0.0.1:5000"
    frontend_dist_dir: Path | None = None
    secret_key: SecretStr | None = None
    database_url: str | None = None

    ai_mode: Literal["demo", "live"] = "demo"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_reasoning_effort: Literal["low", "medium", "high"] = "low"
    openai_max_output_tokens: int = Field(default=3000, ge=700, le=8000)
    openai_timeout_seconds: float = Field(default=25.0, ge=3.0, le=60.0)
    ai_daily_request_limit: int = Field(default=20, ge=1, le=1000)
    ai_per_minute_limit: int = Field(default=5, ge=1, le=60)
    ai_input_usd_per_million: float = Field(default=0.10, ge=0)
    ai_cached_input_usd_per_million: float = Field(default=0.01, ge=0)
    ai_output_usd_per_million: float = Field(default=0.50, ge=0)
    ai_pricing_config_version: str = "openai-gpt-6-luna-standard-2026-10-31-v2"

    session_cookie_name: str = "momentos_session"
    session_cookie_secure: bool | None = None
    session_cookie_samesite: Literal["Lax", "Strict"] = "Lax"
    session_ttl_days: int = Field(default=30, ge=1, le=180)
    session_absolute_ttl_days: int = Field(default=180, ge=1, le=365)
    session_rotation_window_days: int = Field(default=7, ge=1, le=30)
    trusted_origins: str = "http://127.0.0.1:5000,http://localhost:5000,http://127.0.0.1:5173,http://localhost:5173"
    rate_limit_storage_uri: str = "memory://"
    # Set these only for the exact reverse proxy chain in front of this app.
    # Render documents Cloudflare and load balancers but does not guarantee a
    # fixed X-Forwarded-For hop count; deployment config leaves counts explicit.
    proxy_fix_x_for: int = Field(default=0, ge=0, le=3)
    proxy_fix_x_proto: int = Field(default=0, ge=0, le=2)
    proxy_fix_x_host: int = Field(default=0, ge=0, le=2)

    max_content_length: int = Field(default=262_144, ge=1024, le=1_048_576)
    max_description_chars: int = Field(default=12_000, ge=1, le=12_000)
    max_question_chars: int = Field(default=4_000, ge=1, le=4_000)
    max_page_size: int = Field(default=100, ge=1, le=100)
    max_tasks_per_event: int = Field(default=500, ge=1, le=500)
    max_scenarios: int = Field(default=3, ge=1, le=3)
    ripple_preview_ttl_minutes: int = Field(default=15, ge=1, le=60)
    idempotency_ttl_days: int = Field(default=7, ge=1, le=30)

    @field_validator("openai_model")
    @classmethod
    def require_exact_model(cls, value: str) -> str:
        if value != "gpt-6-luna":
            raise ValueError("OPENAI_MODEL must be exactly gpt-6-luna; model fallback is disabled")
        return value

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.session_absolute_ttl_days < self.session_ttl_days:
            raise ValueError("SESSION_ABSOLUTE_TTL_DAYS must be >= SESSION_TTL_DAYS")
        if self.app_env == "production":
            if not self.secret_key or len(self.secret_key.get_secret_value()) < 32:
                raise ValueError("Production requires SECRET_KEY with at least 32 characters")
            if not self.session_cookie_secure:
                raise ValueError("Production requires SESSION_COOKIE_SECURE=true")
            if self.session_cookie_samesite != "Lax":
                raise ValueError("Production requires SESSION_COOKIE_SAMESITE=Lax")
            if self.ai_mode != "live" or not self.openai_key or not self.openai_key.strip():
                raise ValueError("Production requires AI_MODE=live and an OPENAI_API_KEY")
            if self.openai_reasoning_effort != "low":
                raise ValueError("Production requires OPENAI_REASONING_EFFORT=low as the default")
            if not self.database_url or not self.database_uri.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires a PostgreSQL DATABASE_URL")
            redis_url = urlsplit(self.rate_limit_storage_uri)
            try:
                redis_port = redis_url.port
            except ValueError:
                redis_port = None
            if (
                redis_url.scheme != "rediss"
                or not redis_url.hostname
                or not redis_url.username
                or not redis_url.password
                or redis_port is None
            ):
                raise ValueError("Production requires a valid TLS Redis TCP URL in RATE_LIMIT_STORAGE_URI (rediss://)")
            # Flask-Limiter passes this URL to redis-py. Explicit query options
            # make both certificate-chain and hostname verification strict;
            # rediss:// alone does not enable hostname checks in the installed
            # redis-py client. Keep the endpoint and all unrelated query values.
            self.rate_limit_storage_uri = self._require_redis_tls_verification(self.rate_limit_storage_uri)
            if not self.proxy_fix_x_for or not self.proxy_fix_x_proto:
                raise ValueError("Production requires explicit trusted proxy counts for X-Forwarded-For and X-Forwarded-Proto")

            app_origin = self.app_base_url.rstrip("/")
            if not self._is_https_origin(app_origin):
                raise ValueError("Production requires APP_BASE_URL to be an HTTPS origin")
            origins = [part.strip().rstrip("/") for part in self.trusted_origins.split(",") if part.strip()]
            if any(not self._is_https_origin(origin) for origin in origins):
                raise ValueError("Production TRUSTED_ORIGINS must contain only HTTPS origins")
        return self

    @staticmethod
    def _require_redis_tls_verification(value: str) -> str:
        parsed = urlsplit(value)
        query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in {"ssl_cert_reqs", "ssl_check_hostname"}
        ]
        query.extend((("ssl_cert_reqs", "required"), ("ssl_check_hostname", "true")))
        return urlunsplit(parsed._replace(query=urlencode(query)))

    @staticmethod
    def _is_https_origin(value: str) -> bool:
        try:
            parsed = urlsplit(value)
            # Touch .port so malformed ports raise ValueError here.
            _ = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.is_production

    @property
    def database_uri(self) -> str:
        if self.database_url:
            if self.is_production:
                try:
                    url = make_url(self.database_url)
                    if url.drivername in {"postgres", "postgresql"}:
                        url = url.set(drivername="postgresql+psycopg")
                    if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
                        raise ValueError("invalid PostgreSQL address")
                    query = dict(url.query)
                    query["sslmode"] = "verify-full"
                    query.setdefault("connect_timeout", "10")
                    url = url.set(query=query)
                    return url.render_as_string(hide_password=False)
                except Exception:
                    raise ValueError("Production requires a valid PostgreSQL DATABASE_URL using psycopg") from None

            value = self.database_url
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+psycopg://", 1)
            if value.startswith("sqlite:///momentos.sqlite3"):
                return f"sqlite:///{(BACKEND_DIR / 'instance' / 'momentos.sqlite3').as_posix()}"
            return value
        return f"sqlite:///{(BACKEND_DIR / 'instance' / 'momentos.sqlite3').as_posix()}"

    @cached_property
    def trusted_origin_set(self) -> frozenset[str]:
        configured = {part.strip().rstrip("/") for part in self.trusted_origins.split(",") if part.strip()}
        configured.add(self.app_base_url.rstrip("/"))
        return frozenset(configured)

    @property
    def openai_key(self) -> str | None:
        return self.openai_api_key.get_secret_value() if self.openai_api_key else None


def load_settings(overrides: dict[str, object] | None = None) -> Settings:
    """Load settings with process environment and explicit project-root .env support."""
    return Settings(**(overrides or {}))
