# MomentOS — Database Schema

**Status:** Frozen logical schema for implementation. Physical SQL types may vary by SQLite/PostgreSQL adapter but must preserve the constraints below.

## Storage conventions

- Use SQLAlchemy models and Alembic migrations. IDs are UUIDs serialized as canonical strings unless the selected portable SQLAlchemy UUID type works consistently in both supported databases.
- Store timestamps as timezone-aware UTC instants. API event-local date/time data must retain the IANA timezone.
- Store monetary values as signed integer minor units and ISO-4217 currency code. Enforce nonnegative amounts where the domain does not allow credits. Do not store authoritative currency in floating point.
- Store user-authored and accepted plan data in normalized relational tables. JSON is reserved for bounded, versioned input/output snapshots and configuration values that do not need relational querying.
- Each event plan version is immutable after insertion. A mutation clones the relevant aggregate into a new version; stable logical IDs connect the same conceptual row across versions.
- All event data is owned through its event’s guest session. Queries must join/verify the owner session before accessing child rows. UUID unpredictability is not authorization.
- SQLite connections must enable foreign-key enforcement. Test both SQLite behavior and PostgreSQL migrations/constraints before production.

## Entity relationship overview

GuestSession 1—many Event. Event 1—many EventPlanVersion and has one current version number. EventPlanVersion 1—many EventDetails, BudgetCategory, BudgetItem, Task, TaskDependency, Vendor, VendorQuote, and PlanChangeReceipt. RippleSimulation and ScenarioSimulation reference an event and base version; AIUsageRecord references the session and optionally event/version. Simulations and usage are operational records, not plan snapshots.

## Tables

### guest_sessions

| Column | Type / rule | Purpose |
|---|---|---|
| id | UUID primary key | Internal owner identifier. |
| token_hash | fixed-length hash, unique, not null | Hash of high-entropy opaque browser session token; never store raw token. |
| csrf_hash | fixed-length hash, not null | Hash for CSRF double-submit validation. |
| created_at, last_seen_at, expires_at | UTC timestamp, not null | Session lifecycle. |
| revoked_at | nullable UTC timestamp | Revocation without exposing token. |
| schema_version | small integer, not null | Session credential rotation/version. |

Index `expires_at`; unique `token_hash`. Recommended initial policy: sliding 30-day inactivity expiry, bounded by a 180-day absolute lifetime; rotate credentials on renewal and purge expired sessions and owned events after the documented retention window. Implementation must make retention configurable and test expiry. No email or identity provider is required for the guest-session MVP.

### events

| Column | Type / rule | Purpose |
|---|---|---|
| id | UUID primary key | Event identifier. |
| owner_session_id | FK guest_sessions.id, not null, indexed | Ownership. |
| event_type | enum/check: wedding, birthday, community | Supported event kind. |
| title | bounded text, not null | User-visible name. |
| currency | ISO code, not null | Event currency. |
| budget_limit_minor | nonnegative integer, nullable | Null means not supplied; not zero. |
| event_date | date, nullable | Local event date if known. |
| timezone | bounded IANA zone, nullable | Required when time-of-day schedule is used. |
| location_label | bounded text, nullable | User-entered place label, not a verified venue. |
| current_plan_version_no | positive integer, nullable until first commit | Current accepted snapshot pointer. |
| revision | positive integer, not null default 0 | Monotonic concurrency revision; increments on every committed mutation. |
| created_at, updated_at, deleted_at | UTC timestamps | Lifecycle; soft-delete policy for events. |

Constraint: `(id, current_plan_version_no)` references `event_plan_versions(event_id, version_no)` with deferred/nullable semantics where supported. Event type and currency are validated at API boundaries. Index `(owner_session_id, updated_at)` and `(owner_session_id, id)`. Before an accepted version exists, event columns hold the user-entered draft fields. After a version exists, these columns are a transactionally maintained current-summary projection; the immutable version snapshot is the source of truth for historical reads and Ripple calculations.

### event_plan_versions

| Column | Type / rule | Purpose |
|---|---|---|
| id | UUID primary key | Snapshot identifier used by child rows. |
| event_id | FK events.id, not null | Aggregate owner. |
| version_no | positive integer, not null | Per-event monotonically increasing version. |
| base_version_no | nullable positive integer | Previous version; null for initial version. |
| change_kind | enum/check: initial_plan, user_edit, ripple_commit | Audit classification. |
| event_type | enum/check: wedding, birthday, community | Versioned event type. |
| title | bounded text, not null | Versioned event title. |
| currency | ISO code, not null | Snapshot currency. |
| created_at | UTC timestamp, not null | Commit time. |
| created_by_session_id | FK guest_sessions.id, not null | Confirming owner; must equal event owner in service validation. |
| source_simulation_id | nullable UUID | Ripple simulation that produced this version, if any. |
| change_summary | bounded text, nullable | User-facing summary; no raw prompt. |

Unique `(event_id, version_no)` and `(id, event_id)`. Index `(event_id, version_no DESC)`. A version row and all child snapshot rows are inserted in one transaction; no update/delete to prior plan rows except event retention purge.

### event_details

One row per plan version, linked by version ID. Stores optional user-provided and accepted fields: `event_version_id` PK/FK, `budget_limit_minor` nullable nonnegative integer, `event_date` nullable date, `timezone` nullable IANA zone, `location_label` bounded nullable text, `guest_count` nullable nonnegative integer, `guest_count_source` enum (`user`, `accepted_ai_suggestion`, `demo_assumption`), `venue_capacity` nullable nonnegative integer, `venue_capacity_source`, `seats_per_table` nullable positive integer, `invitation_unit` enum/null (`person`, `household`, `unknown`), `accessibility_notes` bounded nullable text, `preferences_json` bounded JSON, `constraints_json` bounded JSON, `created_at`. Preserve provenance per field or in a validated field-source map; do not mark model-suggested values as user-provided. A missing value remains null. Currency and event type/title are captured on the corresponding `event_plan_versions` row.

### budget_categories

| Column | Type / rule | Purpose |
|---|---|---|
| event_version_id | FK version, not null | Snapshot membership. |
| logical_id | UUID, not null | Stable category identity across versions. |
| name | bounded text, not null | Category label. |
| planned_minor | nonnegative integer, nullable | Optional category target; null means unset. |
| sort_order | nonnegative integer | Display order. |
| source | enum: user, accepted_ai_suggestion, demo_assumption | Provenance. |
| is_required | boolean | User/domain requirement. |

Composite primary key `(event_version_id, logical_id)`. Currency is inherited from the event, never duplicated inconsistently.

### budget_items

Columns: `event_version_id`, `logical_id`, `category_id`, `label`, `quantity` nullable positive decimal with fixed scale, `unit_rate_minor` nullable nonnegative integer, `planned_minor` nonnegative integer, `actual_minor` nullable nonnegative integer, `status` enum (`illustrative_estimate`, `user_estimate`, `quoted_by_user`, `confirmed_by_user`, `paid_by_user`), `source_note` nullable bounded text, `created_at`.

Composite PK `(event_version_id, logical_id)`. Composite FK `(event_version_id, category_id)` to `budget_categories(event_version_id, logical_id)`. Amounts are authoritative at item level; when quantity × unit rate is shown, the server applies documented integer rounding and stores/recomputes the total deterministically. Never infer a vendor quotation from an estimate.

### tasks

Columns: `event_version_id`, `logical_id`, `title`, `description` nullable bounded text, `task_type` enum (`task`, `milestone`, `event_activity`), `status` enum (`not_started`, `in_progress`, `blocked`, `completed`), `owner_label` nullable bounded text, `due_at` nullable UTC timestamp, `due_local_date` nullable date, `phase` nullable bounded text, `priority` enum, `source` enum (`user`, `accepted_ai_suggestion`, `demo_assumption`), `completion_source` nullable enum (`user` only in MVP), `vendor_id` nullable logical vendor reference, `created_at`.

Composite PK `(event_version_id, logical_id)`. `vendor_id` references `(event_version_id, vendors.logical_id)` so a task cannot link to a vendor in another version. Include nullable `completed_at` and `completed_by_session_id` fields; a completed status requires a user actor/timestamp. AI-created tasks must start not_started, no owner, and no completion. Index `(event_version_id, due_at)` and `(event_version_id, status)`.

### task_dependencies

Columns: `event_version_id`, `task_id`, `depends_on_task_id`, `dependency_type` (`finish_to_start` in MVP), optional nonnegative `lag_minutes` default 0.

Composite PK `(event_version_id, task_id, depends_on_task_id)`. Both composite FKs target tasks in the same version. Reject self-dependency and any cycle in application validation; database FKs prevent cross-version references. Index `(event_version_id, depends_on_task_id)`.

### vendors

Columns: `event_version_id`, `logical_id`, `category`, `display_name` nullable, `contact_name` nullable, `email` nullable, `phone` nullable, `location_note` nullable, `status` enum (`to_find`, `contacted_by_user`, `shortlisted_by_user`, `selected_by_user`, `declined_by_user`), `information_source` enum (`checklist_suggestion`, `user_entered`), `notes` bounded nullable text, `created_at`.

Composite PK `(event_version_id, logical_id)`. A suggested vendor category can have no identity/contact fields. User entry is not verification. No scraped or fabricated contact details.

### vendor_quotes

Columns: `event_version_id`, `logical_id`, `vendor_id`, `amount_minor` nonnegative integer, `currency`, `quote_date` nullable date, `valid_until` nullable date, `scope_note` bounded text, `source` fixed to `user_entered`, `status` enum (`received_by_user`, `accepted_by_user`, `rejected_by_user`), `created_at`.

Composite PK `(event_version_id, logical_id)`. Composite FK to vendor in same version. Currency must equal event currency unless an explicitly implemented conversion feature records source/target/rate/date; currency conversion is out of MVP. Store quote expiry only as user-entered; never claim verification.

### ripple_simulations

Columns: `id` UUID PK, `event_id` FK, `owner_session_id` FK, `base_version_no`, `base_revision`, `engine_version`, `input_patch_json`, `preview_json`, `preview_hash`, `status` (`ready`, `committed`, `cancelled`, `expired`, `stale`, `rejected`), `blockers_json`, `warnings_json`, `expires_at`, `created_at`, `committed_version_no` nullable, `commit_idempotency_key` nullable, `committed_at` nullable.

Unique `(event_id, commit_idempotency_key)` where key is not null. FK `(event_id, base_version_no)` to event version. FK to committed version similarly. All reads verify both `owner_session_id` and the event’s actual owner. Persist only the minimum normalized input and immutable calculated result required to display and confirm; no raw AI prompt. Preview expiry recommendation: 15 minutes. A ready preview never changes events or plan rows.

### scenario_simulations

Columns: `id` UUID PK, `event_id`, `owner_session_id`, `base_version_no`, `request_json` (bounded named alternatives/patches), `result_json` (deterministic projections), `engine_version`, `created_at`, `expires_at` optional.

FK to event/base version; ownership enforced on every read. Scenarios are read-only and do not create event plan versions. Cap alternatives and patch size in API validation. No model output is treated as a calculation.

### plan_change_receipts

One receipt per committed plan version: `event_version_id` PK/FK, `simulation_id` nullable unique FK, `trigger_summary`, `changes_json` (bounded typed before/after records), `reason_trail_json` (calculation rule IDs and affected entity IDs), `acknowledged_warning_codes_json`, `created_at`. A receipt describes a committed change; it does not claim external work occurred.

### ai_usage_records

Columns: `id` UUID PK, `request_id` unique, `session_id` FK nullable, `event_id` FK nullable, `plan_version_no` nullable, `operation` enum (the seven named AI operations), `model_id`, `reasoning_effort`, `status` (`success`, `refusal`, `invalid_output`, `incomplete`, `timeout`, `provider_error`, `rate_limited`), `input_tokens` nullable nonnegative, `output_tokens` nullable nonnegative, `estimated_cost_minor` nullable, `pricing_config_version` nullable, `latency_ms` nonnegative, `created_at`.

Do not store raw input, raw response, secret values, or unnecessary personal data. A pricing table/config snapshot is owned by the application release, not hard-coded from an undocumented rate. Set session/event/version references null on purge. Index `(created_at, operation, status)` and `(session_id, created_at)` for operational limits and usage views.

## Ownership, versioning, deletion, and concurrency

1. Start each protected request by resolving the opaque cookie to a live session; reject revoked/expired sessions.
2. Load the event with `events.id = requested_id AND owner_session_id = session.id AND deleted_at IS NULL`. Return the same not-found contract for absent and foreign-owned IDs.
3. Load plan children only through the selected event version. Never accept a client-supplied owner ID.
4. For a version commit, within one transaction verify the expected revision, insert the next version and copied/changed child rows, then conditionally update `events.current_plan_version_no` and `revision`. Require exactly one affected event row. PostgreSQL may use SELECT FOR UPDATE; SQLite uses a write transaction plus compare-and-swap. Retry only the whole safe transaction on a recognized serialization conflict.
5. Clone all unchanged child snapshot rows with their logical IDs; use new logical IDs only for new conceptual entities. Composite version FKs keep dependencies and vendor links within one snapshot.
6. Event deletion is a soft delete first; session expiry/purge follows a documented retention policy and cascades plan snapshots/simulations. AI usage is de-identified and detached. Do not cascade a single version edit into destruction of history.

## Index and migration checklist

Required unique/check/FK constraints are listed above. Add indexes for session expiry, event owner/recent list, event version lookup, task date/status, simulation owner/base/status/expiry, and usage date/operation. Keep migrations reversible where practical, use Alembic batch operations for SQLite alterations, and test a fresh database plus upgrade from the prior released schema on SQLite and PostgreSQL. Never rely only on ORM relationship checks for ownership or same-version integrity.
