"""Normalized SQLAlchemy models for MomentOS.

Accepted plan snapshots are append-only. Services must still scope every read
through the owning guest session and validate mutations before inserting rows.
The composite foreign keys here enforce ownership and same-version references
at the database boundary as well as in service code.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)

from .extensions import db


def _uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class GuestSession(db.Model):
    __tablename__ = "guest_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_guest_sessions_token_hash"),
        Index("ix_guest_sessions_expires_at", "expires_at"),
        CheckConstraint("schema_version > 0", name="schema_version_positive"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    token_hash = db.Column(String(64), nullable=False)
    csrf_hash = db.Column(String(64), nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = db.Column(DateTime(timezone=True), nullable=False)
    absolute_expires_at = db.Column(DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(DateTime(timezone=True))
    schema_version = db.Column(Integer, nullable=False, default=1)

    events = db.relationship("Event", back_populates="owner_session", cascade="all, delete-orphan")


class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("id", "owner_session_id", name="uq_events_id_owner_session"),
        ForeignKeyConstraint(
            ["id", "current_plan_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_events_current_plan_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint("budget_limit_minor IS NULL OR budget_limit_minor >= 0", name="budget_nonnegative"),
        CheckConstraint("current_plan_version_no IS NULL OR current_plan_version_no > 0", name="current_version_positive"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("event_type IN ('wedding','birthday','community')", name="event_type_valid"),
        CheckConstraint("length(currency) = 3", name="currency_iso_length"),
        Index("ix_events_owner_updated", "owner_session_id", "updated_at"),
        Index("ix_events_owner_id", "owner_session_id", "id"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    owner_session_id = db.Column(
        String(36), ForeignKey("guest_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type = db.Column(String(16), nullable=False)
    title = db.Column(String(160), nullable=False)
    currency = db.Column(String(3), nullable=False)
    budget_limit_minor = db.Column(Integer)
    event_date = db.Column(Date)
    timezone = db.Column(String(64))
    location_label = db.Column(String(240))
    # Bounded unsaved-plan inputs collected before the first accepted snapshot.
    draft_fields_json = db.Column(JSON, nullable=False, default=dict)
    current_plan_version_no = db.Column(Integer)
    revision = db.Column(Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    deleted_at = db.Column(DateTime(timezone=True))

    owner_session = db.relationship("GuestSession", back_populates="events")
    plan_versions = db.relationship(
        "EventPlanVersion",
        back_populates="event",
        foreign_keys="EventPlanVersion.event_id",
        cascade="all, delete-orphan",
        order_by="EventPlanVersion.version_no",
    )


class EventPlanVersion(db.Model):
    __tablename__ = "event_plan_versions"
    __table_args__ = (
        UniqueConstraint("event_id", "version_no", name="uq_event_plan_versions_event_version"),
        UniqueConstraint("id", "event_id", name="uq_event_plan_versions_id_event"),
        ForeignKeyConstraint(
            ["event_id", "created_by_session_id"],
            ["events.id", "events.owner_session_id"],
            name="fk_event_plan_versions_event_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["event_id", "base_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_event_plan_versions_base_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_simulation_id"],
            ["ripple_simulations.id"],
            name="fk_event_plan_versions_source_simulation",
            ondelete="SET NULL",
            use_alter=True,
        ),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("base_version_no IS NULL OR base_version_no > 0", name="base_version_positive"),
        CheckConstraint("base_version_no IS NULL OR base_version_no < version_no", name="base_version_precedes"),
        CheckConstraint("event_type IN ('wedding','birthday','community')", name="event_type_valid"),
        CheckConstraint("change_kind IN ('initial_plan','user_edit','ripple_commit')", name="change_kind_valid"),
        CheckConstraint("length(currency) = 3", name="currency_iso_length"),
        Index("ix_event_plan_versions_event_version_desc", "event_id", text("version_no DESC")),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    event_id = db.Column(String(36), nullable=False)
    version_no = db.Column(Integer, nullable=False)
    base_version_no = db.Column(Integer)
    change_kind = db.Column(String(24), nullable=False)
    event_type = db.Column(String(16), nullable=False)
    title = db.Column(String(160), nullable=False)
    currency = db.Column(String(3), nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by_session_id = db.Column(String(36), nullable=False)
    source_simulation_id = db.Column(String(36))
    change_summary = db.Column(String(600))

    event = db.relationship("Event", back_populates="plan_versions", foreign_keys=[event_id])
    details = db.relationship("EventDetails", back_populates="plan_version", uselist=False, cascade="all, delete-orphan")
    budget_categories = db.relationship("BudgetCategory", back_populates="plan_version", cascade="all, delete-orphan")
    budget_items = db.relationship("BudgetItem", back_populates="plan_version", cascade="all, delete-orphan", overlaps="items,category")
    tasks = db.relationship("Task", back_populates="plan_version", cascade="all, delete-orphan")
    vendors = db.relationship("Vendor", back_populates="plan_version", cascade="all, delete-orphan")


class EventDetails(db.Model):
    __tablename__ = "event_details"
    __table_args__ = (
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        CheckConstraint("budget_limit_minor IS NULL OR budget_limit_minor >= 0", name="budget_nonnegative"),
        CheckConstraint("guest_count IS NULL OR guest_count >= 0", name="guest_count_nonnegative"),
        CheckConstraint("venue_capacity IS NULL OR venue_capacity >= 0", name="venue_capacity_nonnegative"),
        CheckConstraint("seats_per_table IS NULL OR seats_per_table > 0", name="seats_per_table_positive"),
        CheckConstraint("guest_count_source IS NULL OR guest_count_source IN ('user','accepted_ai_suggestion','demo_assumption')", name="guest_source_valid"),
        CheckConstraint("venue_capacity_source IS NULL OR venue_capacity_source IN ('user','accepted_ai_suggestion','demo_assumption')", name="capacity_source_valid"),
        CheckConstraint("invitation_unit IS NULL OR invitation_unit IN ('person','household','unknown')", name="invitation_unit_valid"),
    )

    event_version_id = db.Column(String(36), primary_key=True)
    budget_limit_minor = db.Column(Integer)
    event_date = db.Column(Date)
    timezone = db.Column(String(64))
    location_label = db.Column(String(240))
    guest_count = db.Column(Integer)
    guest_count_source = db.Column(String(32))
    venue_capacity = db.Column(Integer)
    venue_capacity_source = db.Column(String(32))
    seats_per_table = db.Column(Integer)
    invitation_unit = db.Column(String(16))
    accessibility_notes = db.Column(String(1200))
    preferences_json = db.Column(JSON, nullable=False, default=dict)
    constraints_json = db.Column(JSON, nullable=False, default=dict)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)

    plan_version = db.relationship("EventPlanVersion", back_populates="details")


class BudgetCategory(db.Model):
    __tablename__ = "budget_categories"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "logical_id"),
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        CheckConstraint("planned_minor IS NULL OR planned_minor >= 0", name="planned_nonnegative"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint("source IN ('user','accepted_ai_suggestion','demo_assumption')", name="source_valid"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    logical_id = db.Column(String(36), nullable=False, default=_uuid)
    name = db.Column(String(120), nullable=False)
    planned_minor = db.Column(Integer)
    sort_order = db.Column(Integer, nullable=False, default=0, server_default="0")
    source = db.Column(String(32), nullable=False)
    is_required = db.Column(Boolean, nullable=False, default=False, server_default="0")

    plan_version = db.relationship("EventPlanVersion", back_populates="budget_categories")
    items = db.relationship("BudgetItem", back_populates="category", cascade="all, delete-orphan", overlaps="budget_items,plan_version")


class BudgetItem(db.Model):
    __tablename__ = "budget_items"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "logical_id"),
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["event_version_id", "category_id"],
            ["budget_categories.event_version_id", "budget_categories.logical_id"],
            name="fk_budget_items_category_same_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="quantity_positive"),
        CheckConstraint("quantity_basis IS NULL OR quantity_basis IN ('guest_count','fixed')", name="quantity_basis_valid"),
        CheckConstraint("unit_rate_minor IS NULL OR unit_rate_minor >= 0", name="unit_rate_nonnegative"),
        CheckConstraint("planned_minor >= 0", name="planned_nonnegative"),
        CheckConstraint("actual_minor IS NULL OR actual_minor >= 0", name="actual_nonnegative"),
        CheckConstraint("status IN ('illustrative_estimate','user_estimate','quoted_by_user','confirmed_by_user','paid_by_user')", name="status_valid"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    logical_id = db.Column(String(36), nullable=False, default=_uuid)
    category_id = db.Column(String(36), nullable=False)
    label = db.Column(String(160), nullable=False)
    quantity = db.Column(db.Numeric(12, 3))
    quantity_basis = db.Column(String(24))
    unit_rate_minor = db.Column(Integer)
    planned_minor = db.Column(Integer, nullable=False)
    actual_minor = db.Column(Integer)
    status = db.Column(String(32), nullable=False)
    source_note = db.Column(String(600))
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)

    plan_version = db.relationship("EventPlanVersion", back_populates="budget_items", overlaps="items,category")
    category = db.relationship("BudgetCategory", back_populates="items", overlaps="budget_items,plan_version")


class Vendor(db.Model):
    __tablename__ = "vendors"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "logical_id"),
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        CheckConstraint("status IN ('to_find','contacted_by_user','shortlisted_by_user','selected_by_user','declined_by_user')", name="status_valid"),
        CheckConstraint("information_source IN ('checklist_suggestion','user_entered')", name="information_source_valid"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    logical_id = db.Column(String(36), nullable=False, default=_uuid)
    category = db.Column(String(80), nullable=False)
    display_name = db.Column(String(160))
    contact_name = db.Column(String(120))
    email = db.Column(String(254))
    phone = db.Column(String(40))
    location_note = db.Column(String(240))
    status = db.Column(String(32), nullable=False, default="to_find")
    information_source = db.Column(String(32), nullable=False)
    notes = db.Column(String(1200))
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)

    plan_version = db.relationship("EventPlanVersion", back_populates="vendors")
    quotes = db.relationship("VendorQuote", back_populates="vendor", cascade="all, delete-orphan")


class VendorQuote(db.Model):
    __tablename__ = "vendor_quotes"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "logical_id"),
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["event_version_id", "vendor_id"],
            ["vendors.event_version_id", "vendors.logical_id"],
            name="fk_vendor_quotes_vendor_same_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount_minor >= 0", name="amount_nonnegative"),
        CheckConstraint("length(currency) = 3", name="currency_iso_length"),
        CheckConstraint("source = 'user_entered'", name="source_user_entered"),
        CheckConstraint("status IN ('received_by_user','accepted_by_user','rejected_by_user')", name="status_valid"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    logical_id = db.Column(String(36), nullable=False, default=_uuid)
    vendor_id = db.Column(String(36), nullable=False)
    amount_minor = db.Column(Integer, nullable=False)
    currency = db.Column(String(3), nullable=False)
    quote_date = db.Column(Date)
    valid_until = db.Column(Date)
    scope_note = db.Column(String(600), nullable=False)
    source = db.Column(String(24), nullable=False, default="user_entered", server_default="user_entered")
    status = db.Column(String(24), nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)

    vendor = db.relationship("Vendor", back_populates="quotes")


class Task(db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "logical_id"),
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["event_version_id", "vendor_id"],
            ["vendors.event_version_id", "vendors.logical_id"],
            name="fk_tasks_vendor_same_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["completed_by_session_id"], ["guest_sessions.id"], ondelete="SET NULL"),
        CheckConstraint("task_type IN ('task','milestone','event_activity')", name="task_type_valid"),
        CheckConstraint("status IN ('not_started','in_progress','blocked','completed')", name="status_valid"),
        CheckConstraint("priority IN ('low','medium','high')", name="priority_valid"),
        CheckConstraint("source IN ('user','accepted_ai_suggestion','demo_assumption')", name="source_valid"),
        CheckConstraint("completion_source IS NULL OR completion_source = 'user'", name="completion_source_user"),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL AND completed_by_session_id IS NOT NULL AND completion_source = 'user') "
            "OR (status <> 'completed' AND completed_at IS NULL AND completed_by_session_id IS NULL AND completion_source IS NULL)",
            name="completion_requires_user_actor",
        ),
        Index("ix_tasks_version_due", "event_version_id", "due_at"),
        Index("ix_tasks_version_status", "event_version_id", "status"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    logical_id = db.Column(String(36), nullable=False, default=_uuid)
    title = db.Column(String(160), nullable=False)
    description = db.Column(String(1200))
    task_type = db.Column(String(20), nullable=False, default="task")
    status = db.Column(String(20), nullable=False, default="not_started")
    owner_label = db.Column(String(120))
    due_at = db.Column(DateTime(timezone=True))
    due_local_date = db.Column(Date)
    phase = db.Column(String(80))
    priority = db.Column(String(12), nullable=False, default="medium")
    source = db.Column(String(32), nullable=False)
    completion_source = db.Column(String(16))
    vendor_id = db.Column(String(36))
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = db.Column(DateTime(timezone=True))
    completed_by_session_id = db.Column(String(36))

    plan_version = db.relationship("EventPlanVersion", back_populates="tasks")
    dependencies = db.relationship(
        "TaskDependency",
        foreign_keys="[TaskDependency.event_version_id, TaskDependency.task_id]",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskDependency(db.Model):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        PrimaryKeyConstraint("event_version_id", "task_id", "depends_on_task_id"),
        ForeignKeyConstraint(
            ["event_version_id", "task_id"],
            ["tasks.event_version_id", "tasks.logical_id"],
            name="fk_task_dependencies_task_same_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["event_version_id", "depends_on_task_id"],
            ["tasks.event_version_id", "tasks.logical_id"],
            name="fk_task_dependencies_parent_same_version",
            ondelete="CASCADE",
        ),
        CheckConstraint("task_id <> depends_on_task_id", name="not_self_dependent"),
        CheckConstraint("dependency_type = 'finish_to_start'", name="dependency_type_valid"),
        CheckConstraint("lag_minutes >= 0", name="lag_nonnegative"),
        Index("ix_task_dependencies_version_parent", "event_version_id", "depends_on_task_id"),
    )

    event_version_id = db.Column(String(36), nullable=False)
    task_id = db.Column(String(36), nullable=False)
    depends_on_task_id = db.Column(String(36), nullable=False)
    dependency_type = db.Column(String(24), nullable=False, default="finish_to_start")
    lag_minutes = db.Column(Integer, nullable=False, default=0, server_default="0")

    task = db.relationship("Task", foreign_keys=[event_version_id, task_id], back_populates="dependencies")


class RippleSimulation(db.Model):
    __tablename__ = "ripple_simulations"
    __table_args__ = (
        UniqueConstraint("event_id", "commit_idempotency_key", name="uq_ripple_simulations_commit_key"),
        UniqueConstraint("id", "event_id", name="uq_ripple_simulations_id_event"),
        ForeignKeyConstraint(
            ["event_id", "owner_session_id"],
            ["events.id", "events.owner_session_id"],
            name="fk_ripple_simulations_event_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["event_id", "base_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_ripple_simulations_base_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["event_id", "committed_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_ripple_simulations_committed_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('ready','committed','cancelled','expired','stale','rejected')", name="status_valid"),
        CheckConstraint("base_revision >= 0", name="base_revision_nonnegative"),
        Index("ix_ripple_simulations_owner_base_status", "owner_session_id", "event_id", "base_version_no", "status"),
        Index("ix_ripple_simulations_expiry", "expires_at"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    event_id = db.Column(String(36), nullable=False)
    owner_session_id = db.Column(String(36), nullable=False)
    base_version_no = db.Column(Integer, nullable=False)
    base_revision = db.Column(Integer, nullable=False)
    engine_version = db.Column(String(40), nullable=False)
    input_patch_json = db.Column(JSON, nullable=False)
    preview_json = db.Column(JSON, nullable=False)
    preview_hash = db.Column(String(64), nullable=False)
    status = db.Column(String(16), nullable=False, default="ready")
    blockers_json = db.Column(JSON, nullable=False, default=list)
    warnings_json = db.Column(JSON, nullable=False, default=list)
    expires_at = db.Column(DateTime(timezone=True), nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    committed_version_no = db.Column(Integer)
    commit_idempotency_key = db.Column(String(128))
    committed_at = db.Column(DateTime(timezone=True))


class ScenarioSimulation(db.Model):
    __tablename__ = "scenario_simulations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "owner_session_id"],
            ["events.id", "events.owner_session_id"],
            name="fk_scenario_simulations_event_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["event_id", "base_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_scenario_simulations_base_version",
            ondelete="CASCADE",
        ),
        Index("ix_scenario_simulations_owner_base_created", "owner_session_id", "event_id", "base_version_no", "created_at"),
        Index("ix_scenario_simulations_expiry", "expires_at"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    event_id = db.Column(String(36), nullable=False)
    owner_session_id = db.Column(String(36), nullable=False)
    base_version_no = db.Column(Integer, nullable=False)
    request_json = db.Column(JSON, nullable=False)
    result_json = db.Column(JSON, nullable=False)
    engine_version = db.Column(String(40), nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = db.Column(DateTime(timezone=True))


class PlanChangeReceipt(db.Model):
    __tablename__ = "plan_change_receipts"
    __table_args__ = (
        ForeignKeyConstraint(["event_version_id"], ["event_plan_versions.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["simulation_id"], ["ripple_simulations.id"], ondelete="SET NULL"),
        UniqueConstraint("simulation_id", name="uq_plan_change_receipts_simulation"),
    )

    event_version_id = db.Column(String(36), primary_key=True)
    simulation_id = db.Column(String(36))
    trigger_summary = db.Column(String(600), nullable=False)
    changes_json = db.Column(JSON, nullable=False)
    reason_trail_json = db.Column(JSON, nullable=False)
    acknowledged_warning_codes_json = db.Column(JSON, nullable=False, default=list)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AIUsageRecord(db.Model):
    __tablename__ = "ai_usage_records"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_ai_usage_records_request_id"),
        ForeignKeyConstraint(
            ["event_id", "session_id"],
            ["events.id", "events.owner_session_id"],
            name="fk_ai_usage_records_event_owner",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["event_id", "plan_version_no"],
            ["event_plan_versions.event_id", "event_plan_versions.version_no"],
            name="fk_ai_usage_records_plan_version",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(["session_id"], ["guest_sessions.id"], ondelete="SET NULL"),
        CheckConstraint(
            "operation IN ('extract_event_requirements','generate_event_blueprint','generate_personalized_ideas',"
            "'suggest_event_tasks','suggest_vendor_checklist','explain_ripple_results','answer_event_question')",
            name="operation_valid",
        ),
        CheckConstraint("reasoning_effort IN ('low','medium','high')", name="reasoning_effort_valid"),
        CheckConstraint("status IN ('success','refusal','invalid_output','incomplete','timeout','provider_error','rate_limited')", name="status_valid"),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="input_tokens_nonnegative"),
        CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="output_tokens_nonnegative"),
        CheckConstraint("estimated_cost_minor IS NULL OR estimated_cost_minor >= 0", name="estimated_cost_nonnegative"),
        CheckConstraint("latency_ms >= 0", name="latency_nonnegative"),
        Index("ix_ai_usage_records_created_operation_status", "created_at", "operation", "status"),
        Index("ix_ai_usage_records_session_created", "session_id", "created_at"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    request_id = db.Column(String(36), nullable=False)
    session_id = db.Column(String(36))
    event_id = db.Column(String(36))
    plan_version_no = db.Column(Integer)
    operation = db.Column(String(40), nullable=False)
    model_id = db.Column(String(80), nullable=False, default="gpt-6-luna")
    reasoning_effort = db.Column(String(8), nullable=False)
    status = db.Column(String(24), nullable=False)
    input_tokens = db.Column(Integer)
    output_tokens = db.Column(Integer)
    estimated_cost_minor = db.Column(Integer)
    pricing_config_version = db.Column(String(80))
    latency_ms = db.Column(Integer, nullable=False)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AIQuotaBucket(db.Model):
    """Atomic UTC-day request reservations for a guest session."""

    __tablename__ = "ai_quota_buckets"
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "quota_day", name="pk_ai_quota_buckets"),
        ForeignKeyConstraint(["session_id"], ["guest_sessions.id"], ondelete="CASCADE"),
        CheckConstraint("reserved_count >= 0", name="reserved_count_nonnegative"),
    )

    session_id = db.Column(String(36), nullable=False)
    quota_day = db.Column(Date, nullable=False)
    reserved_count = db.Column(Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)


class IdempotencyRecord(db.Model):
    """Bounded mutation replay cache, scoped to session, route, and key."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("session_id", "route_scope", "idempotency_key", name="uq_idempotency_scope_key"),
        ForeignKeyConstraint(["session_id"], ["guest_sessions.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["event_id", "session_id"],
            ["events.id", "events.owner_session_id"],
            name="fk_idempotency_records_event_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("state IN ('pending','completed')", name="state_valid"),
        CheckConstraint("response_status IS NULL OR response_status BETWEEN 100 AND 599", name="response_status_valid"),
        Index("ix_idempotency_records_expiry", "expires_at"),
    )

    id = db.Column(String(36), primary_key=True, default=_uuid)
    session_id = db.Column(String(36), nullable=False)
    event_id = db.Column(String(36))
    route_scope = db.Column(String(160), nullable=False)
    idempotency_key = db.Column(String(128), nullable=False)
    request_digest = db.Column(String(64), nullable=False)
    state = db.Column(String(12), nullable=False, default="pending", server_default="pending")
    response_status = db.Column(Integer)
    response_json = db.Column(JSON)
    created_at = db.Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = db.Column(DateTime(timezone=True), nullable=False)


__all__ = [
    "AIQuotaBucket",
    "AIUsageRecord",
    "BudgetCategory",
    "BudgetItem",
    "Event",
    "EventDetails",
    "EventPlanVersion",
    "GuestSession",
    "IdempotencyRecord",
    "PlanChangeReceipt",
    "RippleSimulation",
    "ScenarioSimulation",
    "Task",
    "TaskDependency",
    "Vendor",
    "VendorQuote",
    "utc_now",
]
