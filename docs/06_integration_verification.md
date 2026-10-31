# MomentOS — Stage 06 Integration Verification

**Status:** Stage 06 integration and requested GPT-6 Luna blueprint repair are complete. The live plan-draft, plan-save, and reload flow succeeded once through Flask with the configured `gpt-6-luna` model. No deployment or publication was performed.

## Blueprint failure: confirmed causes and repair

The initial `HTTP 422 ai_output_invalid` came from two consecutive, confirmed defects:

1. The initial Responses API call used `responses.parse()`. The SDK's post-parser attempted to parse `output_text` before returning the response, so a token-truncated JSON body raised a Pydantic `json_invalid` error before the application could inspect `status=incomplete` and `incomplete_details.reason=max_output_tokens`. The application therefore misreported provider output exhaustion as an invalid structured result. That request used the 1,800-token blueprint cap and reported 1,146 input / 1,800 output / 2,946 total tokens.
2. After status-first parsing was installed, a completed response reached application validation but cited unsupported machine references in `ideas[].input_references`. The prompt had not supplied a defined reference vocabulary, while validation required each reference to match an allowlisted key.

`backend/momentos/ai_provider.py` now sends strict JSON Schema through the Responses API `create()` interface, using the official SDK's Pydantic strict-schema conversion. It checks refusal and response completion before parsing JSON into Pydantic, and reports incomplete responses separately. The blueprint output ceiling is bounded to 3,000 tokens and the configured application cap. The prompt names the permitted reference IDs and limits the size of generated sections. The confirmed numeric suggestions are still checked against request context, and unsupported references/quantities/rates still fail validation. No model fallback was added.

Safe diagnostics include the request correlation ID, provider request ID where available, exact model ID, operation, response state, incomplete reason, refusal flag, token counts, validation categories, and safe field paths. They omit the API key, event description, response body, and raw provider exception. Public errors use sanitized messages. An incomplete blueprint now returns `ai_incomplete` (HTTP 502), while a completed but schema/business-invalid result returns `ai_output_invalid` (HTTP 422).

## Additional integration defects fixed

- Draft budget calculation now maps stable AI category keys to temporary domain identifiers before deterministic calculation; persisted keys remain stable and storage IDs are generated at commit.
- AI preference/constraint arrays are transformed into bounded event-detail objects before persistence.
- Live plan/ripple commit no longer feeds an already mapped event record through the raw JSON mapper a second time, which had dropped the saved guest count in the UI.
- Copilot context now maps saved task and vendor statuses to the strict AI context vocabulary, limits vendor categories and quote provenance, and defines nullable task due dates in the typed context schema.
- Offline browser tests now use a wedding budget fixture with a visible illustrative reserve so the guest-count Ripple confirmation path is testable. This does not alter live business calculations.
- Vitest excludes Playwright E2E files so the two test runners do not collect each other's specs.

## Frontend-to-Flask contract mapping

Frontend UI call sites use the existing API facade. `VITE_MOMENTOS_MODE=demo` explicitly selects browser-local demo fixtures; otherwise the `liveApi` calls Flask. Live failures never fall back to fixtures.

| UI operation | Flask API | Security and concurrency |
|---|---|---|
| Session restore/create | `GET /api/v1/session`, `POST /api/v1/session` | Opaque cookie; CSRF token returned by session bootstrap. |
| List/get events | `GET /api/v1/events`, `GET /api/v1/events/{id}?include=summary` | Cookie session; owner scoped; ETags captured. |
| Create event | `POST /api/v1/events` | Cookie, CSRF, idempotency key. |
| Generate/review blueprint | `POST /api/v1/events/{id}/plan-drafts` | Cookie, CSRF, server quota/idempotency; draft remains unpersisted. |
| Confirm plan | `POST /api/v1/events/{id}/plan-commits` | CSRF, `If-Match`, idempotency; transactional. |
| Edit budget/task/vendor | `PATCH /api/v1/events/{id}/budget`, `/tasks/{task_id}`, `/vendors/{vendor_id}` | CSRF, current ETag, idempotency. |
| Ripple | `POST /api/v1/events/{id}/ripple-previews`, then `POST .../{simulation_id}/commit|cancel` | Deterministic backend preview; confirmation required; CSRF, ETag, idempotency. |
| Compare/Copilot | `POST /api/v1/events/{id}/scenario-comparisons`, `/copilot` | Event ownership checked server side; Copilot receives minimal context. |

Responses use `{data, request_id}`; normalized errors use `{error:{code,message,fields?},request_id}`. `frontend/src/services/apiClient.ts` handles JSON, cookies, CSRF bootstrap/refresh, ETag capture, idempotency keys, timeout/cancellation, safe-operation retry policy, and one bounded session renewal after 401. Vite proxies `/api` to Flask. Live mode does not use browser localStorage fixture data.

## Live GPT-6 Luna request and saved-plan verification

One controlled live request was made for: “Plan a birthday party in Nagpur for 50 guests with a budget of ₹80,000.” It used the project's private environment configuration, backend-only credentials, exact model `gpt-6-luna`, medium blueprint reasoning, and no retry or model change.

- Flask plan-draft response: **HTTP 200**.
- Structured result: **5** budget categories, **5** tasks, **5** vendor categories, **4** personalized ideas; business validation passed.
- Provider usage: **1,260 input / 1,967 output tokens** (3,227 total).
- Explicit plan commit: **HTTP 201**, saved version **1**.
- Reload: **HTTP 200**; the saved event showed **50 guests**, INR budget limit **8,000,000 minor units** (₹80,000), and persisted plan data.
- No provider response text or secret value was printed or stored in this document.

This confirms the live plan-generation and save path. The live plan was saved/reloaded in the isolated test application used for the controlled check; it is not a production deployment. No live Copilot request was made during final verification.

## Automated verification

Final checks on the corrected source (frontend checks after the final frontend edit; backend tests and browser E2E after the final backend edit):

- Backend: `G:\conda_envs\py311\python.exe -m pytest -q` — **47 passed**.
- Frontend typecheck: `npm run typecheck` — **passed**.
- Frontend lint: `npm run lint` — **passed**.
- Frontend Vitest: `npm test -- --run` — **3 files, 8 tests passed**.
- Frontend production build: `npm run build` — **passed**.
- Playwright: `npm run test:e2e` — **1 browser workflow passed** using isolated Flask `AI_MODE=demo`, Chromium, and seeded/local illustrative assumptions.

The automated provider tests mock the SDK and cover valid blueprint output and nullable fields, missing required fields, wrong nested types, invalid enums, unsupported references/numeric assumptions, refusal, token-limited incomplete output, blueprint timeout without retry, and sanitized incomplete route errors. The API tests cover typed Copilot context, plan draft → confirmed save → reload, session ownership, CSRF, ETags/idempotency, deterministic budget and Ripple behavior.

The Playwright path covered session bootstrap, event creation, plan review/save, dashboard reload, a guest-count Ripple preview, cancellation with unchanged persisted state, a second preview and explicit commit, persistence after refresh, task update, vendor update, and contextual Copilot request. That browser test uses offline demo mode and correctly displays its offline status; it is not evidence of a live Copilot response. Mocked provider tests cover live Copilot context construction.

## Deployment and remaining limitations

- Production deployment and public hosting were not tested or performed.
- Flask continues to serve the API. Production frontend assets require a same-origin reverse proxy/static host or a separately approved serving configuration.
- The Playwright test is an isolated one-session demo-mode workflow; no production browser session or real vendor integration is used.
- The local project folder has no Git metadata, so repository history and a production deployment target are not verifiable from this workspace.
- Stage 07 DOM/accessibility verification and Stage 08 demo scripting have not been started.
