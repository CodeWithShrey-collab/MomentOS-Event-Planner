from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, current_app, g, jsonify, make_response, request
from pydantic import BaseModel, ValidationError
from sqlalchemy import inspect, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from . import domain
from .ai_provider import (
    AIIncomplete,
    AIOutputInvalid,
    AIProviderError,
    AIProviderRateLimit,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIRefused,
    OpenAIProvider,
    PricingConfig,
)
from .ai_schemas import (
    CommonEventContext,
    CopilotRequest,
    EventBrief,
    EventType,
    ExtractionRequest,
    MinimalEventContext,
    RippleSimulationInput,
    RippleValue,
    VENDOR_CATEGORY_ALLOWLIST,
)
from .api_schemas import (
    BudgetPatch,
    CopilotApiRequest,
    DependencyReplace,
    EventCreate,
    EventPatch,
    IntakeRequest,
    PlanCommit,
    PlanDraftRequest,
    QuoteCreate,
    RippleCancel,
    RippleCommit,
    RippleCreate,
    ScenarioCompare,
    TaskCreate,
    TaskPatch,
    VendorCreate,
    VendorPatch,
    iso,
)
from .errors import ApiError
from .extensions import db, limiter
from .models import (
    AIQuotaBucket,
    AIUsageRecord,
    BudgetCategory,
    BudgetItem,
    Event,
    EventDetails,
    EventPlanVersion,
    GuestSession,
    IdempotencyRecord,
    PlanChangeReceipt,
    RippleSimulation,
    ScenarioSimulation,
    Task,
    TaskDependency,
    Vendor,
    VendorQuote,
    utc_now,
)
from .security import (
    csrf_token_for,
    api_response,
    create_session_pair,
    etag_for,
    iso_utc,
    live_session,
    now_utc,
    owned_event,
    require_csrf,
    require_if_match,
    rotate_if_near_expiry,
    set_session_cookie,
    token_digest,
    utc_datetime,
)
from .services.idempotency import begin_idempotent_write, finish_idempotent_write
from .services.plans import (
    apply_ripple_snapshot,
    budget_json,
    clone_current_version,
    current_version,
    event_json,
    persist_plan,
    _safe_json_object,
    snapshot,
    task_json,
)


api = Blueprint("api", __name__)
AI_OPERATION_LIMIT = 20


def _json_body(model: type[BaseModel] | None = None) -> Any:
    if not request.is_json:
        raise ApiError(415, "unsupported_media_type", "Send this request as JSON.")
    value = request.get_json(silent=False)
    if model is None:
        if not isinstance(value, dict):
            raise ApiError(400, "invalid_json", "The JSON request body must be an object.")
        return value
    return model.model_validate(value)


def _success(data: Any, status: int = 200, *, event: Event | None = None, idem: IdempotencyRecord | None = None):
    body = {"data": data, "request_id": getattr(g, "request_id", "")}
    etag = etag_for(event) if event is not None else None
    finish_idempotent_write(idem, body=body, status=status, etag=etag)
    response = make_response(body, status)
    if etag:
        response.headers["ETag"] = etag
    return response


def _replay(value: tuple[dict[str, Any], int, str | None]):
    body, status, etag = value
    response = make_response(body, status)
    if etag:
        response.headers["ETag"] = etag
    return response


def _mutation(event: Event | None, route_scope: str):
    session = live_session()
    require_csrf()
    if event is not None:
        locked = db.session.scalar(select(Event).where(
            Event.id == event.id,
            Event.owner_session_id == session.id,
            Event.deleted_at.is_(None),
        ).with_for_update().execution_options(populate_existing=True))
        if locked is None:
            _not_found()
        event = locked
    row, replay = begin_idempotent_write(session_id=session.id, route_scope=route_scope, event_id=event.id if event else None)
    return session, row, replay


def _ai_idempotency(session: GuestSession, event: Event, route_scope: str):
    row, replay = begin_idempotent_write(
        session_id=session.id,
        route_scope=route_scope,
        event_id=event.id,
    )
    return row, replay


def _event_version(event: Event) -> EventPlanVersion:
    version = current_version(event)
    if version is None:
        raise ApiError(409, "domain_conflict", "Generate and confirm an event plan before using this workspace.")
    return version


def _not_found():
    raise ApiError(404, "not_found", "The requested event data was not found.")


def _live_provider():
    test_factory = current_app.extensions.get("momentos_ai_provider_factory")
    if test_factory is not None:
        return test_factory()
    settings = current_app.extensions["momentos_settings"]
    if settings.ai_mode != "live":
        return None
    if not settings.openai_key:
        raise ApiError(503, "ai_configuration_error", "Live AI is not configured for this application.")
    pricing = PricingConfig(
        version=settings.ai_pricing_config_version,
        input_usd_per_million_tokens=Decimal(str(settings.ai_input_usd_per_million)),
        cached_input_usd_per_million_tokens=Decimal(str(settings.ai_cached_input_usd_per_million)),
        output_usd_per_million_tokens=Decimal(str(settings.ai_output_usd_per_million)),
    )
    return OpenAIProvider(
        api_key=settings.openai_key,
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
        max_output_tokens=settings.openai_max_output_tokens,
        reasoning_effort=settings.openai_reasoning_effort,
        pricing=pricing,
    )


def _ai_status(provider: Any) -> dict[str, Any]:
    if getattr(provider, "provider_mode", None) == "mock":
        return {"mode": "mock", "generated_by": "Mock Responses API provider (no live OpenAI request)", "model": "gpt-6-luna"}
    return {"mode": "live", "generated_by": "OpenAI Responses API", "model": "gpt-6-luna"}


def _check_ai_quota(session: GuestSession) -> None:
    """Atomically reserve one per-session UTC-day AI attempt before calling the provider."""
    settings = current_app.extensions["momentos_settings"]
    now = now_utc()
    dialect = db.session.get_bind().dialect.name
    insert_statement = postgresql_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert_statement is None:
        raise ApiError(503, "service_unavailable", "AI quota storage is not available.")
    statement = insert_statement(AIQuotaBucket).values(
        session_id=session.id,
        quota_day=now.date(),
        reserved_count=1,
        created_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=[AIQuotaBucket.session_id, AIQuotaBucket.quota_day],
        set_={
            "reserved_count": AIQuotaBucket.reserved_count + 1,
            "updated_at": now,
        },
        where=AIQuotaBucket.reserved_count < settings.ai_daily_request_limit,
    )
    with db.session.begin_nested():
        reservation = db.session.execute(statement)
    if reservation.rowcount != 1:
        raise ApiError(429, "rate_limited", "This planning session has reached its daily AI request limit.")
    # The reservation must survive provider timeouts and process restarts.
    db.session.commit()


def _record_ai_usage(session: GuestSession, event: Event, operation: str, *, status: str, usage: Any = None) -> None:
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    amount_minor = None
    input_tokens = output_tokens = None
    latency = 0
    effort = current_app.extensions["momentos_settings"].openai_reasoning_effort
    pricing_version = None
    model = current_app.extensions["momentos_settings"].openai_model
    if usage is not None:
        model = usage.model
        effort = usage.reasoning_effort
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        latency = usage.elapsed_ms
        pricing_version = usage.pricing_version
        if usage.estimated_cost_usd is not None:
            amount_minor = int((usage.estimated_cost_usd * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    version_no = event.current_plan_version_no
    db.session.add(AIUsageRecord(
        request_id=request_id, session_id=session.id, event_id=event.id,
        plan_version_no=version_no, operation=operation, model_id=model,
        reasoning_effort=effort, status=status, input_tokens=input_tokens,
        output_tokens=output_tokens, estimated_cost_minor=amount_minor,
        pricing_config_version=pricing_version, latency_ms=max(0, int(latency)),
    ))


def _invoke_ai(
    session: GuestSession,
    event: Event,
    operation: str,
    call: Callable[[], Any],
    *,
    idem: IdempotencyRecord | None = None,
):
    _check_ai_quota(session)
    try:
        result = call()
    except AIProviderError as exc:
        status = {
            "ai_refused": "refusal", "ai_incomplete": "incomplete",
            "ai_output_invalid": "invalid_output", "ai_timeout": "timeout",
            "ai_rate_limited": "rate_limited", "ai_unavailable": "provider_error",
        }.get(exc.code, "provider_error")
        _record_ai_usage(session, event, operation, status=status)
        diagnostics = exc.diagnostics
        current_app.logger.warning(
            "ai_response_rejected request_id=%s provider_request_id=%s operation=%s model=%s failure_stage=%s response_status=%s incomplete_reason=%s refusal=%s input_tokens=%s output_tokens=%s total_tokens=%s validation_categories=%s validation_paths=%s",
            getattr(g, "request_id", ""), exc.request_id or "unknown", operation,
            current_app.extensions["momentos_settings"].openai_model,
            diagnostics.get("failure_stage", "provider_error"), diagnostics.get("response_status", "unknown"),
            diagnostics.get("incomplete_reason", "none"), diagnostics.get("refusal", False),
            diagnostics.get("input_tokens", "unknown"), diagnostics.get("output_tokens", "unknown"),
            diagnostics.get("total_tokens", "unknown"), diagnostics.get("validation_categories", []),
            diagnostics.get("validation_paths", []),
        )
        if idem is not None:
            db.session.delete(idem)
        # The failed provider attempt must count toward quota even though the
        # request returns a recoverable error response. Release the idempotency
        # key so the user can explicitly retry after seeing the failure.
        db.session.commit()
        codes = {
            "ai_timeout": "ai_timeout", "ai_refused": "ai_refused",
            "ai_incomplete": "ai_incomplete", "ai_output_invalid": "ai_output_invalid",
            "ai_rate_limited": "rate_limited", "ai_unavailable": "ai_provider_unavailable",
            "ai_configuration_error": "service_unavailable",
        }
        message = "GPT-6 Luna could not complete this request. Your event data was not changed."
        raise ApiError(exc.http_status, codes.get(exc.code, "ai_provider_unavailable"), message) from exc
    except Exception as exc:
        _record_ai_usage(session, event, operation, status="provider_error")
        if idem is not None:
            db.session.delete(idem)
        db.session.commit()
        current_app.logger.error(
            "ai_operation_failed request_id=%s operation=%s error_type=%s",
            getattr(g, "request_id", ""), operation, type(exc).__name__,
        )
        raise ApiError(502, "ai_provider_unavailable", "GPT-6 Luna could not complete this request. Your event data was not changed.") from None
    _record_ai_usage(session, event, operation, status="success", usage=result.usage)
    # The response cache and usage record commit together after the route has
    # validated and serialized the complete response.
    db.session.flush()
    return result.data


def _demo_plan(event: Event, brief: dict[str, Any]) -> dict[str, Any]:
    budget = brief.get("budget_limit_minor", event.budget_limit_minor)
    categories = [
        ("catering", "Food and refreshments", 3000),
        ("venue", "Venue and setup", 3400),
        ("decor", "Decor and florals", 1700),
        ("entertainment", "Entertainment", 1105),
        ("photography", "Photography", 1105),
        ("contingency", "Contingency", 1190),
    ]
    guest_count = brief.get("guest_count")
    catering_rate = 100_000  # ₹1,000 per guest, an explicit offline-demo assumption.
    catering_total = guest_count * catering_rate if guest_count is not None else None
    remainder = max(0, budget - catering_total) if budget is not None and catering_total is not None else (budget * 7000 // 10_000 if budget is not None else None)
    allocated = []
    for key, name, share in categories:
        if key == "catering":
            amount = catering_total if catering_total is not None else (budget * 3000 // 10_000 if budget is not None else None)
        else:
            amount = int((Decimal(remainder) * Decimal(share) / Decimal(10_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if remainder is not None else None
        allocated.append({"key": key, "name": name, "planned_minor": amount, "sort_order": len(allocated), "source": "demo_assumption", "is_required": key in {"catering", "venue"}, "share_basis_points": share})
    event_type = brief.get("event_type", event.event_type)
    display_type = event_type.title()
    title = brief.get("title", event.title)
    themes = {
        "wedding": ("A thoughtful celebration", "An elegant gathering shaped around the couple, their guests, and the moments they want to remember.", "refined celebration"),
        "birthday": ("A personal milestone", "A warm celebration with a clear rhythm from welcome to the shared moment at its heart.", "joyful and personal"),
        "community": ("A welcoming gathering", "An accessible community event with a simple program, clear roles, and room for neighbors to connect.", "inclusive and community-led"),
    }
    concept_title, description, style = themes.get(event_type, themes["community"])
    if guest_count:
        description += f" Planned for {guest_count} guests."
    tasks = [
        {"key": "confirm_venue", "title": "Confirm venue requirements", "description": "Check capacity, access, setup, and timing directly with the venue.", "task_type": "task", "status": "not_started", "priority": "high", "phase": "before_event", "source": "demo_assumption", "depends_on_keys": []},
        {"key": "confirm_catering", "title": "Review food and service needs", "description": "Document dietary needs and compare user-entered catering estimates.", "task_type": "task", "status": "not_started", "priority": "high", "phase": "before_event", "source": "demo_assumption", "depends_on_keys": ["confirm_venue"]},
        {"key": "send_invitations", "title": "Prepare the invitation list", "description": "Confirm whether invitations are counted by person or household.", "task_type": "task", "status": "not_started", "priority": "medium", "phase": "before_event", "source": "demo_assumption", "depends_on_keys": []},
        {"key": "event_day_run", "title": "Review event-day run of show", "description": "Assign arrival, welcome, activity, and close-out responsibilities.", "task_type": "milestone", "status": "not_started", "priority": "medium", "phase": "event_day", "source": "demo_assumption", "depends_on_keys": ["confirm_venue", "confirm_catering"]},
    ]
    vendors = [
        {"key": key, "category": key, "why": f"Illustrative {key.replace('_', ' ')} checklist category. Contact and quote details must be entered and verified by you."}
        for key in ("venue", "catering", "decor", "photography", "entertainment")
    ]
    return {
        "event_brief": {**brief, "event_type": event_type, "title": title, "currency": brief.get("currency", event.currency), "budget_limit_minor": budget},
        "concept": {"title": concept_title, "description": description, "style": style},
        "assumptions": ["Budget category amounts are illustrative demo allocations, not market quotations.", "15% of the non-catering remainder is left unallocated as a planning buffer."],
        "unknowns": ["Venue capacity", "Vendor availability and quotations", "Invitation unit"] if not brief.get("venue_capacity") else ["Vendor availability and quotations", "Invitation unit"],
        "budget_categories": allocated,
        "budget_items": ([{"label": "Catering per guest", "category_key": "catering", "quantity": guest_count,
                           "quantity_basis": "guest_count", "unit_rate_minor": catering_rate,
                           "planned_minor": catering_total, "status": "illustrative_estimate",
                           "source_note": "Offline demo assumption: ₹1,000 per guest; replace with user-entered estimates or quotations."}]
                         if guest_count is not None else []),
        "tasks": tasks,
        "dependencies": [],
        "vendor_categories": vendors,
        "ideas": [{"idea": f"Create one signature {display_type.lower()} moment that reflects the host's stated priorities.", "personalization_rationale": "The recommendation is a starting point and needs the user's preferences to personalize further.", "input_references": []}],
        "validation": [{"code": "offline_demo", "status": "illustrative", "message": "No OpenAI response was generated. Review and edit all assumptions."}],
        "ai_status": {"mode": "offline_demo", "generated_by": None, "label": "Offline demo plan"},
    }


def _event_detail_context(value: Any, field: str) -> dict[str, Any]:
    """Convert the concise AI/demo string-list contract to persisted JSON."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if isinstance(value, str):
        return {"items": [value]}
    if value is None:
        return {}
    raise ApiError(422, "validation_failed", f"{field} must be a list or object.")


def _blueprint_to_draft(event: Event, brief: EventBrief, blueprint: Any) -> dict[str, Any]:
    budget = brief.budget_limit_minor
    supplied_shares = [item.suggested_share_basis_points for item in blueprint.budget_categories if item.suggested_share_basis_points is not None]
    if sum(supplied_shares) > 10_000:
        current_app.logger.warning(
            "ai_response_rejected request_id=%s operation=generate_event_blueprint model=%s failure_stage=blueprint_transformation validation_categories=%s validation_paths=%s",
            getattr(g, "request_id", ""), current_app.extensions["momentos_settings"].openai_model,
            ["budget_share_exceeds_total"], ["budget_categories.suggested_share_basis_points"],
        )
        raise ApiError(422, "ai_output_invalid", "The generated budget allocation exceeds the event budget.")
    categories: list[dict[str, Any]] = []
    for index, item in enumerate(blueprint.budget_categories):
        amount = None
        if budget is not None and item.suggested_share_basis_points is not None:
            amount = budget * item.suggested_share_basis_points // 10_000
        categories.append({"key": item.key, "name": item.name, "planned_minor": amount,
                           "sort_order": index, "source": "accepted_ai_suggestion",
                           "is_required": item.priority.value == "high",
                           "share_basis_points": item.suggested_share_basis_points,
                           "rationale": item.rationale})
    items = []
    for item in blueprint.budget_items:
        if item.quantity is None or item.rate_minor is None:
            continue
        amount = domain.calculate_line_amount(item.quantity, item.rate_minor)
        items.append({"label": item.label, "category_key": item.category_key,
                      "quantity": item.quantity, "unit_rate_minor": item.rate_minor,
                      "quantity_basis": item.quantity_basis,
                      "planned_minor": amount,
                      "status": "illustrative_estimate" if item.estimate_basis == "illustrative" else "user_estimate",
                      "source_note": f"{item.estimate_basis}; {item.provenance.value}"})
    tasks = [{"key": task.key, "title": task.title, "description": task.rationale,
              "task_type": "task", "phase": task.phase.value, "priority": task.priority.value,
              "status": "not_started", "source": "accepted_ai_suggestion",
              "depends_on_keys": task.depends_on_keys, "relative_timing_suggestion": task.relative_timing_suggestion}
             for task in blueprint.tasks]
    vendors = [{"key": item.key, "category": item.key, "why": item.why,
                "follow_up_checklist": item.follow_up_checklist} for item in blueprint.vendor_categories]
    budget_calc = domain.calculate_budget({
        "budget_limit_minor": budget, "guest_count": brief.guest_count,
        # The provider-facing draft uses stable category keys. The pure budget
        # engine requires a row identifier, so supply the key only in this
        # temporary calculation view; persisted IDs are generated on commit.
        "budget_categories": [{**category, "logical_id": category["key"]} for category in categories],
        "budget_items": items,
    })
    schedule = domain.detect_schedule_conflicts(tasks)
    return {
        "event_brief": {"event_type": brief.event_type.value, "title": brief.model_dump(mode="json").get("title") or event.title,
                        "currency": brief.currency, "budget_limit_minor": budget,
                        "event_date": brief.event_date, "timezone": brief.model_dump(mode="json").get("timezone") or event.timezone,
                        "location_label": brief.location_label, "guest_count": brief.guest_count,
                        # EventDetails stores bounded JSON objects while the
                        # model contract deliberately uses compact string lists.
                        "preferences": {"items": brief.preferences},
                        "constraints": {"items": brief.constraints}},
        "concept": blueprint.concept.model_dump(mode="json"),
        "assumptions": blueprint.assumptions, "unknowns": blueprint.unknowns,
        "budget_categories": categories, "budget_items": items,
        "tasks": tasks, "dependencies": [], "vendor_categories": vendors,
        "ideas": [idea.model_dump(mode="json") for idea in blueprint.ideas],
        "validation": [{"kind": "budget", "result": budget_calc}, {"kind": "schedule", "conflicts": schedule}, *blueprint.warnings],
    }


def _explain_ripple_if_available(session: GuestSession, event: Event, result: dict[str, Any]) -> dict[str, Any]:
    settings = current_app.extensions["momentos_settings"]
    if settings.ai_mode != "live":
        return {"status": "offline_demo", "generated_by": None,
                "message": "OpenAI was not called in offline demo mode."}
    try:
        values = []
        for index, row in enumerate(result.get("changes", [])[:100]):
            before = row.get("before")
            after = row.get("after")
            values.append(RippleValue(
                result_id=f"change-{index}",
                label=f"{row.get('entity', 'event')} {row.get('field', 'value')}",
                before=before if isinstance(before, (str, int, Decimal)) or before is None else str(before),
                after=after if isinstance(after, (str, int, Decimal)) or after is None else str(after),
                unit=str(row.get("unit", "value")),
            ))
        model = RippleSimulationInput(
            values=values,
            rule_ids=[str(row.get("rule_id")) for row in result.get("causal_trail", result.get("causes", [])) if row.get("rule_id")],
            blockers=[str(row.get("message", row.get("code", "Planning blocker"))) for row in result.get("blockers", [])],
            warnings=[str(row.get("message", row.get("code", "Planning warning"))) for row in result.get("warnings", [])],
            unknowns=[str(row.get("message", row.get("code", "Unknown input"))) for row in result.get("unknowns", [])],
        )
        provider = _live_provider()
        answer = _invoke_ai(session, event, "explain_ripple_results", lambda: provider.explain_ripple_impact(model))
        return {"status": _ai_status(provider)["mode"], "model": "gpt-6-luna", "generated_by": _ai_status(provider)["generated_by"],
                "explanation": answer.model_dump(mode="json")}
    except ApiError as exc:
        # Deterministic simulation remains available when the explanation call fails.
        return {"status": "unavailable", "generated_by": None, "error_code": exc.code,
                "message": "GPT-6 Luna could not explain this preview. Deterministic results remain available."}


def _iso_cursor(value: str | None):
    if not value:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")
        timestamp, identifier = decoded.split("|", 1)
        return datetime.fromisoformat(timestamp), identifier
    except Exception as exc:
        raise ApiError(400, "invalid_request", "The event list cursor is invalid.") from exc


def _event_cursor(event: Event) -> str:
    raw = f"{event.updated_at.isoformat()}|{event.id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@api.get("/health/live")
def health_live():
    return _success({"status": "alive"})


@api.get("/health/ready")
def health_ready():
    settings = current_app.extensions["momentos_settings"]
    try:
        db.session.execute(text("SELECT 1"))
        present = set(inspect(db.engine).get_table_names())
        missing = set(db.metadata.tables) - present
        database_state = "ready" if not missing else "migrations_required"
    except Exception:
        db.session.rollback()
        database_state = "unavailable"
    rate_limit_state = "not_required"
    if settings.is_production:
        try:
            current_app.extensions["momentos_rate_limit_redis"].ping()
            rate_limit_state = "ready"
        except Exception:
            rate_limit_state = "unavailable"
    ai_state = "demo" if settings.ai_mode == "demo" else ("configured" if settings.openai_key else "not_configured")
    ready = (
        database_state == "ready"
        and rate_limit_state in {"ready", "not_required"}
        and (settings.ai_mode != "live" or bool(settings.openai_key))
    )
    response = _success({
        "status": "ready" if ready else "not_ready",
        "components": {"database": database_state, "rate_limit_store": rate_limit_state, "ai": ai_state},
    })
    if not ready:
        response.status_code = 503
    return response


@api.post("/session")
@limiter.limit("10 per hour")
def create_session():
    settings = current_app.extensions["momentos_settings"]
    existing = live_session(required=False)
    if existing:
        session = existing
        token = request.cookies.get(settings.session_cookie_name)
        rotated_token, rotated_csrf_token = rotate_if_near_expiry(session)
        if rotated_token:
            token = rotated_token
        csrf_token = rotated_csrf_token or csrf_token_for(session)
        session.csrf_hash = token_digest(csrf_token)
    else:
        session, token, csrf_token = create_session_pair()
    data = {"csrf_token": csrf_token, "expires_at": iso_utc(session.expires_at)}
    response = _success(data, 201)
    response.set_cookie(settings.session_cookie_name, token, max_age=max(0, int((utc_datetime(session.expires_at) - now_utc()).total_seconds())),
                        httponly=True, secure=settings.cookie_secure, samesite=settings.session_cookie_samesite, path="/")
    return response


@api.get("/session")
def get_session():
    session = live_session()
    settings = current_app.extensions["momentos_settings"]
    token = request.cookies.get(settings.session_cookie_name)
    new_session_token, rotated_csrf_token = rotate_if_near_expiry(session)
    if new_session_token:
        token = new_session_token
    csrf_token = rotated_csrf_token or csrf_token_for(session)
    session.csrf_hash = token_digest(csrf_token)
    response = _success({"authenticated": True, "expires_at": iso_utc(session.expires_at), "csrf_token": csrf_token})
    response.set_cookie(settings.session_cookie_name, token, max_age=max(0, int((utc_datetime(session.expires_at) - now_utc()).total_seconds())),
                        httponly=True, secure=settings.cookie_secure, samesite=settings.session_cookie_samesite, path="/")
    return response


@api.delete("/session")
def delete_session():
    require_csrf()
    session = g.session
    session.revoked_at = now_utc()
    response = make_response("", 204)
    settings = current_app.extensions["momentos_settings"]
    response.set_cookie(settings.session_cookie_name, "", max_age=0, httponly=True, secure=settings.cookie_secure,
                        samesite=settings.session_cookie_samesite, path="/")
    return response


@api.get("/events")
def list_events():
    session = live_session()
    settings = current_app.extensions["momentos_settings"]
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError as exc:
        raise ApiError(400, "invalid_request", "Page size must be an integer.") from exc
    if not 1 <= limit <= settings.max_page_size:
        raise ApiError(400, "invalid_request", f"Page size must be between 1 and {settings.max_page_size}.")
    stmt = select(Event).where(Event.owner_session_id == session.id, Event.deleted_at.is_(None))
    cursor = _iso_cursor(request.args.get("cursor"))
    if cursor:
        timestamp, identifier = cursor
        stmt = stmt.where(or_(Event.updated_at < timestamp, (Event.updated_at == timestamp) & (Event.id < identifier)))
    rows = db.session.scalars(stmt.order_by(Event.updated_at.desc(), Event.id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return _success({"items": [event_json(row) for row in rows], "next_cursor": _event_cursor(rows[-1]) if has_more and rows else None})


@api.post("/events")
@limiter.limit("30 per hour")
def create_event():
    session, idem, replay = _mutation(None, "POST:/events")
    if replay:
        return _replay(replay)
    payload = _json_body(EventCreate)
    if payload.timezone:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ApiError(422, "validation_failed", "Use a valid IANA time zone.") from exc
    now = now_utc()
    event = Event(
        owner_session_id=session.id,
        event_type=payload.event_type,
        title=payload.title,
        currency=payload.currency,
        budget_limit_minor=payload.budget_limit_minor,
        event_date=payload.event_date,
        timezone=payload.timezone,
        location_label=payload.location_label,
        revision=0,
        created_at=now,
        updated_at=now,
        draft_fields_json={"guest_count": payload.guest_count,
                           "preferences": _safe_json_object(payload.preferences, "preferences"),
                           "constraints": _safe_json_object(payload.constraints, "constraints")},
    )
    db.session.add(event)
    db.session.flush()
    return _success(event_json(event), 201, event=event, idem=idem)


@api.get("/events/<event_id>")
def get_event(event_id: str):
    event = owned_event(event_id)
    include_summary = request.args.get("include") == "summary"
    return _success(event_json(event, include_summary=include_summary), event=event)


@api.patch("/events/<event_id>")
def patch_event(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"PATCH:/events/{event_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(EventPatch)
    changes = payload.model_dump(exclude_unset=True)
    if "timezone" in changes and changes["timezone"]:
        try:
            ZoneInfo(changes["timezone"])
        except ZoneInfoNotFoundError as exc:
            raise ApiError(422, "validation_failed", "Use a valid IANA time zone.") from exc
    if event.current_plan_version_no is None:
        draft = dict(event.draft_fields_json or {})
        for key, value in changes.items():
            if key in {"guest_count", "preferences", "constraints"}:
                draft[key] = _safe_json_object(value, key) if key in {"preferences", "constraints"} else value
            else:
                setattr(event, key, value)
        event.draft_fields_json = draft
        event.revision += 1
        event.updated_at = now_utc()
    else:
        def apply(data):
            for key, value in changes.items():
                if key in {"guest_count", "venue_capacity", "seats_per_table", "invitation_unit", "preferences", "constraints"}:
                    data[key] = _safe_json_object(value, key) if key in {"preferences", "constraints"} else value
                else:
                    data[key] = iso(value) if isinstance(value, (date, datetime)) else value
        clone_current_version(event, session.id, change_kind="user_edit", summary="Updated event details", apply=apply)
    return _success(event_json(event), event=event, idem=idem)


@api.delete("/events/<event_id>")
def delete_event(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"DELETE:/events/{event_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    event.deleted_at = now_utc()
    event.revision += 1
    event.updated_at = now_utc()
    body = {"data": {"deleted": True}, "request_id": getattr(g, "request_id", "")}
    finish_idempotent_write(idem, body=body, status=204, etag=None)
    return make_response("", 204)


@api.post("/events/<event_id>/intake")
@limiter.limit("5 per minute")
def intake_event(event_id: str):
    event = owned_event(event_id)
    session = live_session()
    require_csrf()
    payload = _json_body(IntakeRequest)
    if current_app.extensions["momentos_settings"].ai_mode == "demo":
        known = dict(payload.known_fields)
        known.setdefault("event_type", event.event_type)
        if event.title:
            known.setdefault("title", event.title)
        if event.location_label:
            known.setdefault("location_label", event.location_label)
        if event.event_date:
            known.setdefault("event_date", event.event_date.isoformat())
        if event.budget_limit_minor is not None:
            known.setdefault("budget_limit_minor", event.budget_limit_minor)
        if event.draft_fields_json.get("guest_count"):
            known.setdefault("guest_count", event.draft_fields_json["guest_count"])
        return _success({"requirements": {"known_fields": known, "description_for_review": payload.description,
                                           "unparsed_description": payload.description},
                         "missing_questions": [field for field in ("event_date", "location_label", "guest_count", "budget_limit_minor") if field not in known],
                         "uncertainties": ["Offline demo did not extract facts from the description."],
                         "ai_status": {"mode": "offline_demo", "generated_by": None}})
    idem, replay = _ai_idempotency(session, event, f"POST:/events/{event_id}/intake")
    if replay:
        return _replay(replay)
    request_model = ExtractionRequest(description=payload.description, known_fields={str(k): str(v) for k, v in payload.known_fields.items()},
                                      event_type_hint=EventType(event.event_type))
    provider = _live_provider()
    result = _invoke_ai(session, event, "extract_event_requirements", lambda: provider.extract_event_requirements(request_model), idem=idem)
    return _success({"requirements": result.model_dump(mode="json"), "missing_questions": result.follow_up_questions,
                     "uncertainties": result.unknowns,
                     "ai_status": _ai_status(provider)}, idem=idem)


@api.post("/events/<event_id>/plan-drafts")
@limiter.limit("5 per minute")
def create_plan_draft(event_id: str):
    event = owned_event(event_id)
    session = live_session()
    require_csrf()
    payload = _json_body(PlanDraftRequest)
    current = snapshot(event)
    brief_json = {**current, **payload.brief}
    brief_json["event_type"] = event.event_type
    brief_json["currency"] = event.currency
    brief_json["title"] = payload.brief.get("title", event.title)
    if current_app.extensions["momentos_settings"].ai_mode == "demo":
        draft = _demo_plan(event, brief_json)
        fields = {"guest_count", "budget_limit_minor", "event_date", "timezone", "location_label", "preferences", "constraints", "venue_capacity", "seats_per_table", "invitation_unit"}
        overrides = {key: value for key, value in payload.brief.items() if key in fields}
        for key in ("preferences", "constraints"):
            if key in overrides:
                overrides[key] = _event_detail_context(overrides[key], key)
        draft["event_brief"].update(overrides)
        return _success(draft)
    idem, replay = _ai_idempotency(session, event, f"POST:/events/{event_id}/plan-drafts")
    if replay:
        return _replay(replay)
    def text_list(value):
        if isinstance(value, dict):
            return [f"{key}: {item}"[:1200] for key, item in list(value.items())[:25]]
        if isinstance(value, str):
            return [value]
        return value or []
    brief = EventBrief.model_validate({
        "event_type": event.event_type,
        "locale": payload.brief.get("locale", "en-IN"),
        "currency": event.currency,
        "event_date": iso(payload.brief.get("event_date")) if isinstance(payload.brief.get("event_date"), date) else payload.brief.get("event_date"),
        "location_label": payload.brief.get("location_label", event.location_label),
        "guest_count": payload.brief.get("guest_count", current.get("guest_count")),
        "budget_limit_minor": payload.brief.get("budget_limit_minor", event.budget_limit_minor),
        "preferences": text_list(payload.brief.get("preferences", [])),
        "constraints": text_list(payload.brief.get("constraints", [])),
        "known_facts": payload.brief.get("known_facts", []),
        "unknowns": payload.brief.get("unknowns", []),
        "approved_extracted_values": payload.brief.get("approved_extracted_values", {}),
        "concept_preference": payload.brief.get("concept_preference"),
        "requested_sections": payload.include,
    })
    provider = _live_provider()
    blueprint = _invoke_ai(session, event, "generate_event_blueprint", lambda: provider.generate_event_blueprint(brief), idem=idem)
    try:
        draft = _blueprint_to_draft(event, brief, blueprint)
    except ApiError:
        db.session.delete(idem)
        db.session.commit()
        raise
    draft["ai_status"] = _ai_status(provider)
    return _success(draft, idem=idem)


@api.post("/events/<event_id>/plan-commits")
def commit_plan(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/plan-commits")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(PlanCommit)
    if payload.base_version_no != event.current_plan_version_no:
        raise ApiError(412, "stale_event_version", "This plan draft is based on an older event version.")
    if any(isinstance(task, dict) and task.get("status") == "completed" for task in payload.plan.get("tasks", [])):
        raise ApiError(422, "validation_failed", "Mark task completion through the task checklist after the event plan is confirmed.")
    expected_revision = event.revision
    version = persist_plan(event, session.id, payload.plan, change_kind="initial_plan" if event.current_plan_version_no is None else "user_edit",
                           base_version_no=event.current_plan_version_no, summary="Confirmed event plan", update_event=False)
    from .services.plans import _publish_version
    _publish_version(event, version, expected_revision=expected_revision, detail=db.session.get(EventDetails, version.id))
    return _success({"event": event_json(event), "version_no": version.version_no}, 201 if version.version_no == 1 else 200, event=event, idem=idem)


@api.get("/events/<event_id>/budget")
def get_budget(event_id: str):
    event = owned_event(event_id)
    return _success(budget_json(event), event=event)


@api.patch("/events/<event_id>/budget")
def patch_budget(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"PATCH:/events/{event_id}/budget")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(BudgetPatch)
    _event_version(event)
    def apply(data):
        categories = data["budget_categories"]
        items = data["budget_items"]
        for change in payload.category_changes:
            logical_id = str(change.get("logical_id", change.get("id", "")))
            row = next((item for item in categories if item["logical_id"] == logical_id), None)
            if row is None:
                _not_found()
            for key in ("name", "planned_minor", "is_required", "sort_order"):
                if key in change:
                    row[key] = change[key]
        for change in payload.item_changes:
            logical_id = str(change.get("logical_id", change.get("id", "")))
            row = next((item for item in items if item["logical_id"] == logical_id), None)
            if row is None:
                _not_found()
            for key in ("label", "planned_minor", "actual_minor", "quantity", "unit_rate_minor", "status", "source_note"):
                if key in change:
                    row[key] = change[key]
        for category in payload.add_categories:
            row = category.model_dump(mode="json")
            row["logical_id"] = row.pop("logical_id", None) or str(uuid.uuid4())
            categories.append(row)
        for item in payload.add_items:
            row = item.model_dump(mode="json")
            row["logical_id"] = row.pop("logical_id", None) or str(uuid.uuid4())
            row["category_id"] = str(row["category_id"])
            items.append(row)
        remove = {str(item) for item in payload.remove_ids}
        if remove:
            dependent_category_ids = {item["category_id"] for item in items if item["category_id"] in remove}
            if dependent_category_ids:
                raise ApiError(409, "dependent_records_exist", "Remove or reassign budget items before removing their category.")
            data["budget_categories"] = [row for row in categories if row["logical_id"] not in remove]
            data["budget_items"] = [row for row in items if row["logical_id"] not in remove]
        for category in data["budget_categories"]:
            category["planned_minor"] = _minor_or_none(category.get("planned_minor"))
        for item in data["budget_items"]:
            item["planned_minor"] = _minor(item.get("planned_minor", 0))
            item["actual_minor"] = _minor_or_none(item.get("actual_minor"))
    clone_current_version(event, session.id, change_kind="user_edit", summary="Updated budget", apply=apply)
    return _success(budget_json(event), event=event, idem=idem)


@api.get("/events/<event_id>/tasks")
def get_tasks(event_id: str):
    event = owned_event(event_id)
    data = task_json(event)
    if request.args.get("status"):
        data["items"] = [item for item in data["items"] if item["status"] == request.args["status"]]
    for key, rowkey in (("from", "due_local_date"), ("to", "due_local_date")):
        if request.args.get(key):
            try:
                boundary = date.fromisoformat(request.args[key])
            except ValueError as exc:
                raise ApiError(400, "invalid_request", f"{key} must be an ISO date.") from exc
            data["items"] = [item for item in data["items"] if item.get(rowkey) and (date.fromisoformat(item[rowkey]) >= boundary if key == "from" else date.fromisoformat(item[rowkey]) <= boundary)]
    return _success(data, event=event)


@api.post("/events/<event_id>/tasks")
def create_task(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/tasks")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(TaskCreate)
    new_task_id = str(uuid.uuid4())
    def apply(data):
        logical_id = new_task_id
        task = payload.model_dump(mode="json", exclude={"depends_on_task_ids"})
        task.update({"logical_id": logical_id, "source": "user", "vendor_id": None,
                     "due_at": iso(payload.due_at), "due_local_date": iso(payload.due_local_date),
                     "dependencies": [str(item) for item in payload.depends_on_task_ids]})
        if payload.status == "completed":
            task["completion_source"] = "user"
        data["tasks"].append(task)
        data["task_dependencies"].extend({"task_id": logical_id, "depends_on_task_id": str(parent), "lag_minutes": 0} for parent in payload.depends_on_task_ids)
        report = domain.validate_task_dependencies(data["tasks"], data["task_dependencies"])
        if not report["valid"]:
            raise ApiError(422, "invalid_dependency_graph", "The task dependency graph is invalid.", fields=[{"path": row.get("path", "dependencies"), "code": row["code"], "message": row["message"]} for row in report["errors"]])
    clone_current_version(event, session.id, change_kind="user_edit", summary="Added planning task", apply=apply)
    created = next(item for item in task_json(event)["items"] if item["logical_id"] == new_task_id)
    return _success(created, 201, event=event, idem=idem)


@api.patch("/events/<event_id>/tasks/<task_id>")
def patch_task(event_id: str, task_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"PATCH:/events/{event_id}/tasks/{task_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(TaskPatch)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    def apply(data):
        row = next((item for item in data["tasks"] if item["logical_id"] == task_id), None)
        if row is None:
            _not_found()
        if "status" in changes and changes["status"] == "completed":
            row["completion_source"] = "user"
            row["completed_by_session_id"] = session.id
        for key, value in changes.items():
            row[key] = value
    clone_current_version(event, session.id, change_kind="user_edit", summary="Updated planning task", apply=apply)
    updated = next(item for item in task_json(event)["items"] if item["logical_id"] == task_id)
    return _success(updated, event=event, idem=idem)


@api.delete("/events/<event_id>/tasks/<task_id>")
def delete_task(event_id: str, task_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"DELETE:/events/{event_id}/tasks/{task_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    def apply(data):
        if not any(item["logical_id"] == task_id for item in data["tasks"]):
            _not_found()
        dependents = [item["task_id"] for item in data["task_dependencies"] if item["depends_on_task_id"] == task_id]
        if dependents:
            raise ApiError(409, "dependent_records_exist", "Other tasks depend on this task.", fields=[{"path": "dependent_task_ids", "code": "in_use", "message": ",".join(dependents)}])
        data["tasks"] = [item for item in data["tasks"] if item["logical_id"] != task_id]
        data["task_dependencies"] = [item for item in data["task_dependencies"] if item["task_id"] != task_id]
    clone_current_version(event, session.id, change_kind="user_edit", summary="Removed planning task", apply=apply)
    return _success({"deleted": True}, event=event, idem=idem)


@api.put("/events/<event_id>/tasks/<task_id>/dependencies")
def replace_dependencies(event_id: str, task_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"PUT:/events/{event_id}/tasks/{task_id}/dependencies")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(DependencyReplace)
    def apply(data):
        if not any(item["logical_id"] == task_id for item in data["tasks"]):
            _not_found()
        data["task_dependencies"] = [item for item in data["task_dependencies"] if item["task_id"] != task_id]
        data["task_dependencies"].extend({"task_id": task_id, "depends_on_task_id": str(parent), "lag_minutes": 0} for parent in payload.depends_on_task_ids)
        report = domain.validate_task_dependencies(data["tasks"], data["task_dependencies"])
        if not report["valid"]:
            raise ApiError(422, "invalid_dependency_graph", "Task dependencies must reference tasks in this version and contain no cycles.")
    clone_current_version(event, session.id, change_kind="user_edit", summary="Updated task dependencies", apply=apply)
    return _success(task_json(event), event=event, idem=idem)


def _minor(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ApiError(422, "validation_failed", "Money amounts must be non-negative integer minor units.")
    return value


def _minor_or_none(value: Any) -> int | None:
    return None if value is None else _minor(value)


@api.get("/events/<event_id>/vendors")
def get_vendors(event_id: str):
    event = owned_event(event_id)
    data = snapshot(event)
    vendors = data["vendors"]
    if request.args.get("category"):
        vendors = [row for row in vendors if row["category"] == request.args["category"]]
    if request.args.get("status"):
        vendors = [row for row in vendors if row["status"] == request.args["status"]]
    return _success({"items": vendors, "version_no": data["version_no"],
                     "illustrative_only": any(row["information_source"] == "checklist_suggestion" for row in vendors)}, event=event)


@api.post("/events/<event_id>/vendors")
def create_vendor(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/vendors")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(VendorCreate)
    vendor_id = str(uuid.uuid4())
    def apply(data):
        data["vendors"].append({
            "logical_id": vendor_id, "category": payload.category,
            "display_name": payload.display_name, "contact_name": payload.contact_name,
            "email": payload.email, "phone": payload.phone, "location_note": payload.location_note,
            "status": payload.status, "information_source": "user_entered", "notes": payload.notes, "quotes": [],
        })
    clone_current_version(event, session.id, change_kind="user_edit", summary="Added user-entered vendor", apply=apply)
    item = next(row for row in snapshot(event)["vendors"] if row["logical_id"] == vendor_id)
    return _success(item, 201, event=event, idem=idem)


@api.patch("/events/<event_id>/vendors/<vendor_id>")
def patch_vendor(event_id: str, vendor_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"PATCH:/events/{event_id}/vendors/{vendor_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(VendorPatch)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    def apply(data):
        row = next((item for item in data["vendors"] if item["logical_id"] == vendor_id), None)
        if row is None:
            _not_found()
        row.update(changes)
        row["information_source"] = "user_entered"
    clone_current_version(event, session.id, change_kind="user_edit", summary="Updated user-entered vendor", apply=apply)
    item = next(row for row in snapshot(event)["vendors"] if row["logical_id"] == vendor_id)
    return _success(item, event=event, idem=idem)


@api.delete("/events/<event_id>/vendors/<vendor_id>")
def delete_vendor(event_id: str, vendor_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"DELETE:/events/{event_id}/vendors/{vendor_id}")
    if replay:
        return _replay(replay)
    require_if_match(event)
    def apply(data):
        if not any(item["logical_id"] == vendor_id for item in data["vendors"]):
            _not_found()
        if any(item.get("vendor_id") == vendor_id for item in data["tasks"]):
            raise ApiError(409, "dependent_records_exist", "A planning task still refers to this vendor.")
        if any(row.get("logical_id") == vendor_id and row.get("quotes") for row in data["vendors"]):
            raise ApiError(409, "dependent_records_exist", "This vendor has saved quotations. Resolve them before removing the vendor.")
        data["vendors"] = [item for item in data["vendors"] if item["logical_id"] != vendor_id]
    clone_current_version(event, session.id, change_kind="user_edit", summary="Removed vendor record", apply=apply)
    return _success({"deleted": True}, event=event, idem=idem)


@api.post("/events/<event_id>/vendors/<vendor_id>/quotes")
def create_vendor_quote(event_id: str, vendor_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/vendors/{vendor_id}/quotes")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(QuoteCreate)
    if payload.currency != event.currency:
        raise ApiError(422, "validation_failed", "Quote currency must match the event currency.")
    quote_id = str(uuid.uuid4())
    def apply(data):
        vendor = next((item for item in data["vendors"] if item["logical_id"] == vendor_id), None)
        if vendor is None:
            _not_found()
        vendor.setdefault("quotes", []).append({
            "id": quote_id, "amount_minor": payload.amount_minor, "currency": payload.currency,
            "quote_date": iso(payload.quote_date), "valid_until": iso(payload.valid_until),
            "scope_note": payload.scope_note, "source": "user_entered", "status": "received_by_user",
        })
    clone_current_version(event, session.id, change_kind="user_edit", summary="Added user-entered vendor quotation", apply=apply)
    vendor = next(row for row in snapshot(event)["vendors"] if row["logical_id"] == vendor_id)
    quote = next(row for row in vendor["quotes"] if row["id"] == quote_id)
    return _success(quote, 201, event=event, idem=idem)


@api.post("/events/<event_id>/ripple-previews")
@limiter.limit("15 per minute")
def create_ripple_preview(event_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/ripple-previews")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(RippleCreate)
    version = _event_version(event)
    if payload.base_version_no != version.version_no:
        raise ApiError(412, "stale_event_version", "This Ripple request is based on an older plan version.")
    data = snapshot(event, version)
    patch_rows = [row.model_dump(mode="json") for row in payload.changes]
    try:
        result = domain.simulate_ripple(data, patch_rows, {"version": "momentos-ripple-rules-1"})
    except domain.DomainValidationError as exc:
        raise ApiError(422, "validation_failed", exc.message, fields=[{"path": exc.path or "changes", "code": exc.code, "message": exc.message}]) from exc
    now = now_utc()
    expires = now + timedelta(minutes=current_app.extensions["momentos_settings"].ripple_preview_ttl_minutes)
    simulation_id = str(uuid.uuid4())
    preview = {
        **result,
        "simulation_id": simulation_id,
        "status": "ready",
        "base_version_no": version.version_no,
        "base_revision": event.revision,
        "engine_version": domain.ENGINE_VERSION,
        "rule_config_version": "momentos-ripple-rules-1",
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    preview["ai_explanation"] = _explain_ripple_if_available(session, event, result)
    simulation = RippleSimulation(
        id=simulation_id, event_id=event.id, owner_session_id=session.id,
        base_version_no=version.version_no, base_revision=event.revision,
        engine_version=domain.ENGINE_VERSION,
        input_patch_json=result["normalized_changes"], preview_json=preview,
        preview_hash=result["preview_hash"], status="ready",
        blockers_json=result["blockers"], warnings_json=result["warnings"],
        expires_at=expires,
    )
    db.session.add(simulation)
    return _success(preview, 201, event=event, idem=idem)


@api.get("/events/<event_id>/ripple-previews/<simulation_id>")
def get_ripple_preview(event_id: str, simulation_id: str):
    event = owned_event(event_id)
    session = live_session()
    simulation = db.session.scalar(select(RippleSimulation).where(
        RippleSimulation.id == simulation_id,
        RippleSimulation.event_id == event.id,
        RippleSimulation.owner_session_id == session.id,
    ))
    if not simulation:
        _not_found()
    preview = dict(simulation.preview_json)
    if simulation.status == "ready" and utc_datetime(simulation.expires_at) <= now_utc():
        preview["status"] = "expired"
        preview["commit_allowed"] = False
    else:
        preview["status"] = simulation.status
    return _success(preview, event=event)


@api.post("/events/<event_id>/ripple-previews/<simulation_id>/commit")
def commit_ripple_preview(event_id: str, simulation_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/ripple-previews/{simulation_id}/commit")
    if replay:
        return _replay(replay)
    require_if_match(event)
    payload = _json_body(RippleCommit)
    simulation = db.session.scalar(select(RippleSimulation).where(
        RippleSimulation.id == simulation_id,
        RippleSimulation.event_id == event.id,
        RippleSimulation.owner_session_id == session.id,
    ))
    if not simulation:
        _not_found()
    if simulation.status != "ready":
        raise ApiError(409, "domain_conflict", "This Ripple preview is no longer available to commit.")
    if utc_datetime(simulation.expires_at) <= now_utc():
        raise ApiError(409, "domain_conflict", "This Ripple preview has expired. Create a fresh preview.")
    if event.revision != simulation.base_revision or event.current_plan_version_no != simulation.base_version_no:
        raise ApiError(412, "stale_simulation", "This event changed after the preview. Simulate the change again.")
    base_version = current_version(event)
    base_snapshot = snapshot(event, base_version)
    try:
        recomputed = domain.simulate_ripple(base_snapshot, simulation.input_patch_json,
                                            {"version": "momentos-ripple-rules-1", "engine_version": simulation.engine_version})
    except domain.DomainValidationError as exc:
        raise ApiError(412, "stale_simulation", "The saved preview can no longer be validated. Create a fresh preview.") from exc
    if recomputed["preview_hash"] != simulation.preview_hash:
        raise ApiError(412, "stale_simulation", "The deterministic result changed. Create a fresh preview.")
    if not recomputed["commit_allowed"]:
        raise ApiError(409, "hard_constraint_violation", "This change violates a hard planning constraint and cannot be confirmed.",
                       fields=[{"path": "blockers", "code": item.get("code", "blocked"), "message": item.get("message", "Resolve this issue before confirming.")} for item in recomputed["blockers"][:20]])
    required_warnings = {item.get("code") for item in recomputed["warnings"] if item.get("requires_acknowledgement")}
    if not required_warnings.issubset(set(payload.acknowledged_warning_codes)):
        raise ApiError(409, "domain_conflict", "Acknowledge the listed warnings before confirming this change.")
    candidate = domain.apply_changes(base_snapshot, simulation.input_patch_json)
    version = apply_ripple_snapshot(event, session.id, candidate, summary="Confirmed Ripple Engine change", simulation_id=simulation.id)
    receipt = db.session.get(PlanChangeReceipt, version.id)
    receipt.changes_json = recomputed["changes"]
    receipt.reason_trail_json = recomputed.get("causal_trail", recomputed.get("causes", []))
    receipt.acknowledged_warning_codes_json = payload.acknowledged_warning_codes
    simulation.status = "committed"
    simulation.committed_version_no = version.version_no
    simulation.commit_idempotency_key = request.headers["Idempotency-Key"].strip()
    simulation.committed_at = now_utc()
    return _success({"event": event_json(event), "version_no": version.version_no,
                     "receipt": {"event_version_id": version.id, "simulation_id": simulation.id,
                                 "changes": receipt.changes_json, "causal_trail": receipt.reason_trail_json,
                                 "acknowledged_warning_codes": receipt.acknowledged_warning_codes_json}},
                    event=event, idem=idem)


@api.post("/events/<event_id>/ripple-previews/<simulation_id>/cancel")
def cancel_ripple_preview(event_id: str, simulation_id: str):
    event = owned_event(event_id)
    session, idem, replay = _mutation(event, f"POST:/events/{event_id}/ripple-previews/{simulation_id}/cancel")
    if replay:
        return _replay(replay)
    require_if_match(event)
    _json_body(RippleCancel)
    simulation = db.session.scalar(select(RippleSimulation).where(
        RippleSimulation.id == simulation_id, RippleSimulation.event_id == event.id,
        RippleSimulation.owner_session_id == session.id,
    ))
    if not simulation:
        _not_found()
    if simulation.status != "ready":
        raise ApiError(409, "domain_conflict", "Only an unused Ripple preview can be cancelled.")
    simulation.status = "cancelled"
    return _success({"simulation_id": simulation.id, "status": "cancelled"}, event=event, idem=idem)


@api.post("/events/<event_id>/scenario-comparisons")
@limiter.limit("10 per minute")
def compare_scenarios(event_id: str):
    event = owned_event(event_id)
    live_session()
    require_csrf()
    payload = _json_body(ScenarioCompare)
    version = _event_version(event)
    if payload.base_version_no != version.version_no:
        raise ApiError(412, "stale_event_version", "Reload the event before comparing scenarios.")
    data = snapshot(event, version)
    results = []
    for scenario in payload.scenarios:
        try:
            result = domain.simulate_ripple(data, [change.model_dump(mode="json") for change in scenario.changes], {"version": "momentos-ripple-rules-1"})
        except domain.DomainValidationError as exc:
            raise ApiError(422, "validation_failed", exc.message) from exc
        results.append({"name": scenario.name, "budget_summary": result["budget_summary"],
                        "capacity_summary": result["capacity_summary"], "changes": result["changes"],
                        "warnings": result["warnings"], "blockers": result["blockers"],
                        "commit_allowed": result["commit_allowed"]})
    return _success({"base_version_no": version.version_no, "currency": event.currency, "scenarios": results}, event=event)


def _requested_savings_minor(question: str, currency: str) -> int | None:
    if currency != "INR":
        return None
    match = re.search(r"(?:₹\s*|\bINR\s*|\bRs\.?\s*|\brupees?\s+)([0-9][0-9,]*(?:\.[0-9]{1,2})?)", question, re.IGNORECASE)
    if not match:
        return None
    amount = Decimal(match.group(1).replace(",", ""))
    return int((amount * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _copilot_context(event: Event, sections: list[str], question: str) -> MinimalEventContext:
    data = snapshot(event)
    facts = []
    def fact(key, value):
        if value is not None:
            facts.append({"field": key, "value": str(value), "source": "user_input", "evidence": "Saved event planning data"})
    fact("budget_limit_minor", data["budget_limit_minor"])
    budget = domain.calculate_budget(data)
    requested_saving = _requested_savings_minor(question, event.currency) if "budget" in sections else None
    if requested_saving is not None:
        facts.append({
            "field": "requested_saving_minor",
            "value": str(requested_saving),
            "source": "user_input",
            "evidence": question[:300],
        })
    if "budget" in sections:
        fact("planned_total_minor", budget["planned_minor"])
        fact("remaining_minor", budget["remaining_minor"])
    tasks = [{"task_id": row["logical_id"], "title": row["title"],
              "status": "done" if row["status"] == "completed" else row["status"],
              "due_local_date": row["due_local_date"]}
             for row in data["tasks"]] if "tasks" in sections else []
    vendor_status = {
        "to_find": "needed",
        "contacted_by_user": "researching",
        "shortlisted_by_user": "researching",
        "selected_by_user": "selected",
        "declined_by_user": "needed",
    }
    vendors = [
        {
            "category_key": row["category"],
            "status": vendor_status.get(row["status"], "needed"),
            "confirmed_cost_minor": next(
                (quote["amount_minor"] for quote in row.get("quotes", [])
                 if quote.get("status") == "accepted_by_user" and quote.get("source") == "user_entered"),
                None,
            ),
        }
        for row in data["vendors"]
        if row["category"] in VENDOR_CATEGORY_ALLOWLIST
    ] if "vendors" in sections else []
    feasible = []
    if "budget" in sections:
        category_rows = {row["logical_id"]: row for row in data["budget_categories"]}
        protected_tokens: set[str] = set()
        for phrase in re.findall(r"\bwithout\s+(?:affecting|changing|reducing|cutting)\s+([^,.!?;]+)", question.casefold()):
            protected_tokens.update(token for token in re.findall(r"[a-z]+", phrase) if token not in {"the", "my", "our", "any", "event", "budget"})
        candidates = []
        categories_with_items = {item["category_id"] for item in data["budget_items"]}
        for item in data["budget_items"]:
            category = category_rows.get(item["category_id"], {"name": "Budget item", "is_required": False})
            if item["status"] not in {"illustrative_estimate", "user_estimate"} or item["planned_minor"] <= 0 or category.get("is_required"):
                continue
            terms = set(re.findall(r"[a-z]+", f"{category['name']} {item['label']}".casefold()))
            if protected_tokens & terms:
                continue
            current_spend = item.get("actual_minor") or 0
            available = max(0, item["planned_minor"] - current_spend)
            if available:
                candidates.append((item, category, available))
        for category in data["budget_categories"]:
            if category["logical_id"] in categories_with_items or category.get("is_required"):
                continue
            category_terms = set(re.findall(r"[a-z]+", category["name"].casefold()))
            if protected_tokens & category_terms:
                continue
            amount = category.get("planned_minor") or 0
            if amount > 0:
                candidates.append((
                    {"logical_id": category["logical_id"], "label": f"{category['name']} allocation"},
                    category,
                    amount,
                ))
        candidates.sort(key=lambda candidate: (-candidate[2], candidate[0]["logical_id"]))
        remaining_target = requested_saving
        for item, category, available in candidates[:20]:
            suggested_amount = available if remaining_target is None else min(available, remaining_target)
            if suggested_amount <= 0:
                break
            feasible.append({
                "opportunity_id": item["logical_id"],
                "label": f"Review {item['label']} in {category['name']}",
                "saving_minor": suggested_amount,
                "affected_categories": [category["name"]],
                "tradeoff": "A hypothetical reduction to an unconfirmed estimate. Confirm scope and cost with the supplier, then edit and re-simulate the saved plan.",
                "preserved_constraints": ["User-requested protected category"] if protected_tokens else [],
            })
            if remaining_target is not None:
                remaining_target -= suggested_amount
    return MinimalEventContext.model_validate({
        "event_type": event.event_type, "event_title": event.title,
        "event_date": data["event_date"], "location_label": data["location_label"],
        "guest_count": data["guest_count"], "currency": event.currency,
        "budget_limit_minor": data["budget_limit_minor"], "facts": facts,
        "task_statuses": tasks, "vendor_categories": vendors, "feasible_modifications": feasible[:20],
    })


def _budget_adjustment_analysis(context: MinimalEventContext) -> dict[str, Any]:
    requested = next((int(item.value) for item in context.facts if item.field == "requested_saving_minor"), None)
    candidate_total = sum(item.saving_minor for item in context.feasible_modifications)
    return {
        "currency": context.currency,
        "requested_saving_minor": requested,
        "candidate_reduction_total_minor": candidate_total,
        "remaining_requested_minor": max(0, requested - candidate_total) if requested is not None else None,
        "feasible_modifications": [item.model_dump(mode="json") for item in context.feasible_modifications],
        "basis": "unconfirmed_estimates_only",
        "saved": False,
    }


@api.post("/events/<event_id>/copilot")
@limiter.limit("10 per minute")
def copilot(event_id: str):
    event = owned_event(event_id)
    session = live_session()
    require_csrf()
    payload = _json_body(CopilotApiRequest)
    context = _copilot_context(event, payload.context_sections, payload.question)
    if current_app.extensions["momentos_settings"].ai_mode == "demo":
        return _success({"answer": "This is an offline demo response; OpenAI was not called. Review the saved event data and verify all estimates with the people or suppliers involved.",
                         "known_references": [item.field for item in context.facts],
                         "unknowns": ["Vendor quotations and availability are not verified."],
                         "budget_analysis": _budget_adjustment_analysis(context),
                         "suggestions": [], "needs_user_confirmation": False,
                         "ai_status": {"mode": "offline_demo", "generated_by": None}})
    idem, replay = _ai_idempotency(session, event, f"POST:/events/{event_id}/copilot")
    if replay:
        return _replay(replay)
    scope = "tradeoff" if any(term in payload.question.lower() for term in ("save", "reduce", "trade", "without affecting", "cheaper")) else "brief"
    copilot_request = CopilotRequest(question=payload.question, event_context=context,
                                     locale="en-IN", response_scope=scope)
    provider = _live_provider()
    result = _invoke_ai(session, event, "answer_event_question", lambda: provider.answer_event_question(copilot_request), idem=idem)
    return _success({
        **result.model_dump(mode="json"),
        "budget_analysis": _budget_adjustment_analysis(context),
        "ai_status": _ai_status(provider),
    }, idem=idem)
