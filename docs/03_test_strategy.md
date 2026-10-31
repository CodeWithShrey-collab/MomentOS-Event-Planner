# MomentOS — Test Strategy and Acceptance Tests

**Status:** Verification plan for Stages 04–08. This document defines checks to implement; it does not claim that tests have been run or passed.

## Strategy

Use three layers: pure domain unit tests for arithmetic/constraints/graph behavior; Flask API integration tests for ownership, validation, persistence, concurrency, and AI boundary behavior; and browser end-to-end tests for user-visible workflows. Add static checks and automated accessibility checks to CI. Standard CI must not require a live OpenAI key, network request, public database, or paid service.

### Tool mapping

| Area | Tool | Scope |
|---|---|---|
| Python domain/API | Pytest | Deterministic services, Pydantic validation, Flask routes, SQLAlchemy transactions, migrations. |
| Frontend logic/components | Vitest + Testing Library and axe integration | API client parsing, state transitions, form validation, loading/error/accessibility behavior. |
| Browser workflows | Playwright | Create/review/commit, event reload, Ripple preview/confirm/cancel, responsive and keyboard paths. |
| Database | SQLite temporary DB and PostgreSQL CI service | SQLite FKs enabled; fresh migration and upgrade path tested on both supported engines. |
| AI provider | Mocked official SDK client; optional authorized smoke check | Success, refusal, malformed/invalid, incomplete, timeout, 429, provider/model access failure, usage accounting. |
| Accessibility | axe checks + keyboard/manual checklist | Core routes and dialogs; automated results supplemented by semantic and keyboard assertions. |

## Acceptance tests

### Event planning and persistence

| ID | Scenario | Acceptance result |
|---|---|---|
| EVT-01 | Create each supported type: wedding, birthday, community. | Correct event type, currency, date/location unknowns, attendance, and budget persist under the current session; event type enum rejects unsupported values. |
| EVT-02 | Submit a natural-language brief and generate a plan draft. | Mocked GPT-6 Luna returns a valid typed blueprint; user can edit the draft; no plan version exists until explicit confirmation. |
| EVT-03 | Refuse to confirm or cancel the generated draft. | Event metadata may exist as a draft container, but no accepted plan version/child rows are written from the draft. |
| EVT-04 | Confirm a reviewed valid plan. | Version 1 and normalized categories/items/tasks/dependencies/vendor categories persist in one transaction; reload returns the same values and provenance. |
| EVT-05 | Submit edited/tampered invalid AI draft. | Server-side validation rejects negative money, invalid enum, cross-list references, malformed date, cycles, and prohibited completion/booking state. No partial write. |
| EVT-06 | Restart/recreate application with same persistent DB. | Accepted event state and version history remain available to its live owner session; no in-memory-only persistence. |

### Deterministic budget, timeline, and vendor rules

| ID | Scenario | Acceptance result |
|---|---|---|
| DOM-01 | Sum planned and actual item values in minor units. | Category/event totals, remaining budget, and variance match hand-calculated integer arithmetic; null is not treated as zero data. |
| DOM-02 | Calculate a per-person line item and fractional rounding boundary if enabled. | Quantity × rate follows the documented fixed-scale/half-up rule exactly once and is stable across SQLite/PostgreSQL. |
| DOM-03 | Wedding baseline 150 guests, catering ₹1,000/person, total ₹5,80,000, limit ₹6,00,000. | Catering is ₹1,50,000; budget total and remaining amount match fixture values. |
| DOM-04 | Build valid task dependency chain with lag/date constraints. | Stable topological ordering and earliest feasible schedule are produced. |
| DOM-05 | Submit self-edge, missing dependency, cross-version edge, or cycle. | Validation rejects with stable field/domain code; no version commit. |
| DOM-06 | Submit successor before predecessor finish or outside hard event-date window. | Conflict is reported; hard violation blocks commit. Unknown date is surfaced as incomplete, not fabricated. |
| DOM-07 | Read user-entered quotation and AI suggested vendor category. | Quote is marked user-entered; suggested category has no fabricated name, contact, availability, or price. |

### Ripple preview, confirmation, and concurrency

| ID | Scenario | Acceptance result |
|---|---|---|
| RIP-01 | Preview wedding increase 150 → 200 with ₹1,000/person catering, ₹5,80,000 plan, ₹6,00,000 cap, venue cap 180, 10 seats/table. | Deterministic result shows catering +₹50,000; new plan ₹6,30,000 and ₹30,000 over cap; 15→20 tables; capacity blocker; affected budget/task/vendor IDs; invitations unknown without a rule. Current version remains unchanged. |
| RIP-02 | Preview same normalized snapshot/patch twice under same engine version. | Calculation result and canonical hash are identical; no clock/random state changes domain result. |
| RIP-03 | Preview with unknown unit rate, capacity, seating ratio, or household rule. | Each value is labeled unknown/needs input; no guessed value is used. |
| RIP-04 | Preview input with arbitrary patch path, negative quantity, invalid currency, NaN, or bad ID. | Request is rejected before any event mutation; no dynamic attribute/SQL path is accepted. |
| RIP-05 | Cancel preview. | Simulation status changes to cancelled; event version/revision and child rows are unchanged. |
| RIP-06 | Confirm preview with no blockers and required warning acknowledgements. | Recompute matches stored result; new immutable plan version and receipt are created atomically; response has new ETag; old version unchanged. |
| RIP-07 | Confirm preview that has a hard budget/capacity/date/dependency blocker. | Commit is rejected, no partial version is written, and warning acknowledgement cannot bypass hard rule. |
| RIP-08 | Confirm after another tab/user action changed event revision or after preview expiry/rule version change. | Returns stale/expired result; no auto-rebase; user must refresh and preview again. |
| RIP-09 | Repeat the same commit with same Idempotency-Key. | Returns the same committed version/receipt once; no duplicate version. Reusing the key with another body returns conflict. |
| RIP-10 | Force transaction failure during version clone/pointer update. | Entire operation rolls back; no partial child rows or committed simulation state. |
| RIP-11 | Run deterministic Ripple for 500-task fixture. | Proposed performance target is under 200 ms in the recorded reference environment, excluding database and network time; record measured environment and result. |

### Session, security, and API failure behavior

| ID | Scenario | Acceptance result |
|---|---|---|
| SEC-01 | Session creation, rotation, expiry, revocation. | Cookie is opaque, HttpOnly, Secure in production, configured SameSite, not returned in JSON; DB stores only token hash; expired/revoked session rejected. |
| SEC-02 | Session A attempts read/write of Session B event or simulation ID. | Same safe 404 contract as missing resource; no data or existence leakage. |
| SEC-03 | Cookie-authenticated mutation lacks CSRF token or has bad Origin. | Request is rejected; no database change. Valid session refresh exposes a CSRF token safely to same-origin client. |
| SEC-04 | Body, description, question, list, or task count exceeds configured bound. | Rejected before database/provider work with 413/422 and stable safe code. |
| SEC-05 | Stale or missing If-Match on event mutation. | 428 for missing precondition; 412 for stale; no write. |
| SEC-06 | Provider rate limited, unavailable, timed out, refused, or returns incomplete/malformed output. | Typed safe error and request ID; input draft preserved; no silent model fallback or false Live AI label; usage status recorded without raw prompt/secret. |
| SEC-07 | Inspect built frontend bundle and client requests. | No OPENAI_API_KEY or provider credential appears in frontend assets, Vite variables, local storage, or browser requests. |
| SEC-08 | Inject prompt override/instruction into user description/vendor note. | Shared policy remains in effect; output is schema-validated, cannot call tools/write database, and cannot expose secrets or other-session data. |
| SEC-09 | Inspect application logs from provider errors. | Authorization headers, raw secret values, unnecessary raw prompt/response, and unredacted provider body do not appear. |

### Frontend, accessibility, and release readiness

| ID | Scenario | Acceptance result |
|---|---|---|
| UI-01 | Generate plan through loading, success, refusal, timeout, and invalid output. | State and status announcement are accurate; inputs persist; buttons prevent duplicate submission; retry is explicit and bounded. |
| UI-02 | Ripple editing → preview → confirmation → commit. | State sequence follows API contract; confirmation shows exact changes/warnings; cancel leaves plan unchanged; hard blockers disable confirmation. |
| UI-03 | Navigate core screens at 320 CSS px and desktop width. | No horizontal page scroll for core task; budget/timeline/vendor actions remain usable and information is not conveyed by color alone. |
| UI-04 | Use keyboard and screen reader semantics. | All core controls are reachable and named; focus is visible; dialog traps/restores focus; field errors are associated; async updates announced. |
| UI-05 | Render budget/scenario chart with screen reader or without chart support. | Equivalent labeled table/text summary presents exact values. |
| UI-06 | Enable reduced-motion preference. | Nonessential animation is suppressed/reduced; no state or warning relies on motion. |
| REL-01 | Run migrations on fresh SQLite and PostgreSQL; upgrade prior schema. | Alembic completes; constraints and indexes exist; foreign keys enforce same-version references; application can read/write after migration. |
| REL-02 | Readiness/live probes. | Liveness is dependency-independent; readiness exposes no secret, confirms DB/schema and configuration shape, and fails safely when required configuration is absent. |
| REL-03 | Deploy candidate to an authorized public target and perform smoke flow. | Verify HTTPS/cookie flags, production DB persistence across restart, static asset/API same-origin behavior, migration status, exact GPT-6 Luna configured access, and core create→ripple path. Record actual URL only after it exists. This stage does not authorize deployment. |
| REL-04 | Measure repository checkout/package. | Public source repository is under 10 MB, excludes secrets, .env, local DB, dependencies, caches, and oversized generated assets. Do not claim until measured. |

## Cross-session isolation fixture

Create two sessions and two events with recognizable unique values. Assert session A can list only its own event, retrieve/update/delete only its own event, and access no version, task, quote, preview, scenario, or AI context from session B. Repeat with guessed IDs in nested routes. Run this at API and browser boundaries. For AI tests, inspect mocked provider input to prove only the authenticated event's minimized context was included.

## AI contract test fixtures

Mock exact Responses API behavior for each operation: valid parsed Pydantic result, refusal marker, incomplete response, null parsed output, Pydantic failure, extra field, oversized arrays, impossible date, unsupported completion status, mismatched Ripple result ID, 429, 5xx/access error, and timeout. Assert no automatic alternate model is requested; configured model name is exact; `store=False`, bounded output and reasoning, and explicit timeout are included; all failures preserve unsaved input and create a sanitized usage status.

Golden fixtures should be small, deterministic, and clearly identified as synthetic. Unit tests should exercise normalization and business validation independent of provider prose. Do not include personal data or the API key in fixtures.

## CI gates and reporting rules

Proposed CI gates: format/lint/type check; Pytest; Vitest; frontend production build; migration checks; Playwright critical path; axe checks on core screens. Target at least 80% branch coverage for deterministic domain modules once meaningful coverage is measured. Do not chase aggregate coverage at the expense of boundary cases. Keep live provider, public deployment, and cost smoke checks opt-in and separately authorized.

Each stage handoff reports exact commands executed and outcomes. If a tool, browser, database, or external provider is unavailable, record that specific blocker; never report a test as passing merely because its specification exists.
