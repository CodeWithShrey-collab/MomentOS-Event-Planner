# MomentOS — Stage 04 Frontend Handoff

**Status:** Complete. Frontend source, mock adapter, tests, and local visual verification are ready for Stage 06 integration. No backend work was started.

## Visual Director decision

- **Primary:** Premium editorial event-planning workspace.
- **Supporting:** Refined celebratory aesthetics; modern data visualization.
- **Style preflight:** The `/gpt-taste` Python RNG preflight (seeded by the 168-character brief summary) selected Editorial Split, Satoshi, Infinite Marquee, Horizontal Accordions, Inline Typography Images, GSAP Image Scale and Fade, and Scrubbing Text Reveals. The landing page follows AIDA and passed the skill's 3×2 feature-grid density check.
- **Applied identity:** Warm ivory and cream surfaces, charcoal and deep plum typography, restrained coral/marigold accents, serif editorial moments, fine borders, and a spacious but information-rich event workspace. No gradient-heavy generic dashboard styling.
- **Motion and accessibility:** GSAP ScrollTrigger powers landing-page image/text reveals; Motion supports small interface transitions. CSS honors `prefers-reduced-motion`. Charts provide accessible names and companion legends/tables. Controls use labels, visible focus, keyboard behavior, status text, and confirmation dialogs.
- **Assets:** Six local optimized WebP photos are under `frontend/public/images/` (about 0.6 MB total), so event imagery is stable and bundled with the app instead of using random remote placeholders.

## Screens and behavior

- **Landing:** Editorial hero, navigation, event-type exploration, product chapters, planning CTA, Ripple explainer, and locally bundled event imagery.
- **Event Architect:** Wedding/birthday/community selection; event name/date/city/guest/budget inputs; priorities, theme, and description; client-side validation; sample blueprint generation; editable review; explicit confirmation before the plan is saved. Offline status and illustrative assumptions remain visible.
- **Command Center:** Event overview, budget health, task progress, days to event, deadlines, category allocation, vendor status, and guidance cards.
- **Budget Studio:** Editable category budgets, planned/actual summaries, remaining balance and warnings; Recharts visualization with textual category values.
- **Ripple Engine:** Guest-count and budget-limit simulations, explicit assumptions, before/after totals, category changes, seats, affected tasks/vendors, unknowns, capacity/budget blockers, and demo suggestions. A preview is labeled unsaved; hard blockers disable confirmation; cancel discards it.
- **Moment Map:** Milestones, dependent tasks, due dates, and completion toggles with dependency-aware feedback.
- **Vendor Workspace:** Checklist categories, editable supplier names/contact details, illustrative estimates, user-entered quotations and selection status. It explicitly says no vendor data is verified and “selected” is not a booking.
- **AI Copilot:** Contextual, read-only offline demo responses, suggested questions, loading/retry/error states. It never calls OpenAI from the browser and identifies itself as demo behavior.
- **Scenario Comparison:** Two attendance alternatives compared with deterministic projections, budget deltas, table counts, capacity state, and an accessible table; comparisons do not save changes.
- **Shared UI:** Responsive workspace shell, offline/demo disclosure, toast feedback, loading and empty states, accessible confirmation dialogs, and keyboard dismissal/focus behavior.

## Component and source architecture

- `frontend/src/App.tsx` owns client routing and event loading. Route modules are lazy-loaded.
- `frontend/src/components/AppShell.tsx` supplies workspace navigation and the copilot panel. `frontend/src/components/ui.tsx` supplies shared controls, statuses, dialogs, and loading/empty states.
- `frontend/src/pages/` contains the landing, architect, copilot, and workspace screens.
- `frontend/src/types.ts` defines the frontend event, plan, budget, task, vendor, ripple, scenario, and API envelope contracts.
- `frontend/src/services/demoApi.ts` is the Stage 04 replacement boundary. Screens consume its typed methods, not browser API calls. Stage 06 should replace this adapter with `/api/v1` calls while retaining the UI-facing types where the frozen contracts permit.
- `frontend/src/data/demoData.ts` contains clearly illustrative wedding, birthday, and community fixture plans.
- `frontend/src/hooks/useToast.tsx` provides shared notifications. `frontend/src/styles.css` defines responsive tokens and component styling.

## Mock API contract mapping

| UI operation | Typed mock adapter method | Frozen backend contract |
|---|---|---|
| List/load/create event | `listEvents`, `getEvent`, `createEvent` | `GET/POST /api/v1/events`, `GET /api/v1/events/{event_id}` |
| Generate/edit/confirm draft | `generatePlanDraft`, `commitPlanDraft` | `POST /api/v1/events/{event_id}/plan` and explicit plan commit operation |
| Edit budget category | `updateCategory` | Budget category/item update under `/api/v1/events/{event_id}/budget/...` |
| Toggle timeline task | `toggleTask` | `PATCH /api/v1/events/{event_id}/tasks/{task_id}` |
| Add/update vendor data | `addVendor`, `updateVendor` | Vendor create/update under `/api/v1/events/{event_id}/vendors` |
| Preview and explicitly commit Ripple | `previewRipple`, `commitRipple` | `POST /api/v1/events/{event_id}/ripple/preview` and `/commit` |
| Compare attendance scenarios | `compareScenarios` | `POST /api/v1/events/{event_id}/scenarios/compare` |
| Ask contextual copilot | `answerCopilot` | `POST /api/v1/events/{event_id}/copilot` |

The frontend mock envelope is `{ data, meta: { demo: true } }`; error paths use a typed `DemoApiError`. The demo adapter uses localStorage with in-memory recovery when storage is unavailable. This is a browser-local demonstration store, not authenticated server persistence or session isolation. It has deterministic minor-unit arithmetic and does not call the OpenAI API.

## Verification performed

Commands run from `frontend/` after the final source and asset changes:

- `npm run typecheck` — passed.
- `npm run lint` — passed.
- `npm test -- --run` — passed: 2 test files, 6 tests. Coverage includes architect form validation and Ripple arithmetic, blockers, explicit confirmation, and stale-preview rejection.
- `npm run build` — passed. Vite emitted route, chart, and motion chunks; largest chunk was the chart chunk at 387.40 kB (112.38 kB gzip), and no oversized-chunk warning was emitted.
- Local browser review at `http://127.0.0.1:4185/`: landing, Event Architect, Command Center, Vendor Workspace, and Ripple screens loaded. Vendor name/contact controls appeared with accessible labels. A manual 150→200 guest Ripple interaction displayed +₹50,000 catering, ₹6,30,000 projected total, 20 tables, venue capacity and ₹30,000 budget blockers; the preview remained unsaved and confirmation was disabled. The workspace at the old port 4173 showed a different stale project; verification used a fresh port and confirmed the MomentOS title/content there.
- Playwright automation and automated accessibility scanning were not run in this stage. The browser review is a visual/DOM spot check, not a claim that every route or assistive technology was exhaustively validated.

## Stage 06 integration tasks

1. Implement the frozen Flask `/api/v1` contracts, guest-session ownership, CSRF/origin checks, event ETags, idempotency and database transactions.
2. Replace `demoApi.ts` behind the existing UI adapter boundary with a typed same-origin API client; map API validation/conflict/AI errors to the UI states.
3. Keep event blueprint creation as an uncommitted draft and preserve the explicit confirmation flow for plan and Ripple commits.
4. Replace offline copilot and plan generation with backend operations using only `gpt-6-luna`; handle provider unavailability without model fallback.
5. Reconcile frontend field names/response envelopes with the frozen Pydantic contracts. Do not imply demo localStorage provides cross-session security or production persistence.
6. Add end-to-end Playwright and automated accessibility checks in the assigned verification stage, then verify the integrated production build and same-origin serving.

## Files

- Application source and configuration: `frontend/`.
- Optimized visual assets: `frontend/public/images/`.
- Tests: `frontend/src/services/demoApi.test.ts`, `frontend/src/pages/EventArchitect.test.tsx`.
- Ignore rules: root `.gitignore` excludes secrets, frontend dependencies/build output, test coverage, and generated Python files.
- Workflow/context updates: root `AGENTS.md`, `context.md`.
