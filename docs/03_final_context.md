# MomentOS — Stage 03: Final Context

**Status:** Frozen technical blueprint for Stages 04–08. Documentation only; no application code is implemented by this stage.

## Purpose and product contract

MomentOS is an AI-assisted planning workspace for weddings, birthdays, and community events. It turns an event idea into a reviewable, editable, persisted plan. Its distinguishing interaction is the Ripple Engine: a user proposes a change, sees deterministic consequences and the reasons for them, then explicitly confirms or cancels.

The product must distinguish user-provided facts, illustrative assumptions, AI suggestions, and unknown values. No recommendation is a booking, quote, completed task, or verified vendor fact. Demo prices and rates are editable illustrative assumptions.

The P0 vertical path is: create an event → interpret the brief with GPT-6 Luna or use clearly labeled offline demo data → review/edit a typed blueprint → commit the accepted plan → inspect dashboard, budget, tasks, and vendor checklist → preview a change → explicitly confirm or cancel → reload the persisted plan and change receipt.

## Frozen architecture

| Layer | Decision |
|---|---|
| Browser | React, TypeScript, Vite, Tailwind CSS, accessible primitives, Recharts, Motion where useful. |
| API/application | Python Flask, SQLAlchemy, Alembic, Pydantic validation. |
| AI | Official OpenAI Python SDK, Responses API, Structured Outputs, exact model ID gpt-6-luna from OPENAI_MODEL. No silent model substitution. |
| Persistence | SQLite for local development; PostgreSQL for production. Alembic owns schema changes. |
| Testing | Pytest, Vitest, Playwright, automated accessibility checks. |
| Hosting shape | Prefer same-origin Flask API and built frontend. If split hosting is later justified, preserve equivalent cookie, CSRF, CORS, and ownership controls. |

### Frozen technical choices and bounded decisions

1. The event aggregate is versioned. Accepted plans are immutable snapshots; editing or committing a simulation creates a new version.
2. User-authored values and confirmed plan facts are stored separately from AI usage metadata. The model cannot write to persistence.
3. Planning generation is synchronous in the first release. A bounded HTTP request is simpler to operate than a queue; long-running asynchronous jobs are deferred unless measured latency requires them.
4. A plan generation response is a draft only. The browser may let the user edit it. The commit endpoint validates the submitted draft and creates a new immutable version only after explicit confirmation.
5. Preview creation may persist an immutable simulation record for confirmation and audit, but it never changes the current plan version.
6. API mutations use event-version ETags and If-Match. A stale write returns a conflict; clients reload and re-preview.
7. Model outputs and vendor/user content are untrusted input. Typed parsing does not make claims true; application validation and provenance labels remain required.
8. Session policy, rate limits, and request budgets are configuration-backed values. Initial recommendations are specified in the other Stage 03 documents and can be changed only through a recorded decision.

## System components and responsibilities

1. **Event Management:** owns guest-session event CRUD, ownership checks, event metadata, current plan pointer, and event revision. Every event query is scoped by the authenticated session.
2. **AI Event Intake:** accepts bounded natural-language input, asks GPT-6 Luna to extract candidate fields, shows uncertainty and missing information, and requires user review.
3. **Event Plan Generation:** composes a bounded event brief and calls the typed blueprint operation. It returns a draft. Deterministic validators reject invalid fields, dates, amounts, statuses, and references before commit.
4. **Budget Studio:** edits categories and line items, tracks estimate/quote provenance, and derives totals, remaining budget, variance, and allocations in Python integer minor units.
5. **Task & Timeline Engine:** stores tasks and dependencies, validates acyclic dependencies and dates, derives a topological order, and identifies schedule conflicts. AI can suggest candidate tasks only.
6. **Vendor Workspace:** stores categories, user-entered contacts, notes, selection state, and quotations. It never implies real availability or a verified quote unless supported by an explicit provenance field and source.
7. **Ripple Engine:** pure Python simulation over a versioned snapshot and proposed patch; returns before/after values, affected dependency subgraph, warnings, missing inputs, and blocking constraints. A separate transaction commits a fresh version after confirmation.
8. **Scenario Comparison:** runs multiple read-only, deterministic patches against the same base version and returns comparable projections. It does not commit any alternative.
9. **AI Copilot:** answers a bounded event-specific question from a minimized saved-plan context. It is read-only and labels recommendations separately from known values.
10. **Session Management:** issues opaque, high-entropy guest credentials in HttpOnly cookies; stores only token hashes; enforces expiry, CSRF, origin checks, and ownership on all protected routes.
11. **AI Usage Tracking:** records operation/model, status, token counts, latency, request correlation ID, and estimated cost using a dated pricing configuration. Never record credentials or raw prompts/responses by default.

## Primary workflows

### Create and plan

1. POST creates a guest session when none exists, setting a secure cookie and returning a CSRF token for the current page lifetime.
2. The user creates an event with type, title, currency, event date/location if known, budget limit, attendance, and preferences. Unknowns remain null.
3. The user requests interpretation or a blueprint. Backend validates length and operation budget, builds a minimal context, and calls exactly gpt-6-luna with a typed schema.
4. The browser presents candidate facts, assumptions, questions, concept, category suggestions, task suggestions, vendor categories, and ideas for editing. This draft is not persistent.
5. The user confirms a reviewed draft. The backend validates all fields and constraints, writes version 1 transactionally, and returns its ETag.

### Edit budget, tasks, or vendors

Every mutation requires session ownership, CSRF, a valid event ETag, and schema validation. A successful change creates the next immutable plan version and updates the current-version pointer atomically. Derived totals and conflict summaries are recomputed by domain services. User-entered quote and estimate provenance is retained.

### Ripple preview and confirmation

1. The UI posts a typed patch and the current If-Match value.
2. The server loads the owned immutable base version, validates the patch, runs deterministic simulation, and stores an immutable preview with a short expiry. Current event state is unchanged.
3. The UI shows changes, causal explanations, missing inputs, warnings, hard blockers, and editable alternatives. AI explanation is optional and cannot alter calculation results.
4. On explicit confirmation, the server checks owner, preview state/expiry, base version, confirmation flag, and idempotency key. In one transaction it locks or compare-and-swaps the event revision, recomputes the simulation, rejects stale or invalid results, creates the next version and change receipt, and marks the preview committed.
5. Cancel expires the preview. Duplicate confirmation returns the already created version. Stale preview requires a new preview.

## Cross-cutting rules

- Money is stored as integer minor units plus ISO currency; no binary floating-point currency arithmetic. Currencies with different minor-unit scales must use a currency metadata function.
- Dates are ISO-8601 at API boundaries. Instants use UTC; event-local dates and times include an IANA timezone where time-of-day scheduling matters.
- All IDs are opaque UUIDs. Server time is authoritative for timestamps and expiry.
- Unknown is not zero. Missing rates, capacities, per-household invitation rules, or venue limits produce a needs-input state, not an invented number.
- Hard constraints (explicit hard budget ceiling, required date bounds, invalid/cyclic dependencies, exceeded configured venue capacity) block commit. Soft warnings can be confirmed with explicit acknowledgement.
- AI-generated candidate tasks begin unassigned and incomplete. No generated status can represent booked, paid, or completed.
- Offline fixtures are deterministically loaded and clearly labeled. They must never be presented as a successful live model response.
- Every endpoint returns a correlation/request ID and a stable error code. Errors do not include secrets, stack traces, or raw provider content.

## Deployment and operations plan

The deployable unit should build the Vite frontend into a static directory and let Flask serve the same-origin assets plus /api/v1 routes. Production uses PostgreSQL through DATABASE_URL and runs Alembic migrations as a controlled release step. OPENAI_API_KEY and OPENAI_MODEL are backend-only environment settings. Set OPENAI_MODEL=gpt-6-luna explicitly; fail readiness for a misconfigured model identifier, and report a provider access error without substitution.

Use environment-specific secure cookies, TLS, a persistent production database, database backups, bounded request sizes/timeouts, application rate limits, and health/readiness probes. A local SQLite database and sample fixtures are for development/demo only. Do not make deployment or paid-service commitments during this stage. Repository size must stay below 10 MB by excluding dependencies, virtual environments, local databases, caches, and bulky media; keep assets optimized and build in deployment CI.

Suggested release sequence: implementation locally → unit/API/UI checks → production-like PostgreSQL migration check → authorized hosting choice → configure secrets and database → deploy a candidate → smoke test exact GPT-6 Luna access and core paths → verify persistence and security settings → record deployment details. Model availability in the configured project is not verified by this architecture document.

## Test gates

The release must cover the traceability matrix in docs/03_test_strategy.md. At minimum: arithmetic and dependency unit tests; API ownership, CSRF, validation, ETag, and persistence tests; preview-isolation and commit idempotency/staleness tests; mocked AI success/refusal/incomplete/malformed/timeout tests; browser create → review → commit → ripple preview → confirm → reload path; keyboard and automated accessibility checks; responsive mobile layout; and production-like migration/readiness checks. These are specifications, not executed test results.

## Stage handoff and change control

Stages 04–08 must read this document and the supporting API, database, AI, Ripple, and test contracts. Freeze routes, wire schemas, immutable-version semantics, AI operation schemas, session model, and simulation confirmation behavior. If implementation exposes a conflict with a frozen decision, record the evidence, affected contracts, migration impact, and proposed replacement in a short decision entry in this document before changing dependent code.

### Stage 03 verification notes

- Workspace root resolved to G:\Hackathons\MomentOs Event Planner.
- Prior Stage 01 and Stage 02 handoffs were read.
- This directory currently has no Git metadata; repository initialization is outside this stage.
- Official OpenAI documentation was checked for the model page, Responses API, Structured Outputs, data controls, and Python SDK parse pattern. The exact project’s access to gpt-6-luna remains unverified; no live request was made.
- No frontend/backend implementation and no automated application tests were run in this documentation stage.
