"""Bounded, strict schemas for the MomentOS GPT-6 Luna boundary.

These models describe suggestions and candidate facts only. They intentionally
do not represent persisted state, authoritative financial calculations, or
vendor availability.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_200)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ISODate = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=10)]
StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
StrictPositiveInt = Annotated[int, Field(strict=True, gt=0)]
BasisPoints = Annotated[int, Field(strict=True, ge=0, le=10_000)]


class StrictModel(BaseModel):
    # JSON endpoints validate decoded dictionaries with model_validate(), so
    # enum strings must be accepted there. Numeric/date-critical fields use
    # explicit strict constraints and string dates have real-calendar checks.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EventType(str, Enum):
    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    COMMUNITY = "community"
    OTHER = "other"


class FactSource(str, Enum):
    USER_INPUT = "user_input"
    INFERENCE = "inference"
    SUGGESTION = "suggestion"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Phase(str, Enum):
    BEFORE_EVENT = "before_event"
    EVENT_DAY = "event_day"
    AFTER_EVENT = "after_event"


TValue = TypeVar("TValue")


class TypedCandidate(StrictModel, Generic[TValue]):
    value: TValue
    source: FactSource
    evidence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class EvidenceText(StrictModel):
    text: MediumText
    source: FactSource
    evidence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class KnownFact(StrictModel):
    field: Reference
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]
    source: FactSource
    evidence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class EventRequirements(StrictModel):
    """Structured extraction; nullable candidates remain explicitly unknown."""

    event_type_candidate: TypedCandidate[EventType] | None = None
    title_candidate: TypedCandidate[ShortText] | None = None
    date_candidate: TypedCandidate[ISODate] | None = None
    location_candidate: TypedCandidate[ShortText] | None = None
    guest_count_candidate: TypedCandidate[StrictPositiveInt] | None = None
    budget_candidate_minor: TypedCandidate[StrictNonNegativeInt] | None = None
    currency_candidate: TypedCandidate[Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]] | None = None
    preferences: list[EvidenceText] = Field(default_factory=list, max_length=30)
    hard_constraints: list[EvidenceText] = Field(default_factory=list, max_length=30)
    soft_preferences: list[EvidenceText] = Field(default_factory=list, max_length=30)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=30)
    follow_up_questions: list[ShortText] = Field(default_factory=list, max_length=5)

    @field_validator("date_candidate")
    @classmethod
    def valid_iso_date(cls, candidate: TypedCandidate[ISODate] | None) -> TypedCandidate[ISODate] | None:
        if candidate is not None:
            try:
                date.fromisoformat(candidate.value)
            except ValueError as exc:
                raise ValueError("date_candidate must be a real ISO calendar date") from exc
        return candidate


# The architecture document calls the extraction output ExtractedRequirements.
ExtractedRequirements = EventRequirements


class ExtractionRequest(StrictModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000)]
    known_fields: dict[ShortText, str | int | bool | None] = Field(default_factory=dict, max_length=40)
    event_type_hint: EventType | None = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2}-[A-Z]{2}$")] = "en-IN"


class CommonEventContext(StrictModel):
    event_type: EventType
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2}-[A-Z]{2}$")] = "en-IN"
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "INR"
    event_date: ISODate | None = None
    location_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    guest_count: Annotated[int, Field(strict=True, ge=1, le=100_000)] | None = None
    budget_limit_minor: StrictNonNegativeInt | None = None
    preferences: list[MediumText] = Field(default_factory=list, max_length=25)
    constraints: list[MediumText] = Field(default_factory=list, max_length=25)
    known_facts: list[KnownFact] = Field(default_factory=list, max_length=40)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=30)

    @field_validator("event_date")
    @classmethod
    def valid_event_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("event_date must be a real ISO calendar date") from exc
        return value


class EventBrief(CommonEventContext):
    approved_extracted_values: dict[ShortText, str | int | bool | None] = Field(default_factory=dict, max_length=40)
    concept_preference: MediumText | None = None
    requested_sections: list[ShortText] = Field(default_factory=list, max_length=15)


class BlueprintConcept(StrictModel):
    title: ShortText
    description: MediumText
    style: ShortText


class BudgetCategorySuggestion(StrictModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    name: ShortText
    rationale: MediumText
    priority: Priority
    suggested_share_basis_points: BasisPoints | None = None


class BudgetItemSuggestion(StrictModel):
    label: ShortText
    category_key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    quantity: StrictNonNegativeInt | None = None
    rate_minor: StrictNonNegativeInt | None = None
    quantity_basis: Literal["guest_count", "fixed"] | None = None
    estimate_basis: Literal["user_supplied", "illustrative", "unknown"]
    provenance: FactSource

    @model_validator(mode="after")
    def prevent_unsupported_estimates(self) -> "BudgetItemSuggestion":
        if self.estimate_basis == "unknown" and (self.quantity is not None or self.rate_minor is not None):
            raise ValueError("unknown estimates cannot include quantity or rate values")
        if self.quantity_basis == "guest_count" and (self.quantity is None or self.rate_minor is None):
            raise ValueError("guest-count-based items need both quantity and rate")
        if self.estimate_basis == "user_supplied" and self.provenance is not FactSource.USER_INPUT:
            raise ValueError("user_supplied estimates must cite user_input provenance")
        if self.estimate_basis == "illustrative" and self.provenance is not FactSource.SUGGESTION:
            raise ValueError("illustrative estimates must be labeled as suggestions")
        return self


class BlueprintTaskSuggestion(StrictModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    title: ShortText
    rationale: MediumText
    relative_timing_suggestion: ShortText
    phase: Phase
    priority: Priority
    depends_on_keys: list[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]] = Field(
        default_factory=list, max_length=30
    )
    owner: None = None
    status: Literal["not_started"] = "not_started"


class BlueprintVendorCategory(StrictModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    category: ShortText
    why: MediumText
    follow_up_checklist: list[ShortText] = Field(default_factory=list, max_length=15)


class BlueprintIdea(StrictModel):
    idea: MediumText
    personalization_rationale: MediumText
    input_references: list[Reference] = Field(min_length=1, max_length=20)


class EventBlueprint(StrictModel):
    concept: BlueprintConcept
    assumptions: list[ShortText] = Field(default_factory=list, max_length=30)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=30)
    budget_categories: list[BudgetCategorySuggestion] = Field(default_factory=list, max_length=30)
    budget_items: list[BudgetItemSuggestion] = Field(default_factory=list, max_length=80)
    tasks: list[BlueprintTaskSuggestion] = Field(default_factory=list, max_length=60)
    vendor_categories: list[BlueprintVendorCategory] = Field(default_factory=list, max_length=30)
    ideas: list[BlueprintIdea] = Field(default_factory=list, max_length=30)
    warnings: list[ShortText] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_keys_and_dependencies(self) -> "EventBlueprint":
        category_keys = [category.key for category in self.budget_categories]
        if len(category_keys) != len(set(category_keys)):
            raise ValueError("budget category keys must be unique")
        allocated_shares = sum(category.suggested_share_basis_points or 0 for category in self.budget_categories)
        if allocated_shares > 10_000:
            raise ValueError("suggested category shares cannot exceed the whole budget")
        item_categories = set(category_keys)
        if any(item.category_key not in item_categories for item in self.budget_items):
            raise ValueError("budget items must reference a returned category")
        task_keys = [task.key for task in self.tasks]
        if len(task_keys) != len(set(task_keys)):
            raise ValueError("task keys must be unique")
        _validate_dependency_graph({task.key: task.depends_on_keys for task in self.tasks})
        return self


class EventIdeas(StrictModel):
    ideas: list["PersonalizedIdea"] = Field(min_length=1, max_length=8)
    assumptions: list[ShortText] = Field(default_factory=list, max_length=20)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=20)


class PersonalizedIdea(StrictModel):
    title: ShortText
    description: MediumText
    why_it_fits: list[Reference] = Field(min_length=1, max_length=20)
    tradeoffs: list[ShortText] = Field(default_factory=list, max_length=10)
    assumptions: list[ShortText] = Field(default_factory=list, max_length=10)
    user_inputs_needed: list[ShortText] = Field(default_factory=list, max_length=10)


PersonalizedIdeas = EventIdeas


class PersonalizedIdeasRequest(StrictModel):
    context: CommonEventContext
    focus: Literal["theme", "food", "activities", "accessibility", "traditions", "savings"]
    max_item_count: Annotated[int, Field(strict=True, ge=1, le=8)] = 5


class TaskSuggestionRequest(StrictModel):
    event_type: EventType
    event_date: ISODate | None = None
    timezone: Annotated[str, StringConstraints(pattern=r"^[A-Za-z_+-]+(?:/[A-Za-z0-9_+-]+)*$")] | None = None
    plan_summary: MediumText
    max_task_count: Annotated[int, Field(strict=True, ge=1, le=30)] = 20
    existing_tasks: list[Reference] = Field(default_factory=list, max_length=100)
    explicit_milestones: list[MediumText] = Field(default_factory=list, max_length=30)
    constraints: list[MediumText] = Field(default_factory=list, max_length=25)

    @field_validator("event_date")
    @classmethod
    def valid_event_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("event_date must be a real ISO calendar date") from exc
        return value


class SuggestedTask(StrictModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    title: ShortText
    description: MediumText
    phase: Phase
    relative_due_days: Annotated[int, Field(strict=True, ge=0, le=3_650)] | None = None
    depends_on_keys: list[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]] = Field(
        default_factory=list, max_length=30
    )
    priority: Priority
    rationale: MediumText
    required_input: list[ShortText] = Field(default_factory=list, max_length=15)
    owner: None = None
    status: Literal["not_started"] = "not_started"


class SuggestedTasks(StrictModel):
    tasks: list[SuggestedTask] = Field(max_length=30)

    @model_validator(mode="after")
    def validate_task_graph(self) -> "SuggestedTasks":
        keys = [task.key for task in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("task keys must be unique")
        _validate_dependency_graph({task.key: task.depends_on_keys for task in self.tasks})
        return self


class VendorChecklistRequest(StrictModel):
    event_type: EventType
    location_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    event_summary: MediumText
    guest_range: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    budget_priorities: list[ShortText] = Field(default_factory=list, max_length=20)
    existing_vendor_categories: list[ShortText] = Field(default_factory=list, max_length=30)


VENDOR_CATEGORY_ALLOWLIST = frozenset(
    {
        "accommodation",
        "accessibility",
        "audio_visual",
        "catering",
        "cleaning",
        "coordination",
        "decor",
        "entertainment",
        "first_aid",
        "florist",
        "invitations",
        "lighting",
        "makeup",
        "photography",
        "power",
        "permits",
        "rentals",
        "security",
        "stationery",
        "transportation",
        "venue",
        "waste_management",
        "water",
    }
)


class VendorChecklistCategory(StrictModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    why_needed: MediumText
    user_questions: list[ShortText] = Field(default_factory=list, max_length=15)
    selection_criteria: list[ShortText] = Field(default_factory=list, max_length=15)
    follow_up_task_suggestions: list[ShortText] = Field(default_factory=list, max_length=15)
    required_inputs: list[ShortText] = Field(default_factory=list, max_length=15)

    @field_validator("key")
    @classmethod
    def allowlisted_category(cls, value: str) -> str:
        if value not in VENDOR_CATEGORY_ALLOWLIST:
            raise ValueError("vendor category key is not allowlisted")
        return value


class VendorChecklist(StrictModel):
    categories: list[VendorChecklistCategory] = Field(max_length=30)

    @model_validator(mode="after")
    def unique_categories(self) -> "VendorChecklist":
        keys = [category.key for category in self.categories]
        if len(keys) != len(set(keys)):
            raise ValueError("vendor category keys must be unique")
        return self


class RippleValue(StrictModel):
    result_id: Reference
    label: ShortText
    before: str | int | Decimal | None
    after: str | int | Decimal | None
    unit: ShortText

    @field_validator("before", "after")
    @classmethod
    def finite_decimal(cls, value: str | int | Decimal | None) -> str | int | Decimal | None:
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("ripple values must be finite")
        return value


class RippleSimulationInput(StrictModel):
    """Only deterministic service output is supplied to the explanation call."""

    values: list[RippleValue] = Field(max_length=100)
    rule_ids: list[Reference] = Field(default_factory=list, max_length=100)
    blockers: list[ShortText] = Field(default_factory=list, max_length=50)
    warnings: list[ShortText] = Field(default_factory=list, max_length=50)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=50)
    user_priorities: list[ShortText] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_result_and_rule_ids(self) -> "RippleSimulationInput":
        result_ids = [value.result_id for value in self.values]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("Ripple result IDs must be unique")
        if len(self.rule_ids) != len(set(self.rule_ids)):
            raise ValueError("Ripple rule IDs must be unique")
        return self


class RippleCausalStep(StrictModel):
    trigger: ShortText
    rule_id: Reference
    result_reference: Reference
    explanation: MediumText


class RippleOption(StrictModel):
    title: ShortText
    tradeoff: MediumText
    required_user_edit: ShortText
    constraint_risk: ShortText


class RippleExplanation(StrictModel):
    summary: MediumText
    causal_steps: list[RippleCausalStep] = Field(default_factory=list, max_length=30)
    options: list[RippleOption] = Field(default_factory=list, max_length=10)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=30)


class FeasibleModification(StrictModel):
    opportunity_id: Reference
    label: ShortText
    saving_minor: StrictNonNegativeInt
    affected_categories: list[Reference] = Field(default_factory=list, max_length=20)
    tradeoff: MediumText
    preserved_constraints: list[Reference] = Field(default_factory=list, max_length=20)


class CopilotTaskFact(StrictModel):
    task_id: Reference
    title: ShortText
    status: Literal["not_started", "in_progress", "done", "blocked"]
    due_local_date: ISODate | None = None


class CopilotVendorFact(StrictModel):
    category_key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    status: Literal["needed", "researching", "quoted", "selected", "booked"]
    estimated_cost_minor: StrictNonNegativeInt | None = None
    confirmed_cost_minor: StrictNonNegativeInt | None = None

    @field_validator("category_key")
    @classmethod
    def allowlisted_category(cls, value: str) -> str:
        if value not in VENDOR_CATEGORY_ALLOWLIST:
            raise ValueError("vendor category key is not allowlisted")
        return value


class MinimalEventContext(StrictModel):
    """Allowlisted copilot context; callers should omit unrelated PII."""

    event_type: EventType
    event_title: ShortText
    event_date: ISODate | None = None
    location_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    guest_count: Annotated[int, Field(strict=True, ge=1, le=100_000)] | None = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "INR"
    budget_limit_minor: StrictNonNegativeInt | None = None
    facts: list[KnownFact] = Field(default_factory=list, max_length=40)
    task_statuses: list[CopilotTaskFact] = Field(default_factory=list, max_length=40)
    vendor_categories: list[CopilotVendorFact] = Field(default_factory=list, max_length=30)
    feasible_modifications: list[FeasibleModification] = Field(default_factory=list, max_length=20)

    @field_validator("event_date")
    @classmethod
    def valid_event_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("event_date must be a real ISO calendar date") from exc
        return value


class CopilotRequest(StrictModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)]
    event_context: MinimalEventContext
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2}-[A-Z]{2}$")] = "en-IN"
    response_scope: Literal["brief", "planning", "tradeoff"] = "brief"


class CopilotSuggestion(StrictModel):
    text: MediumText
    references: list[Reference] = Field(default_factory=list, max_length=20)


class CopilotAnswer(StrictModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_200)]
    known_references: list[Reference] = Field(default_factory=list, max_length=30)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=30)
    suggestions: list[CopilotSuggestion] = Field(default_factory=list, max_length=15)
    needs_user_confirmation: bool


def _validate_dependency_graph(dependencies: dict[str, list[str]]) -> None:
    keys = set(dependencies)
    for task_key, parents in dependencies.items():
        if task_key in parents:
            raise ValueError("a task cannot depend on itself")
        if len(parents) != len(set(parents)):
            raise ValueError("task dependency keys must be unique")
        if any(parent not in keys for parent in parents):
            raise ValueError("task dependencies must reference returned task keys")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError("task dependencies cannot contain cycles")
        if key in visited:
            return
        visiting.add(key)
        for parent in dependencies[key]:
            visit(parent)
        visiting.remove(key)
        visited.add(key)

    for task_key in dependencies:
        visit(task_key)


__all__ = [
    "BlueprintConcept",
    "BlueprintIdea",
    "BlueprintTaskSuggestion",
    "BudgetCategorySuggestion",
    "BudgetItemSuggestion",
    "CommonEventContext",
    "CopilotAnswer",
    "CopilotRequest",
    "CopilotTaskFact",
    "CopilotVendorFact",
    "EventBlueprint",
    "EventBrief",
    "EventIdeas",
    "EventRequirements",
    "EventType",
    "EvidenceText",
    "ExtractedRequirements",
    "ExtractionRequest",
    "FactSource",
    "FeasibleModification",
    "KnownFact",
    "MinimalEventContext",
    "PersonalizedIdeas",
    "PersonalizedIdeasRequest",
    "Phase",
    "Priority",
    "RippleExplanation",
    "RippleSimulationInput",
    "SuggestedTasks",
    "TaskSuggestionRequest",
    "VendorChecklist",
    "VendorChecklistRequest",
    "_validate_dependency_graph",
]
