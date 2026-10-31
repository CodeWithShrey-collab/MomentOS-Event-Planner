from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


EventTypeValue = Literal["wedding", "birthday", "community"]
TaskStatus = Literal["not_started", "in_progress", "blocked", "completed"]
TaskPriority = Literal["low", "medium", "high"]


class EventCreate(RequestModel):
    event_type: EventTypeValue
    title: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    budget_limit_minor: int | None = Field(default=None, ge=0, le=2_147_483_647)
    event_date: date | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location_label: str | None = Field(default=None, max_length=160)
    guest_count: int | None = Field(default=None, ge=1, le=100_000)
    preferences: dict[str, Any] = Field(default_factory=dict, max_length=40)
    constraints: dict[str, Any] = Field(default_factory=dict, max_length=40)


class EventPatch(RequestModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    event_type: EventTypeValue | None = None
    budget_limit_minor: int | None = Field(default=None, ge=0, le=2_147_483_647)
    event_date: date | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location_label: str | None = Field(default=None, max_length=160)
    guest_count: int | None = Field(default=None, ge=1, le=100_000)
    preferences: dict[str, Any] | None = Field(default=None, max_length=40)
    constraints: dict[str, Any] | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for name in ("title", "event_type"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self


class PlanCommit(RequestModel):
    base_version_no: int | None = Field(default=None, ge=1)
    confirmed: Literal[True]
    plan: dict[str, Any]


class BudgetCategoryInput(RequestModel):
    logical_id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    planned_minor: int | None = Field(default=None, ge=0, le=2_147_483_647)
    sort_order: int = Field(default=0, ge=0)
    source: Literal["user", "accepted_ai_suggestion", "demo_assumption"] = "user"
    is_required: bool = False


class BudgetItemInput(RequestModel):
    logical_id: UUID | None = None
    category_id: UUID
    label: str = Field(min_length=1, max_length=160)
    quantity: Decimal | None = Field(default=None, gt=0, le=1_000_000, max_digits=12, decimal_places=3)
    quantity_basis: Literal["guest_count", "fixed"] | None = None
    unit_rate_minor: int | None = Field(default=None, ge=0, le=2_147_483_647)
    planned_minor: int = Field(ge=0, le=2_147_483_647)
    actual_minor: int | None = Field(default=None, ge=0, le=2_147_483_647)
    status: Literal["illustrative_estimate", "user_estimate", "quoted_by_user", "confirmed_by_user", "paid_by_user"] = "user_estimate"
    source_note: str | None = Field(default=None, max_length=500)


class BudgetPatch(RequestModel):
    category_changes: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    item_changes: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    add_categories: list[BudgetCategoryInput] = Field(default_factory=list, max_length=30)
    add_items: list[BudgetItemInput] = Field(default_factory=list, max_length=500)
    remove_ids: list[UUID] = Field(default_factory=list, max_length=500)


class TaskCreate(RequestModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    task_type: Literal["task", "milestone", "event_activity"] = "task"
    status: TaskStatus = "not_started"
    owner_label: str | None = Field(default=None, max_length=120)
    due_at: datetime | None = None
    due_local_date: date | None = None
    phase: str | None = Field(default=None, max_length=40)
    priority: TaskPriority = "medium"
    depends_on_task_ids: list[UUID] = Field(default_factory=list, max_length=50)


class TaskPatch(RequestModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    task_type: Literal["task", "milestone", "event_activity"] | None = None
    status: TaskStatus | None = None
    owner_label: str | None = Field(default=None, max_length=120)
    due_at: datetime | None = None
    due_local_date: date | None = None
    phase: str | None = Field(default=None, max_length=40)
    priority: TaskPriority | None = None


class DependencyReplace(RequestModel):
    depends_on_task_ids: list[UUID] = Field(max_length=50)


class VendorCreate(RequestModel):
    category: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]{1,59}$")
    display_name: str | None = Field(default=None, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    location_note: str | None = Field(default=None, max_length=200)
    status: Literal["to_find", "contacted_by_user", "shortlisted_by_user", "selected_by_user", "declined_by_user"] = "to_find"
    notes: str | None = Field(default=None, max_length=2000)


class VendorPatch(RequestModel):
    display_name: str | None = Field(default=None, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    location_note: str | None = Field(default=None, max_length=200)
    status: Literal["to_find", "contacted_by_user", "shortlisted_by_user", "selected_by_user", "declined_by_user"] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class QuoteCreate(RequestModel):
    amount_minor: int = Field(ge=0, le=2_147_483_647)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    quote_date: date | None = None
    valid_until: date | None = None
    scope_note: str = Field(min_length=1, max_length=1000)


class RippleChange(RequestModel):
    target: Literal["event", "budget_item", "task", "vendor"]
    target_id: UUID | None = None
    field: Literal["guest_count", "budget_limit_minor", "unit_rate_minor", "planned_minor", "due_at", "venue_capacity", "seats_per_table"]
    value: int | date | datetime | None


class RippleCreate(RequestModel):
    base_version_no: int = Field(ge=1)
    changes: list[RippleChange] = Field(min_length=1, max_length=30)
    acknowledge_unknowns: bool = False


class RippleCommit(RequestModel):
    confirmed: Literal[True]
    acknowledged_warning_codes: list[str] = Field(default_factory=list, max_length=50)


class RippleCancel(RequestModel):
    confirmed: Literal[False]


class ScenarioInput(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    changes: list[RippleChange] = Field(min_length=1, max_length=30)


class ScenarioCompare(RequestModel):
    base_version_no: int = Field(ge=1)
    scenarios: list[ScenarioInput] = Field(min_length=1, max_length=3)


class IntakeRequest(RequestModel):
    description: str = Field(min_length=1, max_length=12_000)
    known_fields: dict[str, Any] = Field(default_factory=dict, max_length=40)


class PlanDraftRequest(RequestModel):
    brief: dict[str, Any]
    include: list[Literal["concept", "budget", "tasks", "vendors", "ideas"]] = Field(
        default_factory=lambda: ["concept", "budget", "tasks", "vendors", "ideas"], max_length=5
    )


class CopilotApiRequest(RequestModel):
    question: str = Field(min_length=1, max_length=4_000)
    context_sections: list[Literal["budget", "tasks", "vendors", "preferences"]] = Field(default_factory=lambda: ["budget", "tasks"], max_length=4)


def iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
