"""Pure, deterministic MomentOS planning calculations.

The functions in this module accept ordinary Python mappings/sequences and return
JSON-safe mappings. They do not read clocks, databases, environment variables,
network services, or global mutable state. Monetary amounts are integer minor
units; Decimal is used only when a configured fractional quantity is multiplied
by an integer minor-unit rate.

Snapshot convention (aliases are accepted at this boundary):

* Event fields live at the top level: ``guest_count``,
  ``budget_limit_minor``, ``venue_capacity``, ``seats_per_table``, ``currency``,
  ``event_id``, ``version_no`` and ``revision``.
* Categories are in ``budget_categories`` (or ``categories``); line items in
  ``budget_items`` (or ``items``). Per-guest category assumptions use the
  explicit ``rate_per_guest_minor`` field.
* Tasks are in ``tasks``. Dependencies may be on each task as ``dependencies``
  or supplied as ``task_dependencies`` rows with ``task_id`` and
  ``depends_on_task_id``.

This is a domain boundary, not an API schema. Callers must perform their own
Pydantic validation and persistence/ownership checks.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence


ENGINE_VERSION = "1.0.0"
MAX_DATABASE_INTEGER = 2_147_483_647
MAX_EVENT_GUESTS = 100_000
MAX_SEATS_PER_TABLE = 1_000
_EVENT_FIELDS = {
    "guest_count",
    "budget_limit_minor",
    "venue_capacity",
    "seats_per_table",
    "event_date",
}
_BUDGET_ITEM_FIELDS = {"unit_rate_minor", "planned_minor", "quantity"}
_CATEGORY_FIELDS = {"planned_minor", "rate_per_guest_minor"}
_TASK_FIELDS = {"due_at", "due_local_date"}
_VENDOR_STATUSES = {
    "to_find",
    "contacted_by_user",
    "shortlisted_by_user",
    "selected_by_user",
    "declined_by_user",
    # Frontend/demo aliases are accepted at the domain boundary.
    "contacted",
    "shortlisted",
    "selected",
    "declined",
}


class DomainValidationError(ValueError):
    """A stable, input-safe validation error raised by a pure domain helper."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _rows(value: Any, path: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DomainValidationError("invalid_collection", "Expected a list of records.", path=path)
    result: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise DomainValidationError(
                "invalid_record", "Expected each record to be an object.", path=f"{path}[{index}]"
            )
        result.append(row)
    return result


def _identifier(row: Mapping[str, Any]) -> str | None:
    value = _first(row, "logical_id", "id", "logicalId")
    return str(value) if value is not None else None


def _integer(value: Any, *, path: str, minimum: int = 0, maximum: int | None = None, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainValidationError("invalid_integer", "Expected an integer value.", path=path)
    if value < minimum:
        raise DomainValidationError("out_of_range", f"Value must be at least {minimum}.", path=path)
    if maximum is not None and value > maximum:
        raise DomainValidationError("out_of_range", f"Value must be at most {maximum}.", path=path)
    return value


def _minor(value: Any, *, path: str, maximum: int = MAX_DATABASE_INTEGER, nullable: bool = False) -> int | None:
    return _integer(value, path=path, minimum=0, maximum=maximum, nullable=nullable)


def _quantity_decimal(value: Any, *, path: str, maximum: Decimal | None = Decimal("1000000"), nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise DomainValidationError(
            "invalid_quantity", "Use an integer, decimal string, or Decimal quantity; floats are not accepted.", path=path
        )
    try:
        quantity = Decimal(value) if isinstance(value, (int, str, Decimal)) else None
    except (InvalidOperation, ValueError):
        quantity = None
    if quantity is None or not quantity.is_finite() or quantity < 0:
        raise DomainValidationError("invalid_quantity", "Quantity must be finite and non-negative.", path=path)
    if maximum is not None and quantity > maximum:
        raise DomainValidationError("out_of_range", f"Quantity must be at most {maximum}.", path=path)
    return quantity


def calculate_line_amount(quantity: int | str | Decimal, unit_rate_minor: int) -> int:
    """Return quantity × minor-unit rate, rounded half-up once at line total.

    ``quantity`` may be fractional only as an exact integer/string/Decimal; float
    input is rejected so binary floating-point cannot affect currency.
    """

    amount_rate = _minor(unit_rate_minor, path="unit_rate_minor")
    qty = _quantity_decimal(quantity, path="quantity")
    assert amount_rate is not None and qty is not None
    return int((qty * Decimal(amount_rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _category_rows(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _rows(_first(snapshot, "budget_categories", "categories", default=[]), "budget_categories")


def _item_rows(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _rows(_first(snapshot, "budget_items", "items", default=[]), "budget_items")


def calculate_budget(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Compute authoritative planned/actual totals and category summaries.

    Items are authoritative for a category whenever that category has one or
    more items. A category-level amount is used only when it has no items. An
    explicit per-guest category rate derives its planned amount from the
    snapshot guest count; a missing guest count/rate remains unknown.
    """

    categories = _category_rows(snapshot)
    items = _item_rows(snapshot)
    guest_count = _first(snapshot, "guest_count")
    if guest_count is not None:
        guest_count = _integer(guest_count, path="guest_count", minimum=1, maximum=MAX_EVENT_GUESTS)

    items_by_category: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for index, item in enumerate(items):
        category_id = _first(item, "category_id", "categoryId")
        if category_id is not None:
            items_by_category[str(category_id)].append(item)
        _minor(_first(item, "planned_minor", "plannedMinor"), path=f"budget_items[{index}].planned_minor")
        _minor(_first(item, "actual_minor", "actualMinor"), path=f"budget_items[{index}].actual_minor", nullable=True)

    categorized_ids = {_identifier(category) for category in categories}
    categorized_ids.discard(None)
    planned_by_category: dict[str, int | None] = {}
    actual_by_category: dict[str, int] = {}
    category_results: list[dict[str, Any]] = []
    accounted_item_ids: set[int] = set()

    for index, category in enumerate(categories):
        category_id = _identifier(category)
        if category_id is None:
            raise DomainValidationError("missing_id", "Budget category is missing its logical ID.", path=f"budget_categories[{index}]")
        child_items = items_by_category.get(category_id, [])
        if child_items:
            category_planned = sum(int(_first(item, "planned_minor", "plannedMinor", default=0)) for item in child_items)
            category_actual = sum(int(_first(item, "actual_minor", "actualMinor", default=0) or 0) for item in child_items)
            for item in child_items:
                accounted_item_ids.add(id(item))
            amount_source = "budget_items"
        else:
            rate = _first(category, "rate_per_guest_minor", "ratePerGuestMinor")
            if rate is not None and guest_count is not None:
                rate = _minor(rate, path=f"budget_categories[{index}].rate_per_guest_minor")
                assert rate is not None
                category_planned = calculate_line_amount(guest_count, rate)
                amount_source = "per_guest_rate"
            elif rate is not None:
                category_planned = None
                amount_source = "needs_guest_count"
            else:
                planned = _first(category, "planned_minor", "plannedMinor")
                category_planned = _minor(planned, path=f"budget_categories[{index}].planned_minor", nullable=True)
                amount_source = "category_amount" if planned is not None else "unknown"
            actual_value = _first(category, "actual_minor", "actualMinor")
            category_actual = int(_minor(actual_value, path=f"budget_categories[{index}].actual_minor", nullable=True) or 0)

        planned_by_category[category_id] = category_planned
        actual_by_category[category_id] = category_actual
        category_results.append(
            {
                "category_id": category_id,
                "name": _first(category, "name", "label", default=category_id),
                "planned_minor": category_planned,
                "actual_minor": category_actual,
                "amount_source": amount_source,
            }
        )

    # Include line items that do not have a category row rather than dropping
    # their explicit amounts from the event total.
    uncategorized_planned = 0
    uncategorized_actual = 0
    for item in items:
        if id(item) not in accounted_item_ids and str(_first(item, "category_id", "categoryId", default="")) not in categorized_ids:
            uncategorized_planned += int(_first(item, "planned_minor", "plannedMinor", default=0))
            uncategorized_actual += int(_first(item, "actual_minor", "actualMinor", default=0) or 0)

    unknown_category_ids = sorted(category_id for category_id, amount in planned_by_category.items() if amount is None)
    known_planned_total = sum(amount for amount in planned_by_category.values() if amount is not None) + uncategorized_planned
    planned_total = None if unknown_category_ids else known_planned_total
    actual_total = sum(actual_by_category.values()) + uncategorized_actual
    limit_raw = _first(snapshot, "budget_limit_minor", "budgetLimitMinor")
    limit = _minor(limit_raw, path="budget_limit_minor", nullable=True)
    variance = planned_total - limit if limit is not None and planned_total is not None else None
    return {
        "currency": _first(snapshot, "currency", default="INR"),
        "budget_limit_minor": limit,
        "planned_minor": planned_total,
        "known_planned_minor": known_planned_total,
        "planned_complete": not unknown_category_ids,
        "unknown_category_ids": unknown_category_ids,
        "actual_minor": actual_total,
        "remaining_minor": limit - planned_total if limit is not None and planned_total is not None else None,
        "variance_minor": variance,
        "over_budget_minor": max(variance, 0) if variance is not None else None,
        "categories": category_results,
    }


def _dependency_edges(
    tasks: Sequence[Mapping[str, Any]], dependencies: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[str]] | None = None
) -> list[tuple[str, str, int]]:
    """Return edges as (predecessor, successor, lag_minutes)."""

    edges: list[tuple[str, str, int]] = []
    for index, task in enumerate(tasks):
        task_id = _identifier(task)
        if task_id is None:
            raise DomainValidationError("missing_task_id", "Task is missing its logical ID.", path=f"tasks[{index}]")
        for dependency in _first(task, "dependencies", "depends_on_task_ids", default=[]) or []:
            if isinstance(dependency, Mapping):
                predecessor = _first(dependency, "depends_on_task_id", "task_id", "id")
                lag = _first(dependency, "lag_minutes", default=0)
            else:
                predecessor = dependency
                lag = 0
            if predecessor is None:
                raise DomainValidationError("missing_dependency_id", "Dependency is missing a task ID.", path=f"tasks[{index}].dependencies")
            lag_value = _integer(lag, path=f"tasks[{index}].dependencies.lag_minutes")
            assert lag_value is not None
            edges.append((str(predecessor), task_id, lag_value))

    if dependencies is not None:
        if isinstance(dependencies, Mapping):
            dependency_rows: list[Mapping[str, Any]] = []
            for successor, predecessor_ids in dependencies.items():
                for predecessor in predecessor_ids:
                    dependency_rows.append({"task_id": successor, "depends_on_task_id": predecessor})
        else:
            dependency_rows = list(_rows(dependencies, "task_dependencies"))
        for index, row in enumerate(dependency_rows):
            predecessor = _first(row, "depends_on_task_id", "depends_on", "predecessor_id")
            successor = _first(row, "task_id", "successor_id")
            if predecessor is None or successor is None:
                raise DomainValidationError("missing_dependency_id", "Dependency requires task_id and depends_on_task_id.", path=f"task_dependencies[{index}]")
            lag_value = _integer(_first(row, "lag_minutes", default=0), path=f"task_dependencies[{index}].lag_minutes")
            assert lag_value is not None
            edges.append((str(predecessor), str(successor), lag_value))

    # Identical duplicate edge declarations do not alter the graph; retain the
    # largest explicit lag so conflicting duplicate rows cannot weaken a rule.
    edge_lags: dict[tuple[str, str], int] = {}
    for predecessor, successor, lag in edges:
        key = (predecessor, successor)
        edge_lags[key] = max(lag, edge_lags.get(key, 0))
    return [(before, after, lag) for (before, after), lag in sorted(edge_lags.items())]


def validate_task_dependencies(
    tasks: Sequence[Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Validate references/cycles and return a stable topological task order."""

    task_ids: list[str] = []
    errors: list[dict[str, str]] = []
    for index, task in enumerate(tasks):
        task_id = _identifier(task)
        if task_id is None:
            errors.append({"code": "missing_task_id", "path": f"tasks[{index}]", "message": "Task is missing its logical ID."})
        elif task_id in task_ids:
            errors.append({"code": "duplicate_task_id", "path": f"tasks[{index}]", "message": "Task IDs must be unique within a plan version."})
        else:
            task_ids.append(task_id)

    if errors:
        return {"valid": False, "errors": errors, "topological_order": []}

    edges = _dependency_edges(tasks, dependencies)
    known = set(task_ids)
    for predecessor, successor, _ in edges:
        if predecessor == successor:
            errors.append({"code": "self_dependency", "path": successor, "message": "A task cannot depend on itself."})
        elif predecessor not in known or successor not in known:
            errors.append({"code": "missing_dependency_task", "path": f"{predecessor}->{successor}", "message": "Dependency references a task outside this plan version."})
    if errors:
        return {"valid": False, "errors": errors, "topological_order": []}

    outgoing: dict[str, set[str]] = {task_id: set() for task_id in task_ids}
    indegree = {task_id: 0 for task_id in task_ids}
    for predecessor, successor, _ in edges:
        if successor not in outgoing[predecessor]:
            outgoing[predecessor].add(successor)
            indegree[successor] += 1

    ready = [task_id for task_id in task_ids if indegree[task_id] == 0]
    ready.sort()
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for successor in sorted(outgoing[current]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort()

    if len(ordered) != len(task_ids):
        cyclic = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
        return {
            "valid": False,
            "errors": [{"code": "dependency_cycle", "path": ",".join(cyclic), "message": "Task dependencies must form a directed acyclic graph."}],
            "topological_order": [],
        }
    return {"valid": True, "errors": [], "topological_order": ordered}


def topological_task_order(
    tasks: Sequence[Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return a stable topological order or raise :class:`DomainValidationError`."""

    report = validate_task_dependencies(tasks, dependencies)
    if not report["valid"]:
        first_error = report["errors"][0]
        raise DomainValidationError(first_error["code"], first_error["message"], path=first_error.get("path"))
    return list(report["topological_order"])


def _parse_local_date(value: Any, path: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise DomainValidationError("invalid_date", "Expected an ISO local date (YYYY-MM-DD).", path=path) from exc
    raise DomainValidationError("invalid_date", "Expected an ISO local date (YYYY-MM-DD).", path=path)


def _parse_instant(value: Any, path: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainValidationError("invalid_datetime", "Expected an ISO-8601 timestamp.", path=path) from exc
    else:
        raise DomainValidationError("invalid_datetime", "Expected an ISO-8601 timestamp.", path=path)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DomainValidationError("naive_datetime", "Timestamps must include a timezone offset.", path=path)
    return parsed.astimezone(timezone.utc)


def detect_schedule_conflicts(
    tasks: Sequence[Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    """Find explicit finish-to-start date/time conflicts.

    A task's ``finish_at`` or ``due_at`` is an explicit finish; its
    ``start_at`` is an explicit start. Local all-day scheduling uses
    ``finish_local_date``/``due_local_date`` and ``start_local_date``. A
    dependency with missing endpoints is unknown and is not converted into an
    invented date. A successor's due date earlier than its predecessor's due
    date is also a conflict because the dependent task cannot finish first.
    """

    report = validate_task_dependencies(tasks, dependencies)
    if not report["valid"]:
        return [
            {
                "code": error["code"],
                "task_id": error.get("path"),
                "message": error["message"],
                "severity": "blocker",
            }
            for error in report["errors"]
        ]

    by_id = {_identifier(task): task for task in tasks}
    conflicts: list[dict[str, Any]] = []
    for predecessor_id, successor_id, lag_minutes in _dependency_edges(tasks, dependencies):
        predecessor = by_id[predecessor_id]
        successor = by_id[successor_id]
        path = f"{predecessor_id}->{successor_id}"

        predecessor_finish = _parse_instant(
            _first(predecessor, "finish_at", "due_at"), f"tasks.{predecessor_id}.due_at"
        )
        successor_start = _parse_instant(_first(successor, "start_at"), f"tasks.{successor_id}.start_at")
        if predecessor_finish is not None and successor_start is not None:
            earliest_start = predecessor_finish + timedelta(minutes=lag_minutes)
            if successor_start < earliest_start:
                conflicts.append(
                    {
                        "code": "finish_to_start_conflict",
                        "predecessor_task_id": predecessor_id,
                        "successor_task_id": successor_id,
                        "required_start_at": earliest_start.isoformat().replace("+00:00", "Z"),
                        "actual_start_at": successor_start.isoformat().replace("+00:00", "Z"),
                        "lag_minutes": lag_minutes,
                        "severity": "blocker",
                    }
                )
            continue

        predecessor_finish_date = _parse_local_date(
            _first(predecessor, "finish_local_date", "due_local_date"), f"tasks.{predecessor_id}.due_local_date"
        )
        successor_start_date = _parse_local_date(
            _first(successor, "start_local_date"), f"tasks.{successor_id}.start_local_date"
        )
        successor_due_date = _parse_local_date(
            _first(successor, "due_local_date"), f"tasks.{successor_id}.due_local_date"
        )

        if predecessor_finish_date is not None and successor_start_date is not None:
            # For date-only values, a sub-day lag cannot be resolved exactly.
            # Same-day starts are accepted only for a zero lag; otherwise the
            # next local date is the first provable compliant start.
            # Date-only data cannot resolve sub-day ordering. Block only when
            # the successor date is earlier than a full-day lag makes possible.
            days = lag_minutes // 1440
            earliest_date = predecessor_finish_date + timedelta(days=days)
            if successor_start_date < earliest_date:
                conflicts.append(
                    {
                        "code": "finish_to_start_conflict",
                        "predecessor_task_id": predecessor_id,
                        "successor_task_id": successor_id,
                        "required_start_local_date": earliest_date.isoformat(),
                        "actual_start_local_date": successor_start_date.isoformat(),
                        "lag_minutes": lag_minutes,
                        "severity": "blocker",
                    }
                )
            continue

        # At date granularity, due dates are explicit finish bounds. They can
        # establish an impossible dependency order even without start dates.
        if predecessor_finish_date is not None and successor_due_date is not None:
            earliest_due = predecessor_finish_date + timedelta(days=lag_minutes // 1440)
            if successor_due_date < earliest_due:
                conflicts.append(
                    {
                        "code": "finish_to_start_due_date_conflict",
                        "predecessor_task_id": predecessor_id,
                        "successor_task_id": successor_id,
                        "required_due_local_date": earliest_due.isoformat(),
                        "actual_due_local_date": successor_due_date.isoformat(),
                        "lag_minutes": lag_minutes,
                        "severity": "blocker",
                    }
                )

    conflicts.sort(key=lambda item: (item.get("predecessor_task_id", ""), item.get("successor_task_id", ""), item["code"]))
    return conflicts


def _canonical_date(value: Any, field: str) -> str | None:
    if value is None:
        return None
    parsed = _parse_local_date(value, field)
    assert parsed is not None
    return parsed.isoformat()


def _canonical_instant(value: Any, field: str) -> str | None:
    parsed = _parse_instant(value, field)
    return parsed.isoformat().replace("+00:00", "Z") if parsed is not None else None


def _normalize_change(snapshot: Mapping[str, Any], change: Mapping[str, Any], index: int) -> dict[str, Any]:
    target = str(_first(change, "target", default="event"))
    target_id_value = _first(change, "target_id", "targetId")
    target_id = str(target_id_value) if target_id_value is not None else None
    field = _first(change, "field")
    if not isinstance(field, str):
        raise DomainValidationError("invalid_patch", "Each change must name an allowlisted field.", path=f"changes[{index}].field")
    value = _first(change, "value")

    if target == "event" and field in _EVENT_FIELDS:
        if field in {"guest_count", "budget_limit_minor", "venue_capacity", "seats_per_table"}:
            if field == "seats_per_table":
                normalized = _integer(value, path=f"changes[{index}].value", minimum=1, maximum=MAX_SEATS_PER_TABLE, nullable=True)
            elif field == "guest_count":
                normalized = _integer(value, path=f"changes[{index}].value", minimum=1, maximum=MAX_EVENT_GUESTS, nullable=True)
            elif field == "venue_capacity":
                normalized = _integer(value, path=f"changes[{index}].value", minimum=1, maximum=MAX_EVENT_GUESTS, nullable=True)
            else:
                normalized = _minor(value, path=f"changes[{index}].value", nullable=True)
        else:
            normalized = _canonical_date(value, f"changes[{index}].value")
        return {"target": target, "target_id": None, "field": field, "value": normalized, "source": "user"}

    if target in {"budget_item", "budget_category"}:
        if target_id is None:
            raise DomainValidationError("missing_target_id", "Budget changes require a target_id.", path=f"changes[{index}].target_id")
        rows = _item_rows(snapshot) if target == "budget_item" else _category_rows(snapshot)
        valid_ids = {_identifier(row) for row in rows}
        if target_id not in valid_ids:
            raise DomainValidationError("unknown_target", "Budget target does not exist in this plan version.", path=f"changes[{index}].target_id")
        allowed = _BUDGET_ITEM_FIELDS if target == "budget_item" else _CATEGORY_FIELDS
        if field not in allowed:
            raise DomainValidationError("unsupported_field", "Budget field is not patchable.", path=f"changes[{index}].field")
        if field in {"unit_rate_minor", "planned_minor", "rate_per_guest_minor"}:
            normalized = _minor(value, path=f"changes[{index}].value")
        else:
            normalized = str(_quantity_decimal(value, path=f"changes[{index}].value", maximum=Decimal("1000000")))
        return {"target": target, "target_id": target_id, "field": field, "value": normalized, "source": "user"}

    if target == "task":
        if target_id is None:
            raise DomainValidationError("missing_target_id", "Task changes require a target_id.", path=f"changes[{index}].target_id")
        task_ids = {_identifier(row) for row in _rows(_first(snapshot, "tasks", default=[]), "tasks")}
        if target_id not in task_ids:
            raise DomainValidationError("unknown_target", "Task target does not exist in this plan version.", path=f"changes[{index}].target_id")
        if field not in _TASK_FIELDS:
            raise DomainValidationError("unsupported_field", "Task field is not patchable.", path=f"changes[{index}].field")
        normalized = _canonical_instant(value, f"changes[{index}].value") if field == "due_at" else _canonical_date(value, f"changes[{index}].value")
        return {"target": target, "target_id": target_id, "field": field, "value": normalized, "source": "user"}

    if target == "vendor" and field == "status":
        if target_id is None:
            raise DomainValidationError("missing_target_id", "Vendor changes require a target_id.", path=f"changes[{index}].target_id")
        vendors = _rows(_first(snapshot, "vendors", default=[]), "vendors")
        if target_id not in {_identifier(row) for row in vendors}:
            raise DomainValidationError("unknown_target", "Vendor target does not exist in this plan version.", path=f"changes[{index}].target_id")
        if value not in _VENDOR_STATUSES:
            raise DomainValidationError("invalid_vendor_status", "Vendor status is not a supported user selection state.", path=f"changes[{index}].value")
        return {"target": target, "target_id": target_id, "field": field, "value": value, "source": "user"}

    raise DomainValidationError("unsupported_field", "Change target or field is not allowlisted.", path=f"changes[{index}]")


def normalize_ripple_changes(
    snapshot: Mapping[str, Any], proposed_changes: Mapping[str, Any] | Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Validate and canonically order an allowlisted Ripple patch.

    Accepts the versioned API's ``[{target, target_id, field, value}]`` rows or
    a concise event-only mapping such as ``{"guest_count": 200}``.
    """

    if isinstance(proposed_changes, Mapping):
        if "changes" in proposed_changes:
            raw_changes = proposed_changes["changes"]
            if not isinstance(raw_changes, Sequence) or isinstance(raw_changes, (str, bytes, bytearray)):
                raise DomainValidationError("invalid_patch", "The changes field must be a list.", path="changes")
            change_rows = list(_rows(raw_changes, "changes"))
        else:
            change_rows = []
            for key, value in proposed_changes.items():
                if key not in _EVENT_FIELDS:
                    raise DomainValidationError("unsupported_field", "Only allowlisted event fields may be changed.", path=str(key))
                change_rows.append({"target": "event", "field": key, "value": value})
    elif isinstance(proposed_changes, Sequence) and not isinstance(proposed_changes, (str, bytes, bytearray)):
        change_rows = list(_rows(proposed_changes, "changes"))
    else:
        raise DomainValidationError("invalid_patch", "Expected an event-field mapping or list of change records.", path="changes")

    if not change_rows:
        raise DomainValidationError("empty_patch", "At least one proposed change is required.", path="changes")
    if len(change_rows) > 32:
        raise DomainValidationError("patch_too_large", "A Ripple preview can contain at most 32 changes.", path="changes")

    normalized = [_normalize_change(snapshot, row, index) for index, row in enumerate(change_rows)]
    normalized.sort(key=lambda item: (item["target"], item["target_id"] or "", item["field"]))
    seen: dict[tuple[str, str | None, str], Any] = {}
    unique: list[dict[str, Any]] = []
    for row in normalized:
        key = (row["target"], row["target_id"], row["field"])
        if key in seen:
            if seen[key] != row["value"]:
                raise DomainValidationError("duplicate_patch_field", "A field cannot have conflicting proposed values.", path=f"{key[0]}.{key[1] or ''}.{key[2]}")
            continue
        seen[key] = row["value"]
        unique.append(row)
    return unique


def _update_record(rows: list[dict[str, Any]], target_id: str, field: str, value: Any) -> bool:
    for row in rows:
        if _identifier(row) == target_id:
            row[field] = value
            return True
    return False


def apply_changes(snapshot: Mapping[str, Any], normalized_changes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply a validated patch to a deep copy; the input snapshot is untouched."""

    candidate = copy.deepcopy(dict(snapshot))
    categories_key = "budget_categories" if "budget_categories" in candidate else "categories"
    items_key = "budget_items" if "budget_items" in candidate else "items"
    candidate.setdefault(categories_key, [])
    candidate.setdefault(items_key, [])
    touched_item_fields: dict[str, set[str]] = defaultdict(set)
    explicit_item_amounts: dict[str, int] = {}
    changed_category_rates: set[str] = set()
    for change in normalized_changes:
        target = change["target"]
        field = change["field"]
        value = change["value"]
        target_id = change.get("target_id")
        if target == "event":
            candidate[field] = value
        elif target == "budget_item":
            _update_record(candidate[items_key], str(target_id), field, value)
            touched_item_fields[str(target_id)].add(field)
            if field == "planned_minor":
                explicit_item_amounts[str(target_id)] = int(value)
        elif target == "budget_category":
            _update_record(candidate[categories_key], str(target_id), field, value)
            if field == "rate_per_guest_minor":
                changed_category_rates.add(str(target_id))
        elif target == "task":
            _update_record(candidate.setdefault("tasks", []), str(target_id), field, value)
        elif target == "vendor":
            _update_record(candidate.setdefault("vendors", []), str(target_id), field, value)

    # When the user edits a quantity or unit rate on an item that has both,
    # calculate the authoritative line total from those explicit inputs.
    for item in _rows(candidate[items_key], items_key):
        item_id = _identifier(item)
        if item_id is None or not touched_item_fields.get(item_id, set()).intersection({"quantity", "unit_rate_minor"}):
            continue
        quantity = _first(item, "quantity")
        rate = _first(item, "unit_rate_minor", "unitRateMinor")
        if quantity is None or rate is None:
            continue
        calculated = calculate_line_amount(quantity, rate)
        explicit_amount = explicit_item_amounts.get(item_id)
        if explicit_amount is not None and explicit_amount != calculated:
            raise DomainValidationError(
                "inconsistent_line_amount",
                "planned_minor must equal quantity multiplied by unit_rate_minor when both inputs are changed.",
                path=f"budget_items.{item_id}.planned_minor",
            )
        item["planned_minor"] = calculated

    # A newly selected category-level rate immediately updates its candidate
    # amount when attendance is known; no estimate is created while unknown.
    guest_count_for_rate = candidate.get("guest_count")
    if guest_count_for_rate is not None:
        for category in _rows(candidate[categories_key], categories_key):
            category_id = _identifier(category)
            if category_id in changed_category_rates:
                rate = _first(category, "rate_per_guest_minor", "ratePerGuestMinor")
                if rate is not None:
                    category["planned_minor"] = calculate_line_amount(guest_count_for_rate, rate)

    # Recompute explicitly configured per-guest amounts after attendance
    # changes. A category/item without this explicit basis is left untouched.
    if any(change["target"] == "event" and change["field"] == "guest_count" for change in normalized_changes):
        guest_count = candidate.get("guest_count")
        categories = _rows(candidate[categories_key], categories_key)
        for category in categories:
            rate = _first(category, "rate_per_guest_minor", "ratePerGuestMinor")
            if rate is not None and guest_count is not None:
                amount = calculate_line_amount(guest_count, rate)
                category["planned_minor"] = amount
        items = _rows(candidate[items_key], items_key)
        for item in items:
            basis = _first(item, "quantity_basis", "quantityBasis")
            if basis == "guest_count" and guest_count is not None:
                rate = _first(item, "unit_rate_minor", "unitRateMinor")
                if rate is not None:
                    amount = calculate_line_amount(guest_count, rate)
                    item["quantity"] = guest_count
                    item["planned_minor"] = amount
    return candidate


def _changed_values(before: Mapping[str, Any], after: Mapping[str, Any], changes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for patch in changes:
        target = patch["target"]
        field = patch["field"]
        target_id = patch.get("target_id")
        if target == "event":
            old = before.get(field)
            new = after.get(field)
            entity_id = _first(before, "event_id", "id")
        else:
            key = {"budget_item": ("budget_items", "items"), "budget_category": ("budget_categories", "categories"), "task": ("tasks",), "vendor": ("vendors",)}[target]
            source_rows = next((before[name] for name in key if name in before), [])
            result_rows = next((after[name] for name in key if name in after), [])
            old_row = next((row for row in source_rows if _identifier(row) == target_id), {})
            new_row = next((row for row in result_rows if _identifier(row) == target_id), {})
            old = _first(old_row, field)
            new = _first(new_row, field)
            entity_id = target_id
        if old != new:
            result.append(
                {
                    "entity": target,
                    "entity_id": entity_id,
                    "field": field,
                        "before": _to_jsonable(old),
                        "after": _to_jsonable(new),
                    "unit": "minor_currency_unit" if field.endswith("_minor") else None,
                    "source": "user",
                }
            )

    before_categories = { _identifier(row): row for row in _category_rows(before) }
    after_categories = { _identifier(row): row for row in _category_rows(after) }
    for category_id in sorted(set(before_categories) & set(after_categories)):
        old_row, new_row = before_categories[category_id], after_categories[category_id]
        # The budget summarizer is authoritative for per-guest/category item
        # totals; use it to capture derived category amount differences too.
        old_summary = calculate_budget({**before, "budget_categories": [old_row], "budget_items": []})["categories"][0]["planned_minor"]
        new_summary = calculate_budget({**after, "budget_categories": [new_row], "budget_items": []})["categories"][0]["planned_minor"]
        has_direct_amount_patch = any(
            change["target"] == "budget_category"
            and change.get("target_id") == category_id
            and change["field"] == "planned_minor"
            for change in changes
        )
        if old_summary != new_summary and not has_direct_amount_patch:
            result.append(
                {
                    "entity": "budget_category",
                    "entity_id": category_id,
                    "field": "planned_minor",
                    "before": old_summary,
                    "after": new_summary,
                    "unit": "minor_currency_unit",
                    "source": "deterministic_rule",
                    "rule_id": "per_guest_category_rate",
                }
            )

    before_items = {_identifier(row): row for row in _item_rows(before)}
    after_items = {_identifier(row): row for row in _item_rows(after)}
    for item_id in sorted(set(before_items) & set(after_items)):
        old_row, new_row = before_items[item_id], after_items[item_id]
        old_amount = _first(old_row, "planned_minor", "plannedMinor")
        new_amount = _first(new_row, "planned_minor", "plannedMinor")
        if old_amount != new_amount and not any(
            change["target"] == "budget_item" and change.get("target_id") == item_id and change["field"] == "planned_minor"
            for change in changes
        ):
            result.append(
                {
                    "entity": "budget_item",
                    "entity_id": item_id,
                    "field": "planned_minor",
                    "before": old_amount,
                    "after": new_amount,
                    "unit": "minor_currency_unit",
                    "source": "deterministic_rule",
                    "rule_id": "guest_count_quantity_rate",
                }
            )
    result.sort(key=lambda row: (row["entity"], str(row["entity_id"] or ""), row["field"]))
    return result


def _task_category(task: Mapping[str, Any]) -> str | None:
    value = _first(task, "category_id", "categoryId", "budget_category_id")
    return str(value) if value is not None else None


def _affected_entities(
    snapshot: Mapping[str, Any], candidate: Mapping[str, Any], normalized: Sequence[Mapping[str, Any]], changes: Sequence[Mapping[str, Any]]
) -> tuple[list[str], list[str]]:
    tasks = _rows(_first(snapshot, "tasks", default=[]), "tasks")
    vendors = _rows(_first(snapshot, "vendors", default=[]), "vendors")
    affected_categories: set[str] = set()
    affected_items: set[str] = set()
    direct_tasks: set[str] = set()
    direct_vendors: set[str] = set()
    for patch in normalized:
        if patch["target"] == "budget_category":
            affected_categories.add(str(patch["target_id"]))
        elif patch["target"] == "budget_item":
            affected_items.add(str(patch["target_id"]))
            item = next((row for row in _item_rows(snapshot) if _identifier(row) == patch["target_id"]), {})
            category_id = _first(item, "category_id", "categoryId")
            if category_id is not None:
                affected_categories.add(str(category_id))
        elif patch["target"] == "task":
            direct_tasks.add(str(patch["target_id"]))
        elif patch["target"] == "vendor":
            direct_vendors.add(str(patch["target_id"]))

    changed_categories = {
        row["entity_id"] for row in changes if row["entity"] == "budget_category" and row["entity_id"] is not None
    }
    changed_items = {row["entity_id"] for row in changes if row["entity"] == "budget_item" and row["entity_id"] is not None}
    affected_categories.update(str(value) for value in changed_categories)
    affected_items.update(str(value) for value in changed_items)

    guest_changed = any(row["target"] == "event" and row["field"] == "guest_count" for row in normalized)
    if guest_changed:
        # Only explicit per-guest rates/quantity bases create financial ripple.
        for category in _category_rows(snapshot):
            if _first(category, "rate_per_guest_minor", "ratePerGuestMinor") is not None:
                category_id = _identifier(category)
                if category_id is not None:
                    affected_categories.add(category_id)
        for item in _item_rows(snapshot):
            if _first(item, "quantity_basis", "quantityBasis") == "guest_count":
                item_id = _identifier(item)
                if item_id is not None:
                    affected_items.add(item_id)
                    category_id = _first(item, "category_id", "categoryId")
                    if category_id is not None:
                        affected_categories.add(str(category_id))

    for task in tasks:
        task_id = _identifier(task)
        if task_id is None:
            continue
        category_id = _task_category(task)
        item_id = _first(task, "budget_item_id", "budgetItemId")
        declared_triggers = _first(task, "depends_on_fields", "dependsOnFields", default=[])
        if category_id in affected_categories or item_id in affected_items:
            direct_tasks.add(task_id)
        elif guest_changed and "guest_count" in declared_triggers:
            direct_tasks.add(task_id)
        elif any(change["target"] == "event" and change["field"] in declared_triggers for change in normalized):
            direct_tasks.add(task_id)

    # Dependency descendants are operationally affected by a changed task but
    # remain unmodified. Invalid graphs are reported separately as blockers.
    report = validate_task_dependencies(tasks, _first(snapshot, "task_dependencies", default=None))
    if report["valid"]:
        edges = _dependency_edges(tasks, _first(snapshot, "task_dependencies", default=None))
        outgoing: dict[str, set[str]] = defaultdict(set)
        for predecessor, successor, _ in edges:
            outgoing[predecessor].add(successor)
        queue = deque(sorted(direct_tasks))
        while queue:
            current = queue.popleft()
            for successor in sorted(outgoing.get(current, ())):
                if successor not in direct_tasks:
                    direct_tasks.add(successor)
                    queue.append(successor)

    for vendor in vendors:
        vendor_id = _identifier(vendor)
        if vendor_id is None:
            continue
        category_id = _first(vendor, "budget_category_id", "category_id", "budgetCategoryId")
        item_id = _first(vendor, "budget_item_id", "budgetItemId")
        if category_id in affected_categories or item_id in affected_items:
            direct_vendors.add(vendor_id)

    return sorted(direct_tasks), sorted(direct_vendors)


def _capacity_summary(snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    guest_count = _first(snapshot, "guest_count")
    capacity = _first(snapshot, "venue_capacity")
    seats = _first(snapshot, "seats_per_table")
    if guest_count is not None:
        guest_count = _integer(guest_count, path="guest_count")
    if capacity is not None:
        capacity = _integer(capacity, path="venue_capacity")
    if seats is not None:
        seats = _integer(seats, path="seats_per_table", minimum=1)

    required_tables: int | None = None
    unknowns: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if guest_count is not None and seats is not None:
        required_tables = (guest_count + seats - 1) // seats
    elif guest_count is not None:
        unknowns.append({"code": "seating_capacity_unknown", "field": "seats_per_table", "message": "Seats per table are not configured; table count needs input."})
    if capacity is None:
        state = "unknown"
        unknowns.append({"code": "capacity_unknown", "field": "venue_capacity", "message": "Venue capacity is not configured; capacity cannot be confirmed."})
    elif guest_count is None:
        state = "unknown"
        unknowns.append({"code": "guest_count_unknown", "field": "guest_count", "message": "Guest count is not configured; venue capacity cannot be checked."})
    elif guest_count > capacity:
        state = "exceeded"
        blockers.append(
            {
                "code": "venue_capacity_exceeded",
                "severity": "hard",
                "guest_count": guest_count,
                "venue_capacity": capacity,
                "over_capacity_by": guest_count - capacity,
                "message": "Attendance exceeds the explicitly configured venue capacity.",
            }
        )
    else:
        state = "within"
    return (
        {
            "guest_count": guest_count,
            "venue_capacity": capacity,
            "state": state,
            "required_tables": required_tables,
            "seats_per_table": seats,
        },
        unknowns,
        warnings + blockers,
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def simulate_ripple(
    snapshot: Mapping[str, Any],
    proposed_changes: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    rule_config: Mapping[str, Any] | None = None,
    *,
    engine_version: str = ENGINE_VERSION,
) -> dict[str, Any]:
    """Calculate a deterministic, non-persistent Ripple preview.

    The returned mapping contains normalized direct changes, calculated budget
    and capacity before/after summaries, dependent task/vendor IDs, unknowns,
    warnings, blockers, ``commit_allowed``, and a stable SHA-256 preview hash.
    ``created_at``/expiry are deliberately left to the clock-owning API layer.
    """

    if not isinstance(snapshot, Mapping):
        raise DomainValidationError("invalid_snapshot", "Snapshot must be an object.", path="snapshot")
    if rule_config is None:
        rule_config = {}
    if not isinstance(rule_config, Mapping):
        raise DomainValidationError("invalid_rule_config", "Rule configuration must be an object.", path="rule_config")
    effective_engine_version = str(_first(rule_config, "engine_version", default=engine_version))
    effective_rule_config_version = str(
        _first(
            rule_config,
            "version",
            "rule_config_version",
            default=_first(snapshot, "rule_config_version", default="default-1"),
        )
    )
    normalized = normalize_ripple_changes(snapshot, proposed_changes)
    candidate = apply_changes(snapshot, normalized)

    before_budget = calculate_budget(snapshot)
    after_budget = calculate_budget(candidate)
    changes = _changed_values(snapshot, candidate, normalized)
    if before_budget["planned_minor"] != after_budget["planned_minor"]:
        changes.append(
            {
                "entity": "event",
                "entity_id": _first(snapshot, "event_id", "id"),
                "field": "planned_total_minor",
                "before": before_budget["planned_minor"],
                "after": after_budget["planned_minor"],
                "unit": "minor_currency_unit",
                "source": "deterministic_rule",
                "rule_id": "sum_planned_budget_items",
            }
        )
    changes.sort(key=lambda row: (row["entity"], str(row["entity_id"] or ""), row["field"]))

    before_capacity, before_capacity_unknowns, _ = _capacity_summary(snapshot)
    after_capacity, after_capacity_unknowns, capacity_findings = _capacity_summary(candidate)
    unknowns: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if before_capacity_unknowns or after_capacity_unknowns:
        for item in after_capacity_unknowns:
            if item not in unknowns:
                unknowns.append(item)
    for finding in capacity_findings:
        if finding.get("severity") == "hard":
            blockers.append(finding)

    if after_budget["over_budget_minor"] is not None and after_budget["over_budget_minor"] > 0:
        blockers.append(
            {
                "code": "budget_limit_exceeded",
                "severity": "hard",
                "budget_limit_minor": after_budget["budget_limit_minor"],
                "planned_minor": after_budget["planned_minor"],
                "over_budget_minor": after_budget["over_budget_minor"],
                "message": "Projected planned spend exceeds the explicit budget limit.",
            }
        )
    if after_budget["planned_minor"] is None:
        unknowns.append(
            {
                "code": "planned_budget_incomplete",
                "field": "budget_categories",
                "category_ids": after_budget["unknown_category_ids"],
                "message": "At least one budget category has no explicit amount or usable quantity/rate.",
            }
        )

    tasks = _rows(_first(snapshot, "tasks", default=[]), "tasks")
    dependency_rows = _first(snapshot, "task_dependencies", default=None)
    dependency_report = validate_task_dependencies(tasks, dependency_rows)
    if not dependency_report["valid"]:
        for error in dependency_report["errors"]:
            blockers.append({"code": error["code"], "severity": "hard", "path": error.get("path"), "message": error["message"]})
    candidate_tasks = _rows(_first(candidate, "tasks", default=[]), "tasks")
    schedule_conflicts = detect_schedule_conflicts(candidate_tasks, dependency_rows) if dependency_report["valid"] else []
    for conflict in schedule_conflicts:
        if conflict.get("severity") == "blocker":
            blockers.append({**conflict, "severity": "hard", "message": conflict.get("message", "A task dependency violates its explicit schedule dates.")})

    guest_count_changed = any(change["target"] == "event" and change["field"] == "guest_count" for change in normalized)
    invitation_unit = _first(candidate, "invitation_unit", "invitationUnit", default="unknown")
    invitation_summary: dict[str, Any]
    if invitation_unit == "person" and candidate.get("guest_count") is not None:
        invitation_summary = {"quantity": candidate["guest_count"], "unit": "invitation", "source": "explicit_person_rule"}
    elif invitation_unit == "household" and _first(candidate, "household_count") is not None:
        invitation_summary = {"quantity": _integer(candidate["household_count"], path="household_count"), "unit": "invitation", "source": "explicit_household_count"}
    else:
        invitation_summary = {"quantity": None, "unit": "invitation", "source": "unknown"}
        if guest_count_changed:
            unknowns.append(
                {
                    "code": "invitation_quantity_unknown",
                    "field": "invitation_unit",
                    "message": "Invitation quantity is unknown; no person or household rule was supplied.",
                }
            )

    affected_task_ids, affected_vendor_ids = _affected_entities(snapshot, candidate, normalized, changes)

    causal_trail: list[dict[str, Any]] = []
    for patch in normalized:
        related = [
            item
            for item in changes
            if (patch["target"] == "event" and item["entity"] == "event")
            or (
                patch.get("target_id") is not None
                and item.get("entity_id") == patch.get("target_id")
                and item["entity"] == patch["target"]
            )
            or (patch["target"] == "event" and patch["field"] == "guest_count" and item["entity"] in {"budget_category", "budget_item"})
        ]
        if patch["target"] == "event" and patch["field"] == "guest_count":
            rule_id = "guest_count_to_configured_per_guest_cost"
            explanation = "Guest count changed; only explicitly configured per-guest rates were recalculated."
        else:
            rule_id = "allowlisted_direct_change"
            explanation = "The proposed value was applied to the corresponding candidate snapshot field."
        causal_trail.append(
            {
                "trigger": {"target": patch["target"], "target_id": patch.get("target_id"), "field": patch["field"]},
                "rule_id": rule_id,
                "input": {"before": related[0]["before"] if related else None, "proposed": patch["value"]},
                "output": related,
                "affected_task_ids": affected_task_ids,
                "affected_vendor_ids": affected_vendor_ids,
                "explanation": explanation,
            }
        )

    # Completed tasks with an explicit assumption link are never silently
    # reopened. They require user review if the linked assumption changed.
    for task in tasks:
        task_id = _identifier(task)
        if task_id not in affected_task_ids or _first(task, "status") != "completed":
            continue
        blockers.append(
            {
                "code": "completed_task_requires_review",
                "severity": "hard",
                "task_id": task_id,
                "message": "A completed task is affected by this change and requires explicit user review.",
            }
        )

    # When configured venue capacity is unknown, keep it visible as unknown;
    # this does not itself prevent confirmation, matching the frozen contract.
    if before_budget["budget_limit_minor"] is None:
        unknowns.append({"code": "budget_limit_unknown", "field": "budget_limit_minor", "message": "No explicit budget limit is configured."})

    budget_delta = (
        after_budget["planned_minor"] - before_budget["planned_minor"]
        if after_budget["planned_minor"] is not None and before_budget["planned_minor"] is not None
        else None
    )
    result: dict[str, Any] = {
        "event_id": _first(snapshot, "event_id", "id"),
        "base_version_no": _first(snapshot, "version_no", "base_version_no", "current_plan_version_no"),
        "base_revision": _first(snapshot, "revision", "base_revision"),
        "engine_version": effective_engine_version,
        "rule_config_version": effective_rule_config_version,
        "normalized_changes": normalized,
        "changes": changes,
        "budget_summary": {
            "before": before_budget,
            "after": after_budget,
            "planned_delta_minor": budget_delta,
            "affected_category_ids": sorted(
                row["category_id"]
                for row in after_budget["categories"]
                if row["planned_minor"] != next(
                    (old["planned_minor"] for old in before_budget["categories"] if old["category_id"] == row["category_id"]),
                    None,
                )
            ),
        },
        "capacity_summary": {"before": before_capacity, "after": after_capacity},
        "invitation_summary": invitation_summary,
        "schedule_conflicts": schedule_conflicts,
        "causal_trail": causal_trail,
        "causes": causal_trail,
        "affected_task_ids": affected_task_ids,
        "affected_vendor_ids": affected_vendor_ids,
        "unknowns": unknowns,
        "warnings": warnings,
        "blockers": blockers,
        "commit_allowed": not blockers,
    }
    canonical_payload = {
        "engine_version": effective_engine_version,
        "rule_config_version": result["rule_config_version"],
        "event_id": result["event_id"],
        "base_version_no": result["base_version_no"],
        "base_revision": result["base_revision"],
        "normalized_changes": normalized,
        "changes": changes,
        "budget_summary": result["budget_summary"],
        "capacity_summary": result["capacity_summary"],
        "invitation_summary": invitation_summary,
        "schedule_conflicts": schedule_conflicts,
        "causal_trail": causal_trail,
        "affected_task_ids": affected_task_ids,
        "affected_vendor_ids": affected_vendor_ids,
        "unknowns": unknowns,
        "warnings": warnings,
        "blockers": blockers,
        "commit_allowed": result["commit_allowed"],
    }
    canonical_json = json.dumps(_to_jsonable(canonical_payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result["preview_hash"] = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return result


# Short aliases make the frozen conceptual API easy to use from services while
# keeping Ripple-specific names explicit at integration call sites.
simulate = simulate_ripple
validate_snapshot_budget = calculate_budget


__all__ = [
    "ENGINE_VERSION",
    "DomainValidationError",
    "calculate_line_amount",
    "calculate_budget",
    "validate_task_dependencies",
    "topological_task_order",
    "detect_schedule_conflicts",
    "normalize_ripple_changes",
    "apply_changes",
    "simulate_ripple",
    "simulate",
    "validate_snapshot_budget",
]
