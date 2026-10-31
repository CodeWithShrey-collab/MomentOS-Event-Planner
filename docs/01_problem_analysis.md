# Stage 01 — Problem Analysis

**Status:** Stage 01 product specification; analysis only. No frontend/backend code or architecture change is authorized by this document.

## 1. Problem interpretation

Event planning is a coordination problem with financial and operational dependencies. A host may have a budget, a date, a location, a rough guest count, and personal priorities, but the work is scattered among notes, messages, spreadsheets, and vendor conversations. A decision such as increasing attendance can change catering, seating, venue feasibility, invitation workload, budget allocation, vendor needs, and deadlines. Late changes make previously reasonable plans stale.

The challenge is to create a GenAI-powered assistant that helps users plan weddings, birthdays, and community events with budgets, timelines, vendor checklists, and personalized ideas. MomentOS should turn a natural-language event idea into an editable plan; keep user-entered facts and unknowns visible; and help the user understand consequences before changing the saved plan.

The main product promise is: **describe the celebration, get a reviewable plan, and see deterministic consequences before committing changes.** GPT-6 Luna adds interpretation, personalization, and explanation. Deterministic application rules own money arithmetic, dependencies, dates, and capacity checks. AI suggestions are proposals, not facts or completed actions.

The pain points below are product hypotheses derived from the challenge and requested capabilities. The personas are representative archetypes, not interview findings or claims of user research.

### Challenge requirements extracted

| Explicit challenge requirement | Product interpretation | Evidence in the product |
|---|---|---|
| GenAI-powered planning assistant | Backend-routed GPT-6 Luna interprets user descriptions and creates reviewable planning suggestions. | Clear AI-assisted planning flow; provider failures and offline demo mode are labeled honestly. |
| Organize weddings | A wedding can be created, planned, edited, budgeted, and adapted to guest/vendor changes. | Wedding end-to-end acceptance scenario. |
| Organize birthdays | A birthday can be planned around a guest of honor's stated preferences, budget, and logistics. | Birthday end-to-end acceptance scenario. |
| Organize community events | A community event can include attendance, activities, capacity, volunteer/vendor tasks, and access needs. | Community-event end-to-end acceptance scenario. |
| Budgets | Users can enter and edit budget amounts and allocations; arithmetic, totals, and variances are deterministic. | Budget Studio and budget acceptance tests. |
| Timelines | Users can plan dated tasks and milestones with dependencies and event-date constraints. | Editable Timeline & Task Planner and schedule tests. |
| Vendor checklists | The plan identifies vendor categories and user-managed follow-ups without inventing real vendor availability or quotes. | Vendor Workspace/checklist, explicit provenance for user-entered quotes. |
| Personalized ideas | Recommendations reflect user-provided preferences, event type, constraints, and context. | Editable ideas with visible grounding in provided context and constraints. |

## 2. Evaluation alignment matrix

These are proposed release acceptance gates for the six stated evaluation dimensions. They are measurable targets, not claims that the current project has passed them or will receive a particular score.

| Evaluation dimension | What evaluators should be able to verify | Proposed acceptance criteria |
|---|---|---|
| **Code Quality** | A maintainable, typed product with business rules separated from UI and model output. | Frontend production build, lint, and TypeScript checks pass. Backend modules use typed request/response validation. Budget, schedule, capacity, and Ripple calculations are independently callable deterministic functions, not embedded in prompts or UI components. No known P0 defects remain at release. |
| **Security** | Secrets and event data are protected; model output cannot perform unauthorized changes. | `OPENAI_API_KEY` is absent from frontend source/build output and logs. Every event read/write is tested for session ownership. Cookie-authenticated mutations reject invalid/missing CSRF tokens. Invalid and oversized requests are rejected. A Ripple preview cannot mutate persisted state; only explicit authorized confirmation can. |
| **Efficiency** | The app remains responsive and avoids wasteful or unbounded model work. | Planning input/output is bounded; model calls have a timeout and bounded retry policy; repeat actions do not trigger needless duplicate generation. Proposed target: deterministic Ripple computation completes within 200 ms for an event with up to 500 tasks on the reference dev environment. Measure separately from network/model latency; do not claim this target until measured. |
| **Testing** | Critical planning and safety behavior has automated coverage. | CI runs backend, frontend, and end-to-end suites. Budget, date/dependency, capacity, and Ripple boundary cases have unit tests; API tests cover validation, session isolation, and confirmation; UI tests cover loading, failure, and offline-demo states; one Playwright path covers create → plan → simulate → confirm. Proposed target: at least 80% branch coverage for deterministic business-rule modules, with all P0 acceptance scenarios represented. |
| **Accessibility** | People can complete the core planning flow with assistive technology and keyboard input. | All core controls expose accessible names and work by keyboard; focus is visible and managed in dialogs; validation errors are programmatically associated with fields; charts have a text/table alternative; automated axe checks show no serious or critical issues on core screens; core flow remains usable at 200% zoom and narrow mobile width. |
| **Problem Statement Alignment** | The product actually plans the three event types and addresses all named planning artifacts. | A user can complete an editable wedding, birthday, and community-event planning flow including budget, timeline, vendor checklist, and personalized ideas. Event changes show deterministic consequences. Proposed changes remain a preview until explicit confirmation. Offline demo content is clearly labeled and never described as a live OpenAI result. |

## 3. Planning problems to solve

| Problem | User impact | MomentOS response | Guardrail |
|---|---|---|---|
| Budget uncertainty | Hosts cannot see remaining funds, the cost of a choice, or which category is over budget. | Editable allocation and line items, deterministic totals/variance, estimate vs confirmed labels, and change preview. | Never ask the model to calculate authoritative money values; show unknown rates as unknown. |
| Vendor coordination | Quotes, questions, deposits, and follow-ups are spread across channels; users may mistake an idea for a booking. | Vendor-category checklist with user-managed status, contact/quote notes, next actions, and linked tasks. | Do not fabricate supplier identities, availability, quotations, or bookings. Mark user-entered vs verified information. |
| Scheduling | Tasks depend on one another and on the event date; generic lists do not reflect actual lead time. | Editable dated tasks/milestones, dependencies, owner/status fields, and conflict indicators. | Enforce date and dependency rules deterministically; flag missing dates rather than inventing certainty. |
| Guest-count changes | Attendance affects catering, seating, venue capacity, and operational work. | Ripple Engine preview of affected categories, task/vendor checklist, capacity, and budget. | Use configured rates/capacity/rules; mark incomplete calculations when inputs are absent. |
| Last-minute adjustments | Venue, weather, vendor, or schedule changes invalidate parts of a plan. | Recompute known affected dependencies, surface impacted tasks, allow editing and confirmation. | Never mark work complete or send/commit actions without the user's action. |
| Lack of personalized guidance | Generic themes and checklists ignore traditions, guest needs, interests, and priorities. | GPT-6 Luna uses user-provided context to propose themes, ideas, and priorities. | Show suggestions as editable; do not invent personal facts; respect stated hard constraints. |

## 4. User personas

These fictional archetypes represent the three required event types. They guide acceptance scenarios and do not imply research interviews.

### Wedding organizer — Maya

- **Context:** Organizing a 150-person wedding with a fixed total budget, several vendors, multiple family opinions, and meaningful traditions.
- **Goals:** Keep the budget credible, coordinate interdependent work, preserve the couple's style, and understand trade-offs before committing.
- **Pain points:** Quote/deposit uncertainty; guest count changes affect food, seats, invitations, and venue capacity; vendor and family schedules conflict; checklists are generic.
- **Constraints:** Hard budget ceiling, venue capacity, event date, accessibility/tradition needs, and a decision-making workload with limited spare time.
- **Needs from MomentOS:** Separate estimates from confirmed user inputs; a personalized editable plan; vendor follow-ups; dependency-aware timeline; clear Ripple preview and confirmation.
- **Success:** Can answer “What will changing attendance cost and affect?” before the saved plan changes.

### Birthday planner — Jordan

- **Context:** Planning a milestone birthday for a family member, without a dedicated planning team, over several weekends.
- **Goals:** Make the event feel personal, stay within a firm budget, and handle age-diverse guest needs without excessive coordination overhead.
- **Pain points:** Unclear cost trade-offs; uncertain RSVPs; generic theme ideas; venue/food/decor tasks fall through; a weather or venue change can invalidate the plan.
- **Constraints:** Budget ceiling, date/location, guest-of-honor preferences, family/access needs, and limited planning time.
- **Needs from MomentOS:** Preference-aware concepts; an editable checklist and timeline; budget choices grounded in entered prices; guest-count and schedule change preview.
- **Success:** Turns a personal idea into an achievable plan and adapts it without rebuilding the plan from scratch.

### Community event coordinator — Priya

- **Context:** Coordinating a neighborhood cultural gathering with volunteers, multiple activities, limited funds, and turnout that may grow.
- **Goals:** Keep the event safe and accessible, coordinate volunteer/vendor work, reflect community context, and stay within available funds.
- **Pain points:** Attendance uncertainty against firm capacity; split spending; unclear task ownership; multiple activity schedules; weather or cancellation disruptions.
- **Constraints:** Venue capacity and access rules, budget sources, volunteer availability, event date, and locally relevant practices.
- **Needs from MomentOS:** Context-aware but editable ideas; capacity and budget warnings; task/vendor coordination; change impacts for turnout and schedule.
- **Success:** Understands operational and financial effects of a turnout/disruption scenario and confirms a feasible response.

## 5. End-to-end user journeys

### Wedding journey

| Step | User action | MomentOS response | User-visible result |
|---|---|---|---|
| 1. Create | Enters wedding type, date/location, approximate attendance, budget, and known hard constraints. | Validates available fields and creates a persistent event workspace; identifies required but missing inputs. | A saved event the organizer can continue editing without completing every field first. |
| 2. Describe | Adds couple preferences, traditions, accessibility needs, priorities, and things to avoid in natural language. | GPT-6 Luna returns typed candidate requirements and concept suggestions for review. | Clear proposed interpretation, with unknowns and assumptions called out. |
| 3. Review blueprint | Edits and accepts relevant items. | Builds an editable initial budget allocation, milestones, tasks, and vendor checklist from confirmed data. | A command center with actionable next steps, not a static response. |
| 4. Track | Enters vendor quote/deposit details and updates task statuses. | Recalculates totals deterministically and keeps quote/source/status distinct. | A reliable view of known costs, remaining funds, open questions, and upcoming work. |
| 5. Simulate | Changes attendance from 150 to 200 and opens Ripple Engine. | Computes catering delta from configured per-person rate, seating from configured seating capacity, venue capacity warning, affected categories/tasks/vendors, budget variance, and missing invitation assumptions. | Before/after impact with each assumption and unresolved input visible. |
| 6. Decide | Edits proposed adjustments, confirms selected changes, or cancels. | Persists only on explicit confirmation; cancellation leaves event state unchanged. | Organizer remains in control of the saved plan. |
| 7. Prepare | Updates task dates/vendor status as the event approaches. | Re-evaluates date/dependency conflicts and displays unresolved tasks. | Current checklist and timeline for the event. |

### Birthday journey

| Step | User action | MomentOS response | User-visible result |
|---|---|---|---|
| 1. Create | Enters birthday date, location/venue status, attendance estimate, budget, and constraints. | Saves a draft workspace and requests missing details only as needed for a plan. | A usable starting point even when RSVP or venue details are unknown. |
| 2. Personalize | Describes guest-of-honor interests, preferred atmosphere, age range/access needs, and exclusions. | GPT-6 Luna proposes a structured, editable concept and relevant ideas grounded in those details. | Ideas with a visible connection to user-provided preferences. |
| 3. Plan | Reviews the concept and accepts/edits plan items. | Generates editable budget categories, timeline, tasks, and vendor checklist. | A clear “what to decide/do next” view. |
| 4. Compare | Adds known prices and adjusts optional items. | Computes totals and remaining budget deterministically; identifies trade-offs. | Spend decisions based on entered costs rather than model-created prices. |
| 5. Adapt | Changes attendance or records a venue/date change. | Previews affected catering, seating/capacity, timing, and relevant tasks/vendors. | A current impact summary before plan mutation. |
| 6. Confirm and prepare | Confirms selected adjustments, checks off tasks, and revises schedule as needed. | Persists confirmed changes and status updates; shows remaining tasks and conflicts. | A recoverable plan for last-minute adjustments. |

### Community event journey

| Step | User action | MomentOS response | User-visible result |
|---|---|---|---|
| 1. Create | Enters event purpose/type, date/location, expected attendance, budget, venue capacity, and known access constraints. | Creates a persistent workspace and highlights missing hard constraints. | A central plan for coordinators and their work. |
| 2. Explain context | Describes community, traditions, audience, activities, accessibility, and volunteer capacity. | GPT-6 Luna interprets context into candidate activities, ideas, and planning requirements. | Coordinator can correct the interpretation before relying on it. |
| 3. Organize | Confirms activities and adds vendors/volunteer tasks and timing. | Provides an editable checklist/timeline with owners, dependencies, and dates. | Clear work ownership and event milestones. |
| 4. Track | Enters known costs and revises attendance. | Computes totals and capacity effects from entered values and configured venue limits. | Visible budget/capacity status and unresolved estimates. |
| 5. Respond | Previews a turnout increase, cancellation, or schedule change. | Identifies known affected budget items, capacity, tasks, and vendor checklist entries; GPT may explain feasible options. | A concise operational impact view before changes are saved. |
| 6. Confirm and coordinate | Edits and confirms the response; updates task/vendor status. | Persists only confirmed updates and keeps the current schedule/checklist visible. | Coordinators can act from a current plan without fabricated completions. |

## 6. Detailed feature requirements

| ID / priority | Requirement | Testable completion condition |
|---|---|---|
| **FR-01 / P0 — Event creation** | Create and edit wedding, birthday, and community events from structured fields or a natural-language description. Store event type, date/time/timezone as known, location/venue status, expected attendance, currency, budget, preferences, and constraints with validation. | Each event type can be created, edited, reloaded, and identified as a distinct supported type. Missing optional details are represented as unknown, not invented. |
| **FR-02 / P0 — GPT interpretation** | Send bounded user input only through the backend to exact model `gpt-6-luna` via the official SDK Responses API. Return typed, schema-validated candidate event details/requirements and handle unavailable/refused/malformed responses. | Output is reviewable; invalid output never silently becomes trusted plan data; no model substitution occurs. |
| **FR-03 / P0 — Generated blueprint** | Produce an editable event concept/plan with personalized ideas, initial budget categories, timeline milestones/tasks, and vendor checklist. Identify assumptions, unknown rates, and suggestions vs user-confirmed facts. | Blueprint exists for all three event types and each item can be reviewed/edited; nothing is represented as booked/completed without user input. |
| **FR-04 / P0 — Smart Budget Studio** | Maintain total budget, editable category allocations and cost lines, estimate/confirmed labels, and remaining/over-budget result. Calculate money in deterministic backend logic with defined currency precision and rounding. | Totals and variances reconcile exactly to entered values; changing an amount updates the deterministic result; unpriced items remain unpriced rather than receiving hallucinated values. |
| **FR-05 / P0 — Event Command Center** | Summarize event details, budget state, guest count, upcoming/overdue tasks, vendor checklist status, and unresolved decisions for one event. | Dashboard fields match persisted event state and update after confirmed edits. Empty/incomplete states explain the next action. |
| **FR-06 / P0 — Timeline & task planner** | Provide editable tasks/milestones, due dates, status, optional owner, and dependency links. Validate impossible dates/dependency order and surface conflicts. | Dates and dependencies are deterministic; moving a task/date updates conflict indicators; AI suggestions remain drafts until reviewed. |
| **FR-07 / P0 — Vendor checklist** | Provide an editable checklist of vendor categories/follow-ups, linked tasks, and user-entered vendor/contact/quote/status information. | Users can distinguish suggestion, contacted, user-entered quote, and confirmed booking states; the system never infers a booking or market price. |
| **FR-08 / P0 — Ripple preview** | Simulate an input change (at minimum guest count) and return before/after values, affected costs/categories/tasks/vendors, capacity/seating implications, budget variance, unresolved inputs, and alternatives where calculable. | Same input and same configured rates yield same result; unknown capacity/rate/rule is explicitly marked incomplete; no persistent write occurs during preview. |
| **FR-09 / P0 — Confirmation gate** | Let the user inspect, revise, apply selected proposals, or cancel a Ripple preview. | Preview/cancel leaves saved data unchanged; only explicit confirmation writes selected changes; post-save dashboard/budget/tasks match the confirmed state. |
| **FR-10 / P0 — Persistence and isolation** | Persist event data across reloads and ensure each session can access only its own events. | Data survives restart/reload in supported configuration; cross-session read and mutation attempts fail without disclosure. |
| **FR-11 / P0 — Offline demonstration** | Provide deterministic local demo data/behavior when live AI is unavailable or not configured, clearly identifying demo mode. | Every demo-generated concept or answer has a visible demo label; UI/API never reports it as a successful OpenAI call. Core event viewing, editing, calculations, and preview can be demonstrated without live AI. |
| **FR-12 / P0 — Public deployment** | Release the working application at a functioning public URL through an authorized deployment path. | Reviewer can open the URL and complete the core flow without private developer credentials. Deployment is a release deliverable only after deployment authorization; this analysis does not perform it. |
| **FR-13 / P1 — AI Event Copilot** | Answer event-specific questions using bounded, ownership-checked event context and explain deterministic results. | Answer is grounded in provided event data, distinguishes unknowns, respects constraints, and never writes a change. |
| **FR-14 / P1 — Vendor Workspace** | Expand checklist to organize contacts, communications/next actions, user-entered quote comparisons, and status history. | Every price/status has a user/application source and no generated fact is represented as verified. |
| **FR-15 / P1 — Scenario comparison** | Compare saved or proposed alternatives such as attendance, budget, or venue constraints. | Each scenario is reproducible and shows differences from a baseline; comparison alone does not mutate the baseline. |
| **FR-16 / P1 — Recommendations and polish** | Offer tailored optimization and theming suggestions with clear rationale and constraint checks. | Suggestions refer to supplied preferences and calculated constraints, are editable, and are labeled as suggestions. |
| **FR-17 / P2 — Collaboration** | Support multiple authorized planners/roles if core single-session ownership is secured. | Role and ownership behavior is explicit and tested before release. |
| **FR-18 / P2 — Integrations/notifications** | Consider external vendor integrations and automated reminders only after core product quality and explicit service/security review. | No integration may claim vendor availability/bookings without trustworthy connected data and user authorization. |

## 7. Functional and nonfunctional requirements

### Functional requirements

1. **Event lifecycle:** Create, read, edit, and persist all supported event types; represent unknown information without blocking unrelated planning.
2. **Requirement extraction:** Interpret natural language into a typed, reviewable draft using the locked model. Present field-level validation and preserve the user's ability to correct it.
3. **Plan generation:** Provide a blueprint with personalized ideas, budget categories, tasks/milestones, and vendor checklist; distinguish accepted facts, proposed suggestions, and missing data.
4. **Budget operations:** Support user-defined currency, budgets, allocations, and line items; deterministically calculate sums, remaining budget, deltas, and overruns. Use decimal/minor-unit-safe arithmetic and declared rounding rules.
5. **Schedule operations:** Maintain event-relative dates, task status and dependencies; prevent/flag invalid date order and surface downstream tasks affected by a change.
6. **Capacity/guest operations:** Compare expected attendance and seat demand against user-entered capacity/configured seating rules. Missing capacity does not mean capacity passed.
7. **Ripple workflow:** Preview → inspect → edit/choose → explicitly confirm or cancel. Compute with authoritative application rules; explain with AI only after deterministic results exist.
8. **Vendor checklist:** Track user-entered vendor leads, quotes, contact/status and related tasks; never claim external validation unless a real trusted source supplies it.
9. **Copilot and personalization:** Use only relevant bounded event context; answer and suggest without direct database mutation.
10. **Offline demo and recovery:** Continue deterministic core flows with clearly labeled fixtures when AI is absent; show actionable loading/error/refusal/timeout states.
11. **Public release:** Deliver a reviewer-accessible URL when deployment is authorized, along with requested demo/submission materials only when separately authorized.

### Nonfunctional requirements

| Quality | Requirement/target |
|---|---|
| Security/privacy | Keep credentials server-side; redact secrets; validate and bound requests; isolate session-owned data; protect cookie mutations against CSRF; require confirmation for proposed changes. |
| Correctness | Financial, date, capacity, dependency, and Ripple outputs are deterministic for identical inputs/configuration. Show precision, assumptions, source, and missing inputs. |
| Reliability | Model/API failures, malformed/refused output, and timeouts produce recoverable states; saved user data and deterministic operations remain usable. No silent model switch. |
| Performance | Keep interaction responsive and bound AI work. Proposed target: deterministic Ripple calculations under 200 ms for up to 500 tasks on the reference dev environment; track network/model timing separately. |
| Cost control | Bound prompt/output sizes; avoid redundant generation; apply rate limits/timeouts/bounded retries; record model/usage and estimated cost without credentials. |
| Accessibility | Keyboard-complete core flows, visible focus, named/associated controls and errors, accessible dialogs, text alternatives to charts, no serious/critical axe findings, usable at 200% zoom and narrow mobile width. |
| Maintainability | Typed API contracts and schema validation; deterministic domain calculations independently testable; database migrations support SQLite development and PostgreSQL production. |
| Responsiveness | Core create, review, edit, simulate, confirm, dashboard, and task flows work on mobile and desktop. |
| Honesty/provenance | Show whether content is user-provided, deterministic calculation, AI suggestion, demo fixture, estimate, confirmed quote, or verified external data. Do not imply evidence that does not exist. |

Proposed numeric performance/coverage targets are planning targets, not measured results. Revisit only through the ordered prompt-engine stages; do not weaken locked architecture to meet them.

## 8. AI vs deterministic responsibility matrix

| Work item | GPT-6 Luna responsibility | Deterministic/application responsibility | Persistence/validation rule |
|---|---|---|---|
| Natural-language intake | Extract candidate fields, preferences, constraints, and questions into Structured Outputs. | Validate schema, type/range, required fields, timezone/currency formats; detect conflicts. | User reviews and corrects extraction before accepting it as event data. |
| Personalized concepts and ideas | Propose themes, activities, wording, and options grounded in user-provided context. | Enforce encoded hard budget/date/capacity/accessibility constraints; label unsupported assumptions. | Editable suggestions only; no invented personal facts. |
| Blueprint and task draft | Suggest event-specific milestones, task names, vendor categories, and planning questions. | Validate task shape, date bounds, dependency graph, and user-entered owners/statuses. | Generated tasks remain proposed until reviewed; never mark complete or booked. |
| Budget arithmetic | Explain deterministic totals/trade-offs in plain language; suggest qualitative savings ideas. | Currency arithmetic, category totals, allocations, rate multiplication, remaining budget, delta, rounding, and overrun. | Numbers shown from backend calculation results; model cannot override or recalculate authority. |
| Schedule | Suggest a draft sequence and planning lead-time ideas. | Date/time math, event-date bounds, prerequisite ordering, conflict detection, downstream impact. | User reviews dates; hard conflicts block or require correction rather than being ignored. |
| Vendor work | Suggest vendor categories and questions to ask. | Store contact, source, quote, status, task relation; calculate user-entered quote differences if requested. | No fabricated real vendor, price, availability, booking, or response. Only a trusted user/connected source can supply such facts. |
| Capacity/seating | Explain implications and suggest options after results exist. | Attendance versus user-entered capacity; seats/tables based on configured seats per unit with explicit ceiling rule. | Unknown capacity/rule yields “unknown/incomplete,” not “fits.” |
| Invitations | Explain that guest count may affect invitation workload. | Calculate only when an explicit rule such as invites per household/party is supplied. | Never assume one invitation per guest; unresolved rule is surfaced. |
| Ripple Engine | Explain validated before/after results and recommend alternatives based on allowed inputs. | Compute cost, budget, capacity, seating, impacted categories and dependency graph; produce a preview diff. | Preview is read-only. Only explicit user confirmation persists selected changes. |
| Copilot response | Answer questions from bounded, relevant event context and explain known results. | Enforce ownership, context bounds, exact model/config, output schema, policy and constraint validation. | Read-only unless a separate typed proposal/confirmation flow exists. |
| Offline mode | None; do not impersonate live AI. | Serve deterministic labeled example data and calculations. | UI identifies demo mode and never records a successful provider call. |

## 9. Feature priority

### P0 — Essential release path

- Event creation and editing for all three event types.
- GPT-6 Luna-powered interpretation via the backend with typed output and failure handling.
- Generated, reviewable event blueprint.
- Editable budget allocation with deterministic totals and variance.
- Event Command Center dashboard.
- Ripple Engine preview and explicit confirmation gate.
- Timeline, tasks/dependencies, and vendor checklist.
- Persistent event state and session isolation.
- Deterministic, clearly labeled offline demo.
- Functioning public deployment as a release requirement after explicit deployment authorization.

P0 is one complete vertical flow, not disconnected mock screens: create → interpret → review/edit plan → budget/tasks → simulate → confirm/cancel → reload persistent state.

### P1 — Competitive after P0 works

- Context-aware, read-only AI Event Copilot.
- Richer Vendor Workspace with user-entered quote/contact/status organization.
- Scenario comparison against a baseline.
- More personalized recommendations and constraint-aware cost optimizations.
- Visual polish, useful charts, purposeful motion, and well-crafted loading/empty/error states.
- Broader Ripple coverage for date, venue, and schedule changes.

### P2 — Optional after core quality is secure

- Advanced collaboration and roles.
- External vendor integrations.
- Automated notifications/reminders.
- Other analytics, integrations, or features that do not displace P0 quality.

## 10. Risk assessment

| Risk | Likelihood / impact | Prevention and recovery | Acceptance evidence |
|---|---|---|---|
| API latency, timeout, or outage | Medium / High: plan generation may stall or be unavailable. | Show progress and timeout state; bounded timeout/retries; preserve entered data; offer labeled deterministic offline demo; allow retry without duplicate writes. Never swap models. | Simulate timeout/provider outage; user can recover, keep event data, and identify demo vs live output. |
| Invalid, incomplete, refused, or schema-mismatched output | Medium / High: bad fields could corrupt a plan or violate constraints. | Parse and validate Structured Outputs; handle refusal/missing fields; apply business validation after schema validation; show recoverable error/retry; do not trust partial output. | Malformed/refused/incomplete responses do not persist or appear as valid completed plans. |
| API cost or redundant requests | Medium / Medium: repeated generation can raise spend and latency. | Bound input/output and context; rate limit; avoid duplicate calls; use low/medium reasoning strategically; record usage and estimated cost without secrets. | Usage records include model/usage metadata but no key; oversized and repeated requests follow limits. |
| Hallucinated vendor information | Medium / High: false quote/availability/booking can cause financial or logistical harm. | Constrain AI to categories/questions/recommendations; label user-supplied vs verified data; never assert real availability/quotes without a trusted source. | Requests for vendor quotes/availability yield no fabricated factual claims or booking state. |
| Exposed API key | Low / Critical: unauthorized use and charges. | Backend-only secret configuration; `.env` ignored; no key in frontend bundle, source, docs, telemetry, or logs. | Secret scan/build inspection finds no credential; logging tests redact values. |
| Session data leakage | Low / Critical: one planner could see or change another event. | Enforce ownership at every read/write boundary; secure session cookies; CSRF on cookie-authenticated mutations; recheck authorization before confirmation. | Two-session tests prove cross-session read/preview/confirm attempts disclose or modify no data. |
| Incomplete functionality / fake interactions | Medium / High: evaluator sees attractive but unusable screens. | Prioritize one vertical P0 workflow; each control performs a real action or is clearly disabled; persist data and recover from errors. | End-to-end create → plan → preview → confirm → reload works for all event types; offline flow also works. |
| Scope creep | High / Medium: optional features displace stable core. | Hold P0/P1/P2 boundary; defer collaboration/integrations/notifications until P0 acceptance passes; reject unplanned architecture changes. | Handoffs show P0 status/deferred list; no P2 work begins while P0 acceptance fails. |
| Incomplete source data / false precision | Medium / High: a calculation can look authoritative while rates/capacity are unknown. | Track input provenance and assumptions; calculate only from known rates/rules; display incomplete results and request inputs. | Missing rate/capacity/invitation rule yields explicit unknowns, never fabricated zero-cost or pass results. |
| Unconfirmed AI change persisted | Low / High: a suggestion overrides user intent. | Make preview read-only; require explicit confirmation; ensure cancel/back do not mutate; validate proposed diff server-side at confirmation. | State remains unchanged on preview/cancel; changes appear only after explicit confirmation. |

Likelihood ratings are initial planning judgments, not measured incident rates.

## 11. Acceptance tests

These are release-level scenarios for later implementation and verification; they have not been executed in Stage 01.

### AT-01 — Event creation and persistence

For each event type, create an event with a date, estimated attendance, budget, and some unknown fields. Confirm it is saved, editable after reload, and missing information remains marked unknown rather than silently filled.

### AT-02 — Natural-language interpretation and blueprint

Submit an event description with preferences and constraints. With live AI configured, the backend uses exactly `gpt-6-luna` via the Responses API, returns schema-valid candidate fields and a blueprint, and asks the user to review them. An invalid/refused/unavailable response yields a recoverable state and no false “AI succeeded” claim. With AI unavailable, the labeled offline demo can still exercise deterministic planning.

### AT-03 — Personalization and provenance

Provide a preference and an exclusion (for example, “outdoor garden feel; avoid loud activities”). Generated suggestions reflect both. The system does not invent a personal fact, vendor quote, booking, or completed task. User-provided, confirmed, demo, estimate, and AI suggestion states are distinguishable.

### AT-04 — Budget arithmetic and allocations

Enter a budget and line items with known amounts. Verify totals, remaining amount, category allocations, and overrun match deterministic arithmetic exactly under declared currency rounding rules. Change one amount and verify appropriate totals/variance change. A cost with no entered rate remains unknown, not zero or an AI estimate presented as fact.

### AT-05 — Schedule dependencies and constraints

Create tasks A → B where B depends on A. Set B earlier than A or beyond a hard event-date constraint. The application blocks the invalid state or presents a clear unresolved conflict according to the chosen rule; moving A identifies affected downstream work. Identical inputs yield identical dependency results.

### AT-06 — Ripple guest-count preview

Use a deterministic fixture: wedding budget ₹6,00,000; 150 guests; existing catering allocation ₹1,50,000 based on an explicit ₹1,000 per-person rate; other entered allocations make current planned total ₹5,80,000; venue capacity 180; configured seating is 10 seats per table. Preview a change to 200 guests.

Expected preview: catering increases by ₹50,000 to ₹2,00,000; total planned spend becomes ₹6,30,000 (₹30,000 over budget); seating rises from 15 to 20 tables; venue capacity warning is shown; catering/budget and linked tasks/vendors are identified as affected. If invitation-per-party rules are absent, invitation impact is marked unknown/needs input rather than assuming one invitation per guest. Suggested savings do not alter the calculation or persisted plan.

### AT-07 — Confirmation/cancellation gate

For AT-06, inspect and cancel the preview; reloading shows the original event unchanged. Repeat, explicitly confirm selected changes, and verify only those selections persist and the dashboard/budget/task views update consistently. The model cannot bypass confirmation.

### AT-08 — Capacity and missing data

For configured capacity below expected attendance, show a warning and operational impact. With no capacity or seating rule, state that the check is incomplete; do not claim the venue fits or invent table requirements.

### AT-09 — Vendor information integrity

Ask for a real vendor quote or availability without a connected trusted source. The assistant may suggest a vendor category or questions, but does not assert real quote, availability, or booking. User-entered quotes retain their source/status.

### AT-10 — Session isolation and CSRF

Create two independent sessions and events. Session B cannot list/read/simulate/confirm changes to Session A's event. Cookie-authenticated state-changing requests without a valid CSRF token are rejected without mutation.

### AT-11 — Offline and provider failure handling

With no API key, unavailable model, timeout, refusal, or malformed response, show a recoverable status and clearly label deterministic demo content. Do not claim a successful OpenAI response or silently use another model. Existing event data and deterministic calculations remain usable.

### AT-12 — Core accessibility and responsive use

Complete create, edit, Ripple preview, confirmation/cancel, and task operations using keyboard only. Verify focus, accessible labels/errors/dialog handling, text alternatives for charts, no serious/critical automated accessibility violations, and usable layout at 200% zoom and narrow mobile width.

### AT-13 — Public reviewer flow

After deployment is explicitly authorized, open the public app URL in a clean browser context and complete the P0 path without developer-only credentials. Verify configured backend model/service behavior or clearly labeled demo mode and ensure no secrets are exposed. This test has not been run and does not authorize deployment.

## 12. Recommended MVP delivery order

Keep the frozen prompt-engine sequence unchanged. Recommended deliverables through that sequence:

1. **Stage 02 — Ideation:** Select the smallest coherent P0 flow, product concept, and priorities; avoid optional integrations.
2. **Stage 03 — Final Context:** Freeze event fields, provenance, confirmation semantics, budget/date/capacity rules, API boundaries, and acceptance scenarios before implementation.
3. **Stage 04 — Frontend:** Create the accessible, responsive flow and explicit loading/error/demo states using `/gpt-taste`; keep UI actions connected to a clear contract, not fake success interactions.
4. **Stage 05 — Backend:** Implement persistence, session isolation, typed validation, deterministic budget/schedule/capacity/Ripple functions, then exact GPT-6 Luna Responses API integration and bounded usage/error handling. Follow the locked stage even though backend responsibilities are described here.
5. **Stage 06 — Integration:** Complete create → interpret → review/edit → budget/tasks → Ripple preview → confirm/cancel → persist/reload; verify offline mode and consistency across views.
6. **Stage 07 — DOM Verification:** Exercise all event types, guest-count Ripple scenario, keyboard/accessibility, responsive layouts, session boundaries, failure recovery, and public reviewer flow once deployment is authorized.
7. **Stage 08 — Demo Script:** Demonstrate a complete scenario and disclose live AI vs offline demo behavior; prepare submission materials only when separately authorized and supported by actual results.

No deployment, publication, paid service activation, repository publication, or competition submission is performed by this specification. Public deployment is a P0 outcome but still requires the authorization stated in the master system.
