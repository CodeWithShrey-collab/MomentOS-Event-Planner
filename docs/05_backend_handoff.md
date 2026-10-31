# MomentOS — Stage 05 Backend Handoff

**Status:** Backend implementation complete. Stage 06 integration has not started.

## Implemented backend

The Flask application factory and API are in `backend/momentos/`; `backend/wsgi.py` is the WSGI/Flask CLI entry point. Pydantic Settings read the process environment first and only the authorized project-root `.env` as a local fallback. SQLite is the local default; PostgreSQL URLs use Psycopg in production.

The API is mounted under `/api/v1` and implements:

- Health: `GET /health/live`, `GET /health/ready`.
- Guest session: `POST/GET/DELETE /session`.
- Events: list, create, read, patch, and soft-delete.
- AI intake and plan flow: `POST /events/{id}/intake`, `/plan-drafts`, and `/plan-commits`.
- Budget: read and patch categories/items with deterministic derived totals.
- Tasks: list, create, patch, delete, and replace dependencies.
- Vendors: list, create, patch, delete, and add user-entered quotations.
- Ripple: create/read/cancel previews and explicitly commit a revalidated preview.
- Scenario comparison: deterministic, read-only alternatives.
- Copilot: event-context-limited question answering and deterministic budget-option analysis.

Requests and responses use the frozen Stage 03 envelope and schemas. Event mutations use `If-Match` ETags; state-changing requests require CSRF/origin validation and idempotency keys. Foreign-owned event records are returned as not found.

## GPT-6 Luna operations

`backend/momentos/ai_provider.py` is the centralized official Python SDK Responses API adapter. `OPENAI_MODEL` must be exactly `gpt-6-luna`; invalid model configuration fails rather than switching. Calls use Pydantic structured parsing, bounded operation-specific output tokens, low or medium reasoning, an explicit timeout, `store=False`, and SDK retries disabled. Sampling parameters are not sent. Refusal, incomplete output, schema/domain validation failures, timeout, rate limit, and provider-unavailable errors are mapped to safe API errors.

The provider exposes all seven typed operations: requirement extraction, blueprint generation, personalized ideas, task suggestions, vendor checklist, Ripple explanation, and copilot answers. The API currently invokes extraction, blueprint generation, Ripple explanation (best-effort; it cannot fail a deterministic preview), and copilot. Blueprint generation includes ideas, task suggestions, and vendor categories in its structured result; the standalone idea/task/checklist operations are not separate HTTP routes.

Demo mode is the default and returns deterministic offline fixtures marked `offline_demo`; it does not claim an OpenAI response. Live calls reserve an atomic per-session/day quota before contacting the provider. AI usage records contain operation, model, effort, outcome, provider request ID, token counts when available, duration, and versioned cost estimate. The project `.env` contains live-mode settings and a key, but the live smoke request was not made: a key was inadvertently present in `.env.example` and exposed during inspection. Rotate the credential before using it; live GPT-6 Luna access remains unverified.

## Deterministic planning and Ripple

Budget amounts are integer minor units; line-item multiplication uses `Decimal` and explicit half-up rounding. Budget totals, remaining balance, and overruns are calculated in Python. Task dependency validation rejects unknown/self references and cycles; topological ordering and schedule-conflict checks are deterministic.

Ripple uses the pure domain service in `backend/momentos/domain.py`. It validates supported input changes, recomputes projections, marks affected entities, evaluates budget/capacity/schedule constraints, and returns a before/after preview. Preview records are immutable and expire; preview creation does not change the accepted plan. Commit checks owner, base version/revision, expiry, warning acknowledgement, hard blockers, preview hash, and idempotency, then writes a new plan version transactionally. A capacity-blocked commit regression test confirms the event version and guest count remain unchanged.

## Database and migrations

The normalized schema includes guest sessions; events and immutable plan versions; event details; budget categories/items; tasks/dependencies; vendors/quotes; Ripple and scenario simulations; plan-change receipts; AI usage and daily quota buckets; and idempotency records. Composite foreign keys tie versions, dependencies, and records to their owning event/version. Ownership, version, status, and expiry access paths are indexed.

Alembic revisions are in `backend/migrations/versions/`. SQLite was migrated to head (`078bdffa6615`); schema inspection confirmed the atomic quota table and the two cyclic event/version foreign keys. PostgreSQL offline SQL generation succeeded and includes both deferred/post-creation constraints. No live PostgreSQL server was available or used, so production-database execution still needs deployment verification.

## Security and operations

- Session cookies are opaque and only token hashes are stored. Cookies are HttpOnly, SameSite, and Secure in production. CSRF tokens are stable within a session generation and derive from the application secret; token rotation happens with session rotation, preventing concurrent tab refreshes from invalidating each other.
- All event data access is scoped to the live session owner. State-changing cookie-authenticated routes validate a CSRF token and trusted Origin/Referer.
- Event writes require current ETags. Repeated writes are bounded by idempotency storage. Live AI calls have per-minute request limiting and an atomic configurable daily quota.
- Request bodies, descriptions, questions, list sizes, task counts, and scenario counts are bounded. Prompts treat user/vendor text as untrusted data; the model cannot execute SQL or mutate storage.
- Production configuration rejects short/missing secrets, insecure session cookies, and in-memory rate-limit storage. The fallback development secret is ephemeral; provide a stable `SECRET_KEY` when persisting development sessions across restarts.
- `.env` is ignored and is loaded only from the project root by Pydantic Settings; process environment values take precedence. `.env.example` contains names and safe placeholders only. The inadvertently exposed credential was removed from `.env.example`; the credential should be rotated before any live request.

## Verification performed

Run from `G:\Hackathons\MomentOs Event Planner` with the configured Python 3.11 environment:

```powershell
& 'G:\conda_envs\py311\python.exe' -B -m pytest -p no:cacheprovider backend/tests -q
```

Result: **32 passed**. Coverage includes Decimal budget arithmetic, deterministic Ripple/dependency rules, session cookies and stable cross-tab CSRF/origin checks, cross-session isolation, explicit offline plan commit, task versioning/completion, stale ETag rejection, Ripple preview immutability/idempotent commit/hard-blocker rollback, AI structured-output errors and exact model selection, timeout/rate-limit mapping, quota/idempotency behavior, dotenv settings precedence, and sanitized smoke-command behavior. Tests use isolated SQLite and mocked providers; they do not use a live API key.

Migration checks were also run separately: SQLite upgrade to head and foreign-key inspection passed; PostgreSQL offline SQL generation passed. There was no live PostgreSQL migration or deployment.

The `flask openai-smoke` command makes exactly one low-reasoning request to `gpt-6-luna`, capped at 128 output tokens, with a 15-second timeout, no retries, and `store=False`. Following user confirmation that the exposed credential was rotated, the command completed once: API accepted the request, `gpt-6-luna` was accessible, and a completed response with visible output was received. Usage was 22 input, 5 output, 27 total tokens. Response content and credentials were not displayed. The smoke command now reports safe token counts and distinguishes `max_output_tokens` truncation from connectivity errors.

## Known limitations and Stage 06 integration requirements

- The backend is API-only; it does not yet serve the built React app. The frontend still uses `frontend/src/services/demoApi.ts` and must be switched to a typed same-origin `/api/v1` client.
- Reconcile frontend wire names and path expectations with `docs/03_api_contracts.md`. Keep blueprint and Ripple preview results unsaved until explicit confirmation; map 412/409/422 and provider errors to recoverable UI states.
- Standalone personalized-ideas, task-suggestion, and vendor-checklist operations exist in the provider but have no independent HTTP endpoints; Stage 06 should use them through the blueprint flow or record an API-contract change before adding routes.
- PostgreSQL has offline migration validation only. Run an authorized staging migration/readiness check when deployment credentials and infrastructure are available.
- No public app, paid infrastructure, or live OpenAI request was provisioned. Public deployment remains unperformed; the master instructions require explicit authorization before publishing or initiating paid services.

## Setup

Install and run the backend using [backend/README.md](../backend/README.md). It documents local migrations, deterministic demo mode, live model settings, production PostgreSQL requirements, and test commands.
