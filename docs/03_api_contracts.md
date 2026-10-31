# MomentOS — API and Frontend Contracts

**Status:** Frozen version 1 wire contract. JSON over same-origin HTTPS. All examples use conceptual field names; Pydantic models and TypeScript types must preserve these names, null semantics, enums, and units.

## Conventions

- Base path: `/api/v1`; content type `application/json; charset=utf-8`; UTF-8; UUID identifiers; ISO date and UTC timestamp strings.
- Money uses integer minor units and an ISO currency code. Missing values are null, never silently zero.
- Success response shape is `{ "data": <typed-value>, "request_id": "uuid" }`. List values include `items` and a nullable `next_cursor` when pagination applies.
- Error response shape is `{ "error": { "code": "stable_code", "message": "safe user-facing message", "fields": [{"path":"...","code":"...","message":"..."}] }, "request_id":"uuid" }`. Omit fields when irrelevant. Never return traceback, prompt, credential, SQL, or raw provider error.
- Protected browser requests use the HttpOnly session cookie and `X-CSRF-Token` on every state-changing method. Check Origin/Referer against configured same-origin allowlist as defense in depth. Do not accept an owner/session ID in request bodies.
- Every event response carries `ETag: "event:<uuid>:r<revision>:v<version>"`; a draft without an accepted plan uses the literal version marker `none`. Mutations require that exact value in `If-Match`; initial plan commit uses the draft ETag. Missing precondition is 428; stale revision is 412. A 409 is reserved for domain conflicts that are current but invalid.
- Mutation requests accept `Idempotency-Key` (UUID/random opaque string). Scope keys by session, route, and request digest; same key+same digest returns prior result; same key+different digest returns 409. Keep a bounded retention period.
- Default limits (configuration-backed): JSON body 256 KiB; natural-language description 12,000 characters; question 4,000; max page 100; max task/dependency rows per event 500; max scenario alternatives 3; AI operations per session per minute and day are server-configured. Enforce before provider calls.
- AI generation is synchronous with explicit pending/loading UI. The client may abort its wait, but cancellation is not a guarantee that provider work stopped. Idempotency and explicit user actions prevent accidental repeated requests.

## Common request/response types

### Session

Session creation has no request body. Response data: `{ "csrf_token": "opaque-token", "expires_at": "ISO-8601" }`. Session cookie: opaque random token, Secure in production, HttpOnly, SameSite=Lax (Strict if navigation flow permits), Path=/, bounded Max-Age; never return the session token in JSON. CSRF token is returned to the same-origin client and retained in memory. `GET /session` returns `{ "authenticated": true, "expires_at": "...", "csrf_token": "..." }` after a refresh. `DELETE /session` requires CSRF and revokes the session, clears cookie, and returns 204.

### Event and plan primitives

Event creation request: `{ "event_type":"wedding|birthday|community", "title":"...", "currency":"INR", "budget_limit_minor":60000000, "event_date":"YYYY-MM-DD|null", "timezone":"Asia/Kolkata|null", "location_label":"Nagpur|null", "guest_count":150|null, "preferences":{...}, "constraints":{...} }`. INR amounts use paise: ₹6,00,000 = 60,000,000 minor units. The display layer formats for humans.

Event representation includes `id`, `event_type`, `title`, `currency`, `budget_limit_minor`, `event_date`, `timezone`, `location_label`, `current_version_no|null`, `revision`, `created_at`, `updated_at`, and compact current summary if requested.

Plan draft response is an uncommitted typed object: `event_brief`, `concept`, `assumptions[]`, `unknowns[]`, `budget_categories[]`, `budget_items[]`, `tasks[]`, `dependencies[]`, `vendor_categories[]`, `ideas[]`, `validation[]`, `ai_status`. Each field carries provenance/source where applicable. It has no server-side write authority.

## Versioned REST endpoints

| Method and path | Request | Response and behavior |
|---|---|---|
| POST `/session` | None | 201; set cookie; return CSRF token and expiry. Reuse an existing valid session instead of creating unnecessary identities. |
| GET `/session` | None | 200 current session metadata and refreshed CSRF token. |
| DELETE `/session` | CSRF header | 204; revoke and clear cookie. |
| GET `/health/live` | None | 200 process liveness only; no credentials or dependencies exposed. |
| GET `/health/ready` | None | 200 readiness with generic component states; checks database/migrations and AI configuration shape, not a paid model call. 503 if required dependencies/configuration are unusable. |
| GET `/events?limit=&cursor=` | Pagination | 200 owned event summaries only, ordered by updated_at/id. |
| POST `/events` | Event creation schema | 201 event with ETag. Creates a draft event container, not a generated/committed plan. |
| GET `/events/{event_id}` | Optional `?include=summary` | 200 owned event, current version and ETag; 404 indistinguishable from foreign-owned. |
| PATCH `/events/{event_id}` | Partial editable event fields | 200 updated event; If-Match required; creates a new plan version when changing a versioned field. Metadata-only update increments revision under same policy. |
| DELETE `/events/{event_id}` | Empty body | 204 soft-delete; If-Match required when versioned; ownership/CSRF enforced. |
| POST `/events/{id}/intake` | `{ "description":"...", "known_fields":{...} }` | 200 typed extraction candidate, missing questions, uncertainties, `ai_status`. Does not persist event changes. |
| POST `/events/{id}/plan-drafts` | `{ "brief":{...}, "include":["concept","budget","tasks","vendors","ideas"] }` | 200 typed blueprint draft. No database write. Exactly GPT-6 Luna in live mode; offline mode is explicitly identified. |
| POST `/events/{id}/plan-commits` | `{ "base_version_no":null|N, "confirmed":true, "plan":<PlanDraft> }` | 201 initial version or 200 next version; requires If-Match and Idempotency-Key; server validates submitted/edited draft, checks hard constraints, writes all normalized rows atomically. `confirmed` must be true. |
| GET `/events/{id}/budget` | None | 200 current categories/items, derived category/event totals, remaining and variance, provenance, and ETag. Derived amounts are server-calculated. |
| PATCH `/events/{id}/budget` | `{ "category_changes":[], "item_changes":[], "add_categories":[], "add_items":[], "remove_ids":[] }` | 200 updated budget plus new version number and derived totals. Unknown IDs, cross-version IDs, negative values, or mismatched currency are rejected. |
| GET `/events/{id}/tasks?status=&from=&to=` | Filters | 200 tasks, dependencies, topological order, and conflict summary. |
| POST `/events/{id}/tasks` | Typed task fields and optional same-version dependency IDs | 201 task and new version. New task is incomplete. |
| PATCH `/events/{id}/tasks/{task_id}` | Partial task fields | 200 task/new version; changing status to completed requires a user action and audit actor. |
| DELETE `/events/{id}/tasks/{task_id}` | Empty | 204/new version if no remaining task depends on it; otherwise 409 with dependent IDs. |
| PUT `/events/{id}/tasks/{task_id}/dependencies` | `{ "depends_on_task_ids":["uuid"] }` | 200; replaces dependency set in a new version after cycle/date validation. |
| GET `/events/{id}/vendors` | Optional category/status filter | 200 current user-managed vendors/checklist and quote summaries; provenance included. |
| POST `/events/{id}/vendors` | Vendor category/contact/status/notes | 201 user-entered vendor record and new version. No external verification implied. |
| PATCH `/events/{id}/vendors/{vendor_id}` | Partial editable fields | 200 updated record/new version. |
| DELETE `/events/{id}/vendors/{vendor_id}` | Empty | 204/new version if no quote/task reference remains; otherwise 409 or explicit cascade operation. |
| POST `/events/{id}/vendors/{vendor_id}/quotes` | `{ "amount_minor":..., "currency":"INR", "quote_date":null, "valid_until":null, "scope_note":"..." }` | 201 user-entered quotation/new version. Never sourced from AI. |
| POST `/events/{id}/ripple-previews` | `{ "base_version_no":N, "changes":[...], "acknowledge_unknowns":false }` | 201 immutable simulation preview; requires current If-Match; no plan mutation. |
| GET `/events/{id}/ripple-previews/{simulation_id}` | None | 200 owned preview while retained; status and expiry included. |
| POST `/events/{id}/ripple-previews/{simulation_id}/commit` | `{ "confirmed":true, "acknowledged_warning_codes":[...] }` | 200 committed version/receipt; If-Match and Idempotency-Key required. Recomputes and compare-and-swaps in transaction. Hard blockers reject commit. |
| POST `/events/{id}/ripple-previews/{simulation_id}/cancel` | `{ "confirmed":false }` | 200 canceled preview; no event version change. |
| POST `/events/{id}/scenario-comparisons` | `{ "base_version_no":N, "scenarios":[{"name":"...","changes":[...]}] }` | 200 read-only deterministic alternative results. No commit. |
| POST `/events/{id}/copilot` | `{ "question":"...", "context_sections":[...] }` | 200 grounded answer, references to known field/task IDs, unknowns, recommendation flag, `ai_status`. Read-only. P1. |

All event routes first verify live session ownership and CSRF for mutation. `GET` AI operations that consume provider usage are still POST and rate limited. Deletes and writes require event preconditions. API schema includes explicit maximum lengths and enums; omitted optional field means unchanged in PATCH, while null clears a nullable field.

## Ripple wire contract

Accepted change item fields: `{ "target":"event|budget_item|task|vendor", "target_id":null|"uuid", "field":"guest_count|budget_limit_minor|unit_rate_minor|planned_minor|due_at|venue_capacity|seats_per_table|...", "value":<typed-scalar> }`. Only an allowlist of patchable fields is accepted. Arbitrary JSON paths are forbidden.

Preview response data: `simulation_id`, `base_version_no`, `base_revision`, `engine_version`, `expires_at`, `changes[]` (entity, field, before, after, unit), `causes[]` (trigger, rule_id, explanation, affected IDs), `budget_summary`, `capacity_summary`, `schedule_conflicts[]`, `affected_task_ids[]`, `affected_vendor_ids[]`, `unknowns[]`, `warnings[]`, `blockers[]`, `commit_allowed`, `preview_hash`. Values are produced deterministically. Optional AI prose is a separately labeled explanation and cannot replace these fields.

Commit response: event, new version, new ETag, immutable change receipt, acknowledged warning codes. Repeated same idempotency key returns the same result. Stale, expired, rejected, or committed previews cannot be committed again under a new key.

## Error codes and status mapping

| HTTP | Stable codes | Client behavior |
|---|---|---|
| 400 | `invalid_json`, `invalid_request`, `invalid_idempotency_key` | Show field-level errors; preserve user input. |
| 401 | `session_required`, `session_expired` | Create/renew session; retain only safe unsaved draft locally. |
| 403 | `csrf_failed`, `origin_rejected` | Refresh session token or show recoverable security error. |
| 404 | `not_found` | Do not reveal another session’s event existence. |
| 409 | `domain_conflict`, `idempotency_conflict`, `dependent_records_exist`, `hard_constraint_violation` | Show precise safe action; do not retry unchanged request. |
| 412 | `stale_event_version`, `stale_simulation` | Reload current event and create a fresh preview. |
| 413 | `request_too_large` | Explain input limit and preserve editing. |
| 415 | `unsupported_media_type` | Client defect or wrong content type. |
| 422 | `validation_failed`, `invalid_dependency_graph`, `ai_output_invalid` | Show validated errors; AI output failure offers a labeled retry/demo option. |
| 428 | `precondition_required` | Reload the ETag before mutating. |
| 429 | `rate_limited`, `ai_daily_limit` | Honor Retry-After; the daily AI quota resets at 00:00 UTC and returns the exact remaining seconds. Do not auto-loop. |
| 502 | `ai_provider_unavailable`, `ai_refused`, `ai_incomplete` | Preserve request; report GPT-6 Luna issue; no model substitution. |
| 504 | `ai_timeout` | Preserve work; offer explicit retry. |
| 500/503 | `internal_error`, `service_unavailable` | Safe message plus request ID; never expose internals. |

## Frontend routes and component boundaries

| Route | Screen and primary components |
|---|---|
| `/` | Landing/event list, DemoModeBanner, EventList, CreateEventAction. |
| `/events/new` | EventArchitect: EventBasicsForm, DescriptionInput, IntakeReview, BlueprintReview, UnknownsAndAssumptions. |
| `/events/:eventId` | EventCommandCenter: EventHeader, BudgetHealth, PlanningProgress (derived from tasks), NextActions, Milestones, VendorSummary, RecommendationPanel. |
| `/events/:eventId/budget` | BudgetStudio: category/item editor, provenance labels, totals, accessible chart plus table. |
| `/events/:eventId/map` | MomentMap: semantic task list/timeline, filters, dependency indicators, task editor. |
| `/events/:eventId/vendors` | VendorWorkspace: category checklist, user-entered contact/quote editor. |
| `/events/:eventId/ripple` | RippleWorkspace: change form, PreviewImpactTrail, BeforeAfterSummary, Warnings, RecommendationOptions, ConfirmDialog. |
| `/events/:eventId/scenarios` | ScenarioComparison, read-only P1. |

The Copilot is an event-scoped panel/dialog launched from event screens, not a separate generic chat home. Shared components: AppShell, EventNavigation, SessionBootstrap, ApiErrorBanner, LoadingState, EmptyState, OfflineDemoBadge, ConfirmationDialog, AccessibleChartSummary. Keep API/query state, editable form state, and transient preview state separate. Never optimistically show a mutation as saved before server success.

### UI states

Each API-backed screen must represent initial/loading, loaded, empty/incomplete, validation error, network/provider error, rate-limited, stale-version conflict, offline demo, and retry states as applicable. Preserve forms on error. Disable duplicate submits while a request is active, but retain accessible status announcements. An expired session must not erase the in-progress unsaved form.

### Accessibility and responsive behavior

Use semantic headings/landmarks/forms, visible labels, keyboard-accessible actions, visible focus, focus restoration in dialogs, field error associations, and live regions for async updates. Charts require a nearby textual summary/table. Do not use color alone for status. Respect reduced motion. Core flows must work at 320 CSS px and 200% zoom without horizontal page scrolling, and with keyboard/screen reader. Motion cannot obscure confirmation or warnings.

## Typed API client contract

Create one TypeScript client module exposing typed functions corresponding to the route table. Shared types mirror Pydantic response models; use a discriminated `ApiResult<T>` or typed exception with `status`, stable `code`, field errors, request ID, and retry-after. The client must:

1. Use relative same-origin URLs, `credentials: "same-origin"`, JSON content headers, and a CSRF token held in memory for mutations.
2. Obtain/refresh session before protected requests and refresh CSRF token after session renewal.
3. Send ETag-derived If-Match and an Idempotency-Key on mutations; never invent owner IDs.
4. Validate/parse responses at the boundary (generated types plus runtime schema validation for critical payloads); treat malformed payloads as recoverable protocol errors.
5. Expose abort signals for UI navigation, without claiming provider cancellation.
6. Never place OPENAI_API_KEY or any provider credential in Vite variables, source, storage, or requests.

Frontend state transition for Ripple: `editing → preview_loading → preview_ready | preview_failed → confirming → commit_loading → committed | stale | commit_failed`; cancel returns to editing/current plan. Confirm is disabled when `commit_allowed=false`, session is absent, preview is expired, or required warning acknowledgement is missing.
