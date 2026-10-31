# MomentOS — Ripple Engine Specification

**Status:** Frozen deterministic preview/commit contract. Financial and dependency results are Python application logic, never model authority.

## Purpose and invariants

Ripple Engine answers “why did the plan change?” for a proposed edit. It calculates direct and downstream effects, shows evidence and unknown inputs, offers editable alternatives, and persists nothing to the event until explicit confirmation.

Invariants:

1. Simulation is a pure deterministic function of a canonical plan snapshot, an allowlisted patch, and a versioned rule/config set.
2. Identical normalized inputs and engine version produce identical result objects and preview hashes.
3. Money uses integer minor units and a documented rounding rule; calculations never rely on binary float or AI arithmetic.
4. Unknown is distinct from zero. The engine never fills capacity, price, seating, or invitation rules from a default unless the default is explicit in the event snapshot and labeled as an assumption.
5. Preview is immutable and cannot update event/version rows. Saving a preview record is allowed only to support confirmation and audit.
6. Commit requires explicit confirmation, current ownership, unexpired ready preview, matching base version/revision, a matching recomputation, and a transactionally successful compare-and-swap.
7. Hard constraints cannot be overridden by AI or a warning acknowledgement. The user may edit the plan/constraint and create a new preview.
8. A simulation never marks work done, sends invitations, books vendors, changes user-entered quote provenance, or triggers an external side effect.

## Pure calculation interface

Conceptual boundary:

- `simulate(snapshot, proposed_changes, rule_config) -> RipplePreview`
- `validate_snapshot(snapshot, rule_config) -> ValidationReport`
- `apply_changes(snapshot, normalized_changes) -> CandidateSnapshot`
- `commit_preview(session, event_id, simulation_id, confirmation, expected_etag, idempotency_key) -> VersionedEvent`

The first three are pure: no database, network, clock, global mutable state, or model calls. Pass simulation time/expiry separately from calculation so tests remain deterministic. The commit service handles ownership and transactional persistence and re-runs pure functions against the current version.

## Input and normalization

Input snapshot is the full accepted plan version: event type/date/timezone/currency/budget limit; attendance; configured capacity/seating assumptions; budget categories/items and provenance; tasks/dependencies; vendor categories/records/quotes; hard/soft constraints; and current version/revision identifiers.

Proposed changes use an allowlist of typed scalar fields such as guest count, budget limit, line-item rate/amount, venue capacity, seats per table, and task due date. Each field validator defines units, nullability, bounds, whether it is hard/soft, and affected node types. Reject arbitrary paths, duplicate conflicting patches, unknown IDs, NaN/infinity, negative values where disallowed, wrong currency, malformed timezones, and patch sizes above configured limits.

Normalization sorts unordered patch elements, canonicalizes dates/timezones and currency, normalizes decimal quantities to fixed precision, and records the user-supplied value/source. The patch never silently converts an unknown into a default.

## Dependency graph and affected subgraph

Represent calculation nodes as typed `(kind, logical_id or event-key)` identifiers. Edges are directed from an input/cause to a derived value or operational follow-up. Example:

`guest_count → catering quantity → catering planned amount → category total → event total → budget variance`

`guest_count → seating requirement → table count → venue capacity check`

`guest_count → invitation quantity` only when an explicit invitation unit/household rule is configured.

`changed category/item → linked budget review task/vendor follow-up`

`task due date/dependency → successor earliest start/latest finish → schedule conflict`

Algorithm:

1. Validate base snapshot integrity and proposed patch.
2. Apply normalized changes to an in-memory candidate snapshot.
3. Seed a queue with changed source nodes; traverse downstream edges to form the affected subgraph.
4. Topologically sort the affected subgraph using stable node-ID tie breaks. A cycle is a validation failure, never silently truncated.
5. Recompute derived nodes using registered deterministic functions. Reuse unchanged derived values only when their input fingerprint and rule version match.
6. Evaluate event-wide constraints that can be affected even if not direct descendants (budget ceiling, venue capacity, hard date window, task graph validity).
7. Emit changes only when typed before/after values differ; preserve unit, source, and rule ID.
8. Emit causal trail entries linking trigger → rule → calculated output → affected task/vendor/constraint.
9. Serialize a canonical immutable preview and hash it with engine/rule version, base version, normalized patch, and result.

Graph nodes and rule functions must be inspectable and unit-testable. AI may paraphrase a trail but cannot add dependencies or change affected IDs.

## Deterministic calculations

### Budget

- Category total is the sum of its included planned line items plus any explicit category-level amount policy; choose one source of truth and do not double count. Recommended rule: line items are authoritative when present; an explicitly planned category remainder is a separate line item.
- Event planned total is the sum of planned line items across categories. Actual total is the sum of user-entered actuals only; it is not used to fabricate estimates.
- Remaining budget = limit − planned total. Variance = planned total − limit. Positive variance is over budget.
- Per-person amount = integer minor-unit rate × nonnegative integer quantity. If fractional quantities are supported, normalize a fixed decimal scale and round half-up once at line-item total. Record rule version and display units.
- For wedding demo: 150 people × ₹1,000/person = ₹1,50,000 catering. At 200, catering is ₹2,00,000 (+₹50,000), planned total ₹6,30,000 from ₹5,80,000, and overage ₹30,000 against ₹6,00,000.

### Capacity and seating

- If attendance exceeds configured venue capacity, emit a hard blocker (`venue_capacity_exceeded`) and do not permit commit until attendance/capacity/venue changes resolve it. If capacity is absent, emit `capacity_unknown`; this is an unknown, not a pass.
- Required table count = ceiling(guest_count / seats_per_table) when seats_per_table is explicitly configured. If missing, show “needs input.”
- No inference of safety, permits, accessibility compliance, or venue adequacy from attendance alone.

### Invitations

- Quantity follows configured invitation unit: one per person or one per household only with an explicit household count/rule. If not supplied, show `invitation_quantity_unknown` and the affected invitation task; do not assume one invitation per guest.

### Tasks and schedule

- Reject self-dependencies, missing dependency IDs, cross-version dependencies, and directed cycles.
- For finish-to-start dependencies, successor earliest start must be at or after predecessor finish plus configured lag. An explicit date earlier than this is a schedule conflict.
- Required event-date bounds and task lead-time constraints are evaluated in the event timezone. Unknown event date/timezone produces incomplete schedule status rather than invented dates.
- Hard date windows and dependency integrity block commit; soft overdue/follow-up warnings can be confirmed when no hard rule is violated.
- Any plan change that invalidates a completed task’s underlying assumptions emits a blocker requiring user review; do not automatically reopen or mark complete without explicit user edit.

### Vendor/task effects

Vendor categories and follow-up tasks are linked by stable logical IDs. When a changed assumption affects an existing category/task, mark it affected and explain why. When a newly needed category is suggested, show it as a proposed checklist entry with no vendor identity, quote, or selected status. Do not synthesize contacts or bookings.

## Preview response contract

Immutable result fields: `simulation_id`, `event_id`, `base_version_no`, `base_revision`, `engine_version`, `rule_config_version`, `created_at`, `expires_at`, `normalized_changes[]`, `changes[]` with entity/field/before/after/unit/source, `causal_trail[]` with trigger/rule/input/output/affected IDs/plain explanation, `budget_summary`, `capacity_summary`, `schedule_conflicts[]`, `affected_task_ids[]`, `affected_vendor_ids[]`, `unknowns[]`, `warnings[]`, `blockers[]`, `commit_allowed`, canonical `preview_hash`.

The preview is returned unchanged on later reads. Any optional AI explanation is stored separately with operation/model/status and is never embedded as calculated truth. A user edits a suggestion by producing a new typed patch and rerunning simulation.

## Constraint severity

**Invalid input blockers:** malformed or out-of-range values, invalid currency, missing referenced entity, invalid/cyclic dependency graph. Cannot preview as committable.

**Hard constraint blockers:** explicit hard budget limit exceeded; configured venue capacity exceeded; required schedule/date bound violated; dependent task integrity broken; unresolved invalidation of a completed task. `commit_allowed=false`; acknowledgement cannot bypass. User changes the relevant value/constraint and requests a new preview.

**Warnings:** missing optional rate/capacity/invitation rule, incomplete but non-blocking schedule data, unknown vendor quotation, soft budget target warning, or affected follow-up requiring attention. Commit may proceed only when policy permits, with explicit acknowledgment of required warning codes.

This severity split preserves the Stage 01/02 promise that hard budget and timeline constraints are not bypassed, while allowing incomplete optional facts to remain visible in a plan.

## Commit protocol and stale simulation detection

1. Resolve live owner session, verify CSRF/Origin, idempotency key, route event ownership, and explicit `confirmed=true`.
2. Begin transaction. Lock event row in PostgreSQL where available; SQLite begins a write transaction. Load current version and compare the supplied If-Match revision, simulation base version/revision, owner, status, and expiry.
3. If simulation was committed with the same idempotency key, return its stored receipt. If a different commit key targets an already committed simulation, return conflict.
4. Load immutable base snapshot and current snapshot. Require current equals preview base; otherwise mark stale and return 412. Never rebase a preview silently.
5. Revalidate input patch and recompute pure simulation with the recorded engine/rule version. Require canonical hash/result equal the stored preview. If rule implementation/config changed, mark stale and require a new preview.
6. If blockers exist or warning acknowledgments are missing, rollback and return a typed conflict. Do not persist partial rows.
7. Clone the accepted snapshot into next version, apply normalized changes, create plan change receipt, update event current version/revision with compare-and-swap, and mark simulation committed with new version and commit idempotency key.
8. Commit transaction. Return the new ETag/version/receipt. On serialization/deadlock conflict, retry the complete transaction only within a small bounded policy; otherwise return stale/conflict for user reload.

Cancel is an explicit state transition to cancelled; it does not mutate event version. Expiry is checked on both read and commit. A stale or expired preview can be viewed as history if retention allows, but cannot be committed. The user must run a fresh preview.

## Scenario comparison

Scenario Comparison calls the same pure simulation engine independently for up to three labeled patches against one immutable base version. It returns normalized projections and differences in a comparison table; no scenario applies and no preview is promoted to commit. If a user chooses an alternative, create a fresh ordinary Ripple preview and confirm it through the normal commit protocol.

## Failure and audit behavior

Return typed errors for invalid patch, hard blocker, stale version, expired preview, ownership failure, duplicate idempotency mismatch, and transaction conflict. Keep preview unchanged on failure; avoid leaking whether a foreign event/simulation exists. Record engine version and safe calculation rule IDs. Do not log sensitive notes or raw AI explanation input. Usage records contain no secrets.
