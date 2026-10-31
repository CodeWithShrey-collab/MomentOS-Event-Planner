from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, update

from ..domain import (
    calculate_budget,
    detect_schedule_conflicts,
    validate_task_dependencies,
)
from ..errors import ApiError
from ..extensions import db
from ..models import (
    BudgetCategory,
    BudgetItem,
    Event,
    EventDetails,
    EventPlanVersion,
    PlanChangeReceipt,
    Task,
    TaskDependency,
    Vendor,
    VendorQuote,
)
from ..security import iso_utc


def current_version(event: Event) -> EventPlanVersion | None:
    if event.current_plan_version_no is None:
        return None
    return db.session.scalar(select(EventPlanVersion).where(
        EventPlanVersion.event_id == event.id,
        EventPlanVersion.version_no == event.current_plan_version_no,
    ))


def event_json(event: Event, *, include_summary: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": event.id,
        "event_type": event.event_type,
        "title": event.title,
        "currency": event.currency,
        "budget_limit_minor": event.budget_limit_minor,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "timezone": event.timezone,
        "location_label": event.location_label,
        "draft_fields": event.draft_fields_json or {},
        "current_version_no": event.current_plan_version_no,
        "revision": event.revision,
        "created_at": iso_utc(event.created_at),
        "updated_at": iso_utc(event.updated_at),
    }
    if include_summary:
        version = current_version(event)
        result["summary"] = snapshot(event, version) if version else None
    return result


def snapshot(event: Event, version: EventPlanVersion | None = None) -> dict[str, Any]:
    version = version or current_version(event)
    if version is None:
        return {
            "event_id": event.id,
            "version_no": None,
            "revision": event.revision,
            "event_type": event.event_type,
            "title": event.title,
            "currency": event.currency,
            "budget_limit_minor": event.budget_limit_minor,
            "event_date": event.event_date.isoformat() if event.event_date else None,
            "timezone": event.timezone,
            "location_label": event.location_label,
            "guest_count": (event.draft_fields_json or {}).get("guest_count"),
            "venue_capacity": (event.draft_fields_json or {}).get("venue_capacity"),
            "seats_per_table": (event.draft_fields_json or {}).get("seats_per_table"),
            "invitation_unit": (event.draft_fields_json or {}).get("invitation_unit"),
            "preferences": (event.draft_fields_json or {}).get("preferences", {}),
            "constraints": (event.draft_fields_json or {}).get("constraints", {}),
            "budget_categories": [],
            "budget_items": [],
            "tasks": [],
            "task_dependencies": [],
            "vendors": [],
        }
    details = db.session.get(EventDetails, version.id)
    categories = db.session.scalars(select(BudgetCategory).where(BudgetCategory.event_version_id == version.id).order_by(BudgetCategory.sort_order, BudgetCategory.logical_id)).all()
    items = db.session.scalars(select(BudgetItem).where(BudgetItem.event_version_id == version.id).order_by(BudgetItem.logical_id)).all()
    tasks = db.session.scalars(select(Task).where(Task.event_version_id == version.id).order_by(Task.due_at, Task.logical_id)).all()
    dependencies = db.session.scalars(select(TaskDependency).where(TaskDependency.event_version_id == version.id).order_by(TaskDependency.task_id, TaskDependency.depends_on_task_id)).all()
    vendors = db.session.scalars(select(Vendor).where(Vendor.event_version_id == version.id).order_by(Vendor.logical_id)).all()
    quotes = db.session.scalars(select(VendorQuote).where(VendorQuote.event_version_id == version.id).order_by(VendorQuote.logical_id)).all()
    quote_map: dict[str, list[dict[str, Any]]] = {}
    for quote in quotes:
        quote_map.setdefault(quote.vendor_id, []).append({
            "id": quote.logical_id, "amount_minor": quote.amount_minor, "currency": quote.currency,
            "quote_date": quote.quote_date.isoformat() if quote.quote_date else None,
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            "scope_note": quote.scope_note, "source": quote.source, "status": quote.status,
        })
    return {
        "event_id": event.id,
        "version_no": version.version_no,
        "revision": event.revision,
        "event_type": version.event_type,
        "title": version.title,
        "currency": version.currency,
        "budget_limit_minor": details.budget_limit_minor if details else event.budget_limit_minor,
        "event_date": (details.event_date if details else event.event_date).isoformat() if (details.event_date if details else event.event_date) else None,
        "timezone": details.timezone if details else event.timezone,
        "location_label": details.location_label if details else event.location_label,
        "guest_count": details.guest_count if details else None,
        "venue_capacity": details.venue_capacity if details else None,
        "seats_per_table": details.seats_per_table if details else None,
        "invitation_unit": details.invitation_unit if details else None,
        "preferences": details.preferences_json or {} if details else {},
        "constraints": details.constraints_json or {} if details else {},
        "budget_categories": [{
            "logical_id": row.logical_id, "name": row.name, "planned_minor": row.planned_minor,
            "sort_order": row.sort_order, "source": row.source, "is_required": row.is_required,
        } for row in categories],
        "budget_items": [{
            "logical_id": row.logical_id, "category_id": row.category_id, "label": row.label,
            "quantity": str(row.quantity) if row.quantity is not None else None,
            "quantity_basis": row.quantity_basis,
            "unit_rate_minor": row.unit_rate_minor, "planned_minor": row.planned_minor,
            "actual_minor": row.actual_minor, "status": row.status, "source_note": row.source_note,
        } for row in items],
        "tasks": [{
            "logical_id": row.logical_id, "title": row.title, "description": row.description,
            "task_type": row.task_type, "status": row.status, "owner_label": row.owner_label,
            "due_at": iso_utc(row.due_at),
            "due_local_date": row.due_local_date.isoformat() if row.due_local_date else None,
            "phase": row.phase, "priority": row.priority, "source": row.source,
            "vendor_id": row.vendor_id, "completed_at": iso_utc(row.completed_at),
            "completion_source": row.completion_source,
            "completed_by_session_id": row.completed_by_session_id,
            "dependencies": [d.depends_on_task_id for d in dependencies if d.task_id == row.logical_id],
        } for row in tasks],
        "task_dependencies": [{"task_id": d.task_id, "depends_on_task_id": d.depends_on_task_id, "lag_minutes": d.lag_minutes} for d in dependencies],
        "vendors": [{
            "logical_id": row.logical_id, "category": row.category, "display_name": row.display_name,
            "contact_name": row.contact_name, "email": row.email, "phone": row.phone,
            "location_note": row.location_note, "status": row.status,
            "information_source": row.information_source, "notes": row.notes,
            "quotes": quote_map.get(row.logical_id, []),
        } for row in vendors],
    }


def budget_json(event: Event) -> dict[str, Any]:
    data = snapshot(event)
    calculated = calculate_budget(data)
    return {
        "currency": data["currency"],
        "budget_limit_minor": data["budget_limit_minor"],
        **calculated,
        "categories": data["budget_categories"],
        "items": data["budget_items"],
        "version_no": data["version_no"],
    }


def task_json(event: Event) -> dict[str, Any]:
    data = snapshot(event)
    dependency_report = validate_task_dependencies(data["tasks"], data["task_dependencies"])
    return {
        "items": data["tasks"],
        "dependencies": data["task_dependencies"],
        "topological_order": dependency_report.get("topological_order", []),
        "schedule_conflicts": detect_schedule_conflicts(data["tasks"], data["task_dependencies"]),
        "version_no": data["version_no"],
    }


def _uuid_value(value: Any = None) -> str:
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, AttributeError, TypeError):
            pass
    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class _PlanContext:
    """Validated event-level values shared by plan row builders."""

    brief: dict[str, Any]
    current_version_no: int | None
    event_type: str
    title: str
    currency: str
    budget_limit_minor: int | None
    guest_count: int | None
    timezone_name: str | None


def _validate_plan_structure(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ApiError(422, "validation_failed", "The plan must be a structured object.")
    required = {"event_brief", "concept", "budget_categories", "budget_items", "tasks", "dependencies", "vendor_categories", "ideas", "assumptions", "unknowns", "validation", "ai_status"}
    missing = required - set(plan)
    if missing:
        raise ApiError(422, "validation_failed", "The plan draft is missing required sections.", fields=[{"path": key, "code": "missing", "message": "This section is required."} for key in sorted(missing)])
    if len(plan.get("budget_categories", [])) > 30 or len(plan.get("budget_items", [])) > 500 or len(plan.get("tasks", [])) > 500 or len(plan.get("vendor_categories", [])) > 50:
        raise ApiError(422, "validation_failed", "The plan exceeds the supported number of planning rows.")
    for field in ("budget_categories", "budget_items", "tasks", "vendor_categories", "dependencies"):
        if not isinstance(plan.get(field), list):
            raise ApiError(422, "validation_failed", f"{field} must be a list.")
    if not isinstance(plan.get("concept"), dict):
        raise ApiError(422, "validation_failed", "The event concept must be an object.")
    if any(not isinstance(row, dict) for field in ("budget_categories", "budget_items", "tasks") for row in plan[field]):
        raise ApiError(422, "validation_failed", "Budget and task rows must be objects.")
    return plan


def _validate_plan_brief(
    event: Event,
    brief: dict[str, Any],
    current_version_no: int | None,
) -> _PlanContext:
    event_type = brief.get("event_type", event.event_type)
    title = brief.get("title", brief.get("event_name", event.title))
    currency = brief.get("currency", event.currency)
    if event_type != event.event_type or currency != event.currency:
        raise ApiError(422, "validation_failed", "The accepted plan must keep the event type and currency.")
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ApiError(422, "validation_failed", "The event title must contain 1 to 160 characters.")
    budget_limit = _nonnegative_optional(brief.get("budget_limit_minor", event.budget_limit_minor))
    guest_count = brief.get("guest_count")
    if guest_count is not None and (isinstance(guest_count, bool) or not isinstance(guest_count, int) or not 1 <= guest_count <= 100_000):
        raise ApiError(422, "validation_failed", "Guest count must be an integer between 1 and 100000.")
    for field, lower, upper in (("venue_capacity", 1, 100_000), ("seats_per_table", 1, 1000)):
        value = brief.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper):
            raise ApiError(422, "validation_failed", f"{field} must be an integer between {lower} and {upper}.")
    timezone_name = brief.get("timezone", event.timezone)
    if timezone_name:
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, TypeError) as exc:
            raise ApiError(422, "validation_failed", "Use a valid IANA time zone.") from exc
    return _PlanContext(
        brief=brief,
        current_version_no=current_version_no,
        event_type=event_type,
        title=title,
        currency=currency,
        budget_limit_minor=budget_limit,
        guest_count=guest_count,
        timezone_name=timezone_name,
    )


def _validate_plan_input(event: Event, plan: Any, base_version_no: int | None) -> _PlanContext:
    plan = _validate_plan_structure(plan)
    current_version_no = event.current_plan_version_no
    if base_version_no != current_version_no:
        raise ApiError(412, "stale_event_version", "This plan draft is based on an older event version.")
    brief = plan["event_brief"]
    if not isinstance(brief, dict):
        raise ApiError(422, "validation_failed", "The event brief must be an object.")
    return _validate_plan_brief(event, brief, current_version_no)


def _build_budget_categories(plan: dict[str, Any]) -> tuple[dict[str, str], list[BudgetCategory]]:
    category_ids: dict[str, str] = {}
    categories: list[BudgetCategory] = []
    for index, item in enumerate(plan["budget_categories"]):
        if not isinstance(item, dict):
            raise ApiError(422, "validation_failed", "Budget category rows must be objects.")
        category_id = _uuid_value(item.get("logical_id"))
        key = str(item.get("key", item.get("category_key", item.get("name", index))))
        if key in category_ids:
            raise ApiError(422, "validation_failed", "Budget category keys must be unique.")
        category_ids[key] = category_id
        categories.append(BudgetCategory(
            event_version_id="", logical_id=category_id, name=str(item.get("name") or key)[:120],
            planned_minor=_nonnegative_optional(item.get("planned_minor")), sort_order=_nonnegative(item.get("sort_order", index)),
            source=_source(item.get("source", plan.get("ai_status", "demo"))), is_required=bool(item.get("is_required", False)),
        ))
    return category_ids, categories


def _create_plan_version(
    event: Event,
    session_id: str,
    context: _PlanContext,
    *,
    change_kind: str,
    source_simulation_id: str | None,
    summary: str | None,
) -> EventPlanVersion:
    version = EventPlanVersion(
        id=str(uuid.uuid4()), event_id=event.id,
        version_no=(context.current_version_no or 0) + 1,
        base_version_no=context.current_version_no,
        change_kind=change_kind, event_type=context.event_type,
        title=context.title[:160], currency=context.currency,
        created_at=datetime.now(UTC), created_by_session_id=session_id,
        source_simulation_id=source_simulation_id, change_summary=summary,
    )
    db.session.add(version)
    db.session.flush()
    return version


def _persist_categories(version: EventPlanVersion, categories: list[BudgetCategory]) -> None:
    for category in categories:
        category.event_version_id = version.id
        db.session.add(category)
    db.session.flush()


def _build_event_details(event: Event, context: _PlanContext, version: EventPlanVersion) -> EventDetails:
    brief = context.brief
    return EventDetails(
        event_version_id=version.id,
        budget_limit_minor=context.budget_limit_minor,
        event_date=_parse_date(brief.get("event_date", event.event_date)),
        timezone=context.timezone_name,
        location_label=brief.get("location_label", event.location_label),
        guest_count=context.guest_count,
        guest_count_source="user" if context.guest_count is not None else None,
        venue_capacity=brief.get("venue_capacity"),
        venue_capacity_source="user" if brief.get("venue_capacity") is not None else None,
        seats_per_table=brief.get("seats_per_table"),
        invitation_unit=brief.get("invitation_unit"),
        accessibility_notes=brief.get("accessibility_notes"),
        preferences_json=_safe_json_object(brief.get("preferences", {}), "preferences"),
        constraints_json=_safe_json_object(brief.get("constraints", {}), "constraints"),
    )


def _build_budget_items(
    plan: dict[str, Any],
    category_ids: dict[str, str],
    categories: list[BudgetCategory],
    version: EventPlanVersion,
) -> list[BudgetItem]:
    known_category_ids = {category.logical_id for category in categories}
    items: list[BudgetItem] = []
    for row in plan["budget_items"]:
        key = str(row.get("category_key", row.get("category_id", "")))
        category_id = category_ids.get(key, str(row.get("category_id", "")))
        if category_id not in known_category_ids:
            raise ApiError(422, "validation_failed", "A budget item references an unknown category.")
        quantity = row.get("quantity")
        if quantity is not None:
            if isinstance(quantity, float):
                raise ApiError(422, "validation_failed", "Use a decimal string for fractional budget quantities.")
            try:
                quantity = Decimal(quantity)
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ApiError(422, "validation_failed", "Budget quantity must be a finite positive decimal.") from exc
            if not quantity.is_finite() or quantity <= 0 or quantity > Decimal(1000000) or -quantity.as_tuple().exponent > 3:
                raise ApiError(422, "validation_failed", "Budget quantity must be finite, positive, and use at most three decimal places.")
        items.append(BudgetItem(
            event_version_id=version.id, logical_id=_uuid_value(row.get("logical_id")),
            category_id=category_id, label=str(row.get("label") or row.get("name") or "Estimate")[:160],
            quantity=quantity, quantity_basis=row.get("quantity_basis"),
            unit_rate_minor=_nonnegative_optional(row.get("unit_rate_minor", row.get("rate_minor"))),
            planned_minor=_nonnegative(row.get("planned_minor", 0)), actual_minor=_nonnegative_optional(row.get("actual_minor")),
            status=_item_status(row.get("status", row.get("estimate_basis", "illustrative_estimate"))),
            source_note=str(row.get("source_note") or row.get("provenance") or "Illustrative planning assumption")[:600],
        ))
    return items


def _task_id_map(task_rows: list[dict[str, Any]]) -> dict[str, str]:
    task_ids: dict[str, str] = {}
    for row in task_rows:
        key = str(row.get("key", row.get("id", len(task_ids))))
        task_ids[key] = _uuid_value(row.get("logical_id"))
    return task_ids


def _build_tasks(
    task_rows: list[dict[str, Any]],
    task_ids: dict[str, str],
    version: EventPlanVersion,
    session_id: str,
    change_kind: str,
    ai_status: Any,
) -> tuple[list[Task], list[tuple[str, str, int]]]:
    tasks: list[Task] = []
    dependency_rows: list[tuple[str, str, int]] = []
    for index, row in enumerate(task_rows):
        # Snapshots persist the stable logical id rather than the draft-only key.
        # Use the same fallback as the task-id map above when cloning a saved plan.
        key = str(row.get("key", row.get("id", index)))
        logical_id = task_ids[key]
        status = row.get("status", "not_started")
        if status not in {"not_started", "in_progress", "blocked", "completed"}:
            raise ApiError(422, "validation_failed", "Unsupported task status.")
        if status == "completed" and change_kind == "initial_plan":
            # Accepted model drafts cannot assert that work already happened.
            status = "not_started"
        completed = status == "completed"
        if completed and row.get("completion_source") != "user":
            raise ApiError(422, "validation_failed", "A completed task needs explicit user completion provenance.")
        tasks.append(Task(
            event_version_id=version.id, logical_id=logical_id,
            title=str(row.get("title") or "Planning task")[:160], description=str(row.get("description") or row.get("rationale") or "")[:1200] or None,
            task_type=row.get("task_type", "task"), status=status, owner_label=row.get("owner_label"),
            due_at=_parse_datetime(row.get("due_at")), due_local_date=_parse_date(row.get("due_local_date")),
            phase=str(row.get("phase") or "before_event")[:80], priority=row.get("priority", "medium"),
            source=_source(row.get("source", ai_status)),
            vendor_id=row.get("vendor_id"),
            completion_source="user" if completed else None,
            completed_at=datetime.now(UTC) if completed else None,
            completed_by_session_id=session_id if completed else None,
        ))
        parents = row.get("depends_on_keys", row.get("dependencies", [])) or []
        for parent in parents:
            parent_id = task_ids.get(str(parent), str(parent))
            dependency_rows.append((logical_id, parent_id, 0))
    return tasks, dependency_rows


def _append_explicit_dependencies(
    plan: dict[str, Any],
    task_ids: dict[str, str],
    dependency_rows: list[tuple[str, str, int]],
) -> None:
    for dependency in plan.get("dependencies", []):
        if not isinstance(dependency, dict):
            raise ApiError(422, "validation_failed", "Dependency rows must be objects.")
        task_key = str(dependency.get("task_key", dependency.get("task_id", "")))
        parent_key = str(dependency.get("depends_on_key", dependency.get("depends_on_task_id", "")))
        task_id = task_ids.get(task_key, task_key)
        parent_id = task_ids.get(parent_key, parent_key)
        lag = _nonnegative(dependency.get("lag_minutes", 0))
        dependency_rows.append((task_id, parent_id, lag))


def _persist_task_graph(
    version: EventPlanVersion,
    tasks: list[Task],
    dependency_rows: list[tuple[str, str, int]],
) -> None:
    db.session.add_all(tasks)
    db.session.flush()
    task_graph = [{"logical_id": task.logical_id, "dependencies": [parent for task_id, parent, _ in dependency_rows if task_id == task.logical_id]} for task in tasks]
    dep_validation = validate_task_dependencies(task_graph)
    if not dep_validation.get("valid"):
        raise ApiError(422, "invalid_dependency_graph", "The task dependency graph is invalid.")
    unique_dependencies: dict[tuple[str, str], int] = {}
    for task_id, parent, lag in dependency_rows:
        key = (task_id, parent)
        unique_dependencies[key] = max(lag, unique_dependencies.get(key, 0))
    db.session.add_all([
        TaskDependency(event_version_id=version.id, task_id=task_id, depends_on_task_id=parent, lag_minutes=lag)
        for (task_id, parent), lag in sorted(unique_dependencies.items())
    ])


def _build_vendor(row: dict[str, Any], version: EventPlanVersion, vendor_id: str) -> Vendor:
    return Vendor(
        event_version_id=version.id, logical_id=vendor_id,
        category=str(row.get("key", row.get("category", row.get("name", "other"))))[:80],
        display_name=str(row.get("display_name") or "")[:160] or None,
        contact_name=str(row.get("contact_name") or "")[:120] or None,
        email=str(row.get("email") or "")[:254] or None,
        phone=str(row.get("phone") or "")[:40] or None,
        location_note=str(row.get("location_note") or "")[:240] or None,
        status=row.get("status", "to_find"),
        information_source="user_entered" if row.get("information_source") == "user_entered" or row.get("display_name") else "checklist_suggestion",
        notes=str(row.get("notes") or row.get("why") or row.get("rationale") or "")[:1200] or None,
    )


def _persist_vendor_quotes(
    row: dict[str, Any], version: EventPlanVersion, vendor_id: str, currency: str,
) -> None:
    for quote in row.get("quotes", []):
        if not isinstance(quote, dict):
            continue
        if quote.get("currency", currency) != currency:
            raise ApiError(422, "validation_failed", "Vendor quote currency must match the event currency.")
        db.session.add(VendorQuote(
            event_version_id=version.id, logical_id=_uuid_value(quote.get("logical_id") or quote.get("id")),
            vendor_id=vendor_id, amount_minor=_nonnegative(quote.get("amount_minor", 0)), currency=currency,
            quote_date=_parse_date(quote.get("quote_date")), valid_until=_parse_date(quote.get("valid_until")),
            scope_note=str(quote.get("scope_note") or "User-entered quotation")[:600],
            source="user_entered", status=quote.get("status", "received_by_user"),
        ))


def _build_vendors(plan: dict[str, Any], version: EventPlanVersion, currency: str) -> list[Vendor]:
    vendor_rows: list[Vendor] = []
    for raw_row in plan["vendor_categories"]:
        row = {"category": raw_row} if isinstance(raw_row, str) else raw_row
        vendor_id = _uuid_value(row.get("logical_id"))
        vendor_rows.append(_build_vendor(row, version, vendor_id))
        _persist_vendor_quotes(row, version, vendor_id, currency)
    return vendor_rows


def persist_plan(event: Event, session_id: str, plan: dict[str, Any], *, change_kind: str, base_version_no: int | None, source_simulation_id: str | None = None, summary: str | None = None, update_event: bool = True) -> EventPlanVersion:
    context = _validate_plan_input(event, plan, base_version_no)
    category_ids, categories = _build_budget_categories(plan)
    version = _create_plan_version(
        event,
        session_id,
        context,
        change_kind=change_kind,
        source_simulation_id=source_simulation_id,
        summary=summary,
    )
    _persist_categories(version, categories)

    detail = _build_event_details(event, context, version)
    db.session.add(detail)
    items = _build_budget_items(plan, category_ids, categories, version)
    db.session.add_all(items)
    db.session.flush()

    task_rows = plan["tasks"]
    task_ids = _task_id_map(task_rows)
    tasks, dependency_rows = _build_tasks(
        task_rows, task_ids, version, session_id, change_kind, plan.get("ai_status", "demo")
    )
    _append_explicit_dependencies(plan, task_ids, dependency_rows)
    _persist_task_graph(version, tasks, dependency_rows)

    vendor_rows = _build_vendors(plan, version, context.currency)
    db.session.add_all(vendor_rows)
    db.session.flush()

    db.session.add(PlanChangeReceipt(
        event_version_id=version.id, trigger_summary=summary or "Accepted event plan",
        changes_json=[], reason_trail_json=[], acknowledged_warning_codes_json=[],
    ))
    db.session.flush()
    if update_event:
        _publish_version(event, version, expected_revision=event.revision, detail=detail)
    return version


def clone_current_version(event: Event, session_id: str, *, change_kind: str, summary: str, apply: Callable[[dict[str, Any]], None] | None = None, source_simulation_id: str | None = None) -> EventPlanVersion:
    base = current_version(event)
    if base is None:
        raise ApiError(409, "domain_conflict", "Generate and confirm a plan before editing this section.")
    data = snapshot(event, base)
    if apply:
        apply(data)
    plan = _snapshot_to_plan(data)
    expected_revision = event.revision
    version = persist_plan(event, session_id, plan, change_kind=change_kind, base_version_no=base.version_no, source_simulation_id=source_simulation_id, summary=summary, update_event=False)
    _publish_version(event, version, expected_revision=expected_revision, detail=db.session.get(EventDetails, version.id))
    return version


def apply_ripple_snapshot(event: Event, session_id: str, data: dict[str, Any], *, summary: str, simulation_id: str | None = None) -> EventPlanVersion:
    plan = _snapshot_to_plan(data)
    expected_revision = event.revision
    version = persist_plan(event, session_id, plan, change_kind="ripple_commit", base_version_no=event.current_plan_version_no, source_simulation_id=simulation_id, summary=summary, update_event=False)
    _publish_version(event, version, expected_revision=expected_revision, detail=db.session.get(EventDetails, version.id))
    return version


def _publish_version(event: Event, version: EventPlanVersion, *, expected_revision: int, detail: EventDetails | None) -> None:
    statement = update(Event).where(
        Event.id == event.id,
        Event.owner_session_id == event.owner_session_id,
        Event.revision == expected_revision,
        Event.deleted_at.is_(None),
    )
    if version.base_version_no is None:
        statement = statement.where(Event.current_plan_version_no.is_(None))
    else:
        statement = statement.where(Event.current_plan_version_no == version.base_version_no)
    result = db.session.execute(statement.values(
        current_plan_version_no=version.version_no,
        revision=expected_revision + 1,
        event_type=version.event_type,
        title=version.title,
        currency=version.currency,
        budget_limit_minor=detail.budget_limit_minor if detail else event.budget_limit_minor,
        event_date=detail.event_date if detail else event.event_date,
        timezone=detail.timezone if detail else event.timezone,
        location_label=detail.location_label if detail else event.location_label,
        updated_at=datetime.now(UTC),
    ))
    if result.rowcount != 1:
        raise ApiError(412, "stale_event_version", "This event changed elsewhere. Reload and review it.")
    db.session.refresh(event)


def _snapshot_to_plan(data: dict[str, Any]) -> dict[str, Any]:
    brief_keys = ("event_type", "title", "currency", "budget_limit_minor", "event_date", "timezone", "location_label", "guest_count", "venue_capacity", "seats_per_table", "invitation_unit", "preferences", "constraints")
    return {
        "event_brief": {key: data.get(key) for key in brief_keys},
        "concept": {"title": data["title"], "description": data.get("change_summary", "Updated event plan"), "style": ""},
        "assumptions": [], "unknowns": [],
        "budget_categories": copy.deepcopy(data.get("budget_categories", [])),
        "budget_items": copy.deepcopy(data.get("budget_items", [])),
        "tasks": copy.deepcopy(data.get("tasks", [])),
        "dependencies": copy.deepcopy(data.get("task_dependencies", [])),
        "vendor_categories": copy.deepcopy(data.get("vendors", [])),
        "ideas": [], "validation": [], "ai_status": "user",
    }


def _source(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("mode", value.get("source"))
    if not isinstance(value, str):
        return "demo_assumption"
    if value in {"user", "user_input", "user_supplied"}:
        return "user"
    if value in {"accepted_ai_suggestion", "ai", "inference", "suggestion"}:
        return "accepted_ai_suggestion"
    return "demo_assumption"


def _safe_json_object(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 40:
        raise ApiError(422, "validation_failed", f"{field} must be a bounded object.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ApiError(422, "validation_failed", f"{field} contains unsupported values.") from exc
    if len(encoded) > 12_000:
        raise ApiError(422, "validation_failed", f"{field} is too large.")
    return value


def _item_status(value: Any) -> str:
    return value if value in {"illustrative_estimate", "user_estimate", "quoted_by_user", "confirmed_by_user", "paid_by_user"} else "illustrative_estimate"


def _nonnegative(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ApiError(422, "validation_failed", "Money values must be non-negative integer minor units.")
    return value


def _nonnegative_optional(value: Any) -> int | None:
    return None if value is None else _nonnegative(value)


def _parse_date(value: Any):
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat"):
        return value
    try:
        return datetime.fromisoformat(str(value)).date() if "T" in str(value) else datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(422, "validation_failed", "Dates must use ISO calendar format.") from exc


def _parse_datetime(value: Any):
    if value is None or value == "":
        return None
    if hasattr(value, "tzinfo"):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise ApiError(422, "validation_failed", "Task timestamps must use ISO-8601 format.") from exc
    if parsed.tzinfo is None:
        raise ApiError(422, "validation_failed", "Task timestamps must include a timezone offset.")
    return parsed.astimezone(UTC)


__all__ = ["apply_ripple_snapshot", "budget_json", "clone_current_version", "current_version", "event_json", "persist_plan", "snapshot", "task_json"]
