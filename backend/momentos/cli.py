"""Safe, manually invoked maintenance commands for MomentOS."""

from __future__ import annotations

import time

import click
from flask import current_app
from sqlalchemy import text

from .extensions import db


def _verify_production_dependencies(database_check, redis_check, *, sleep=time.sleep) -> str | None:
    """Run bounded, idempotent connectivity probes without returning details."""
    last_error = None
    for attempt in range(3):
        try:
            database_check()
            redis_check()
            return None
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                sleep(2)
    return type(last_error).__name__ if last_error else "ConnectionError"

from .ai_provider import (
    AIProviderError,
    AIProviderRateLimit,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIRefused,
    MODEL_ID,
    OpenAIProvider,
)


def register_commands(app) -> None:
    @app.cli.command("production-preflight")
    def production_preflight() -> None:
        """Verify the configured production database and shared Redis store."""
        settings = current_app.extensions["momentos_settings"]
        if not settings.is_production:
            click.echo("Production preflight requires APP_ENV=production.", err=True)
            raise click.exceptions.Exit(2)
        redis_client = current_app.extensions["momentos_rate_limit_redis"]

        def database_check():
            try:
                db.session.execute(text("SELECT 1"))
            except Exception:
                db.session.rollback()
                raise

        def redis_check():
            redis_client.ping()

        error_type = _verify_production_dependencies(
            database_check,
            redis_check,
        )
        if error_type:
            # Deliberately omit exception text: drivers may include endpoint data.
            click.echo(f"Production dependency preflight failed ({error_type}).", err=True)
            raise click.exceptions.Exit(1)
        click.echo("Production dependency preflight passed (database and TLS Redis reachable).")

    @app.cli.command("openai-smoke")
    def openai_smoke() -> None:
        """Verify GPT-6 Luna access with one low-effort, 128-token request."""
        settings = current_app.extensions["momentos_settings"]
        if settings.ai_mode != "live":
            click.echo("OpenAI smoke test not run: set AI_MODE=live.", err=True)
            raise click.exceptions.Exit(2)
        if not settings.openai_key:
            click.echo("OpenAI smoke test not run: OPENAI_API_KEY is not configured.", err=True)
            raise click.exceptions.Exit(2)
        if settings.openai_model != MODEL_ID:
            click.echo("OpenAI smoke test not run: OPENAI_MODEL must be gpt-6-luna.", err=True)
            raise click.exceptions.Exit(2)

        provider = OpenAIProvider(
            api_key=settings.openai_key,
            model=settings.openai_model,
            timeout_seconds=min(settings.openai_timeout_seconds, 15.0),
            max_output_tokens=settings.openai_max_output_tokens,
            reasoning_effort="low",
        )
        try:
            check = provider.connectivity_check()
        except AIProviderTimeout:
            click.echo("OpenAI smoke test failed: request timed out; no retry was attempted.", err=True)
            raise click.exceptions.Exit(1)
        except AIProviderRateLimit:
            click.echo("OpenAI smoke test failed: provider rate limit; no retry was attempted.", err=True)
            raise click.exceptions.Exit(1)
        except AIProviderUnavailable:
            click.echo("OpenAI smoke test failed: provider or gpt-6-luna access is unavailable; details suppressed.", err=True)
            raise click.exceptions.Exit(1)
        except AIRefused:
            click.echo("OpenAI smoke test: API/model responded, but the request was refused; no response content shown.", err=True)
            raise click.exceptions.Exit(1)
        except AIProviderError:
            click.echo("OpenAI smoke test failed: configuration or provider error; details suppressed.", err=True)
            raise click.exceptions.Exit(1)
        except Exception:
            click.echo("OpenAI smoke test failed: unexpected provider error; details suppressed.", err=True)
            raise click.exceptions.Exit(1) from None

        usage = check
        tokens = (
            f"input={usage.input_tokens if usage.input_tokens is not None else 'unavailable'}, "
            f"output={usage.output_tokens if usage.output_tokens is not None else 'unavailable'}, "
            f"total={usage.total_tokens if usage.total_tokens is not None else 'unavailable'}"
        )
        if usage.status == "incomplete":
            if usage.incomplete_reason == "max_output_tokens":
                click.echo(f"OpenAI API accepted the request; gpt-6-luna was accessible. Response incomplete at the 128-token output cap (reasoning may have consumed the budget); visible response not confirmed. Tokens: {tokens}. No retry.")
            else:
                click.echo(f"OpenAI API accepted the request; gpt-6-luna was accessible. Response incomplete (reason suppressed); visible response not confirmed. Tokens: {tokens}. No retry.")
            raise click.exceptions.Exit(1)
        if usage.has_visible_output:
            click.echo(f"OpenAI API accepted the request; gpt-6-luna returned a completed response with visible output. Tokens: {tokens}.")
        else:
            click.echo(f"OpenAI API accepted the request; gpt-6-luna completed without visible output. A visible response was not confirmed. Tokens: {tokens}.")
