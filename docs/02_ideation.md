# Stage 02 — Product Ideation

**Status:** Product concept and prioritization for Stage 03 handoff. This document is not a final visual design or an implementation specification. It preserves the Stage 01 requirements, architecture, and nine-stage workflow.

## Product positioning

### Position

**MomentOS turns a celebration idea into a working plan—and shows what each decision changes.**

MomentOS is a connected event-planning workspace for hosts and coordinators. It combines natural-language planning with an editable command center for the budget, timeline, tasks, venue constraints, and vendor checklist. Its core distinction is that a plan remains explainable as it changes: users see the cause, financial and operational effects, assumptions, risks, and available next steps before approving a change.

The tagline remains **“The AI Operating System for Every Celebration.”** The product experience should feel like a dependable planning partner and a living plan, not a chatbot transcript or a set of unrelated feature pages. Conversation is an input to the workspace; saved, reviewable event information is the shared source of truth.

### Promise and proof

- **Promise:** Describe the occasion, get a personalized starting plan, and understand the consequences before changing it.
- **Proof:** A complete event journey; deterministic budget and dependency results; visible assumptions and provenance; a “Why this changed” impact trail; and an explicit confirmation step.
- **Trust boundary:** GPT-6 Luna interprets, drafts, personalizes, and explains. Python business rules calculate money, schedule and dependency changes, seating, capacity, and Ripple results. The user approves persisted changes.

## Differentiating features

### 1. Ripple Engine “Why this changed” impact trail

Ripple Engine is the flagship experience. It explains both **what changed** and **why** by presenting a cause-linked trace:

1. **Trigger:** The user changes a planning variable, such as attendance from 150 to 200.
2. **Direct calculation:** Show the exact configured rule and inputs, such as `50 additional guests × ₹1,000 per guest = +₹50,000 catering estimate`.
3. **Downstream effects:** Surface impacted budget categories, capacity/seating checks, dependent tasks, vendor follow-ups, and invitation implications.
4. **Risks and unknowns:** Identify a budget overrun, exceeded capacity, missing rate, or missing invitation-per-household rule. Unknown is not treated as safe or zero.
5. **Possible responses:** Offer a small number of editable options. GPT-6 Luna may explain them; deterministic rules recalculate any numerical option.
6. **Decision:** The user selects, edits, and explicitly confirms changes, or cancels. Preview and cancel do not mutate saved event data.

The preview uses readable text and clear before/after values. A causal connector or other visual treatment may reinforce the chain, but color or motion must never be the only way to convey it. After a confirmed change, a compact **change receipt** can summarize the trigger, inputs and their sources, computed effects, selected actions, and confirmation time. It gives users a durable explanation without allowing the model to create an audit record of an unconfirmed action.

### 2. Provenance at the point of decision

Keep facts and suggestions distinct wherever users make a decision:

- **You entered** — user-provided event data or quotation.
- **Planning assumption** — illustrative, editable rate or quantity.
- **Calculated** — deterministic result derived from visible inputs.
- **AI suggestion** — editable idea or recommendation, not a fact.
- **Needs input** — a required value is unknown.
- **Verified source** — reserved for data actually returned by a connected trusted source; no such integration is assumed for the MVP.
- **Offline demo** — deterministic fixture/example; never presented as a live model response.

These labels make the budget and the AI useful without implying that a generated number is a market quote or a generated task is complete.

### 3. A plan that stays connected

An accepted event brief feeds the same event workspace: its budget categories, task and milestone list, vendor-category checklist, and relevant dashboard summaries. A user change refreshes the affected deterministic results rather than leaving disconnected cards or obsolete text. The plan is always editable; a generated blueprint is a starting draft, not a locked output.

## Selected product modules and interaction concepts

All eight modules remain part of the product concept. The MVP implements the useful core of each P0 surface and defers deeper P1 capabilities until the end-to-end planning loop works. **Moment Map** is the proposed user-facing name for the milestone/timeline experience called Timeline & Task Planner in Stage 01; this is a naming choice, not an architecture change.

| Module | User interaction concept | MVP selection |
|---|---|---|
| **AI Event Architect** | A guided event composer combines structured fields with an optional natural-language description. The user can leave details unknown, review extracted preferences/constraints, correct the event brief, then ask for a blueprint. | **P0:** event-type-aware intake, typed interpretation, review/edit, and generated plan. |
| **Event Command Center** | One event home answers: “What is settled?”, “What needs attention?”, and “What changed?” It highlights budget health, progress grounded in real task status, next milestones, vendor checklist state, and a small number of relevant recommendations. | **P0:** saved event summary and actionable next steps; avoid unsupported progress scores. |
| **Budget Studio** | Editable categories and line items show planned amount, estimate/quote status, source, remaining budget, and over/under result. Charts have a table/text equivalent. | **P0:** deterministic totals, allocations, and warning states; richer comparisons in P1. |
| **Ripple Engine** | Change a variable, inspect the causal impact trail and before/after values, choose proposed adjustments, and confirm or cancel. | **P0 flagship:** guest-count simulation with cost, seating/capacity, affected tasks/vendors, budget variance, and “needs input” states. |
| **Moment Map** (Timeline & Task Planner) | Tasks are grouped by planning phase/date with owner, due date, status, and dependency; event-day activities can be viewed in sequence. Forms/buttons are sufficient—drag and drop is optional. | **P0:** editable milestones/tasks, owners/status, and basic dependency/date conflicts. Rich event-day mode is a later enhancement if time allows. |
| **Vendor Workspace** | A checklist for venue, food, music, photo/video, rentals, and other relevant categories; users can add contacts, notes, user-entered quotes, and selection status. | **P0 basic checklist:** categories, tasks, user-entered notes/status. **P1:** fuller quote comparison/contact history. No live availability claims. |
| **AI Event Copilot** | An event-aware, read-only helper explains known plan data and answers planning questions. It distinguishes recommendations from saved facts and links advice to supplied inputs. | **P1:** introduce after create/edit/Ripple flows; do not build a second generic chat product. |
| **Scenario Comparison** | Named alternatives compare outcomes such as 150 vs 200 guests or premium vs economical venue across budget, capacity, and tasks. | **P1:** compare read-only projections after the underlying Ripple calculation is stable. |

### Shared interaction rules

- Ask for only high-impact missing details when they are needed for a meaningful calculation; let users continue with unknown values where safe.
- Show the event type, source, date/location as known, budget, attendance, and constraints in an editable brief before accepting generated work.
- Keep all model requests behind the backend. Use the exact configured `gpt-6-luna` model; never silently switch models.
- Do not call the model on every keystroke or deterministic field change. Use explicit actions such as “Interpret description,” “Generate plan,” or “Explain these impacts.”
- Keep assumptions editable and display them beside calculations. A user can change the assumed rate or quantity and see the deterministic result update.
- Separate preview from commit. The final confirmation summarizes which specific plan fields will change.
- Provide semantic forms, buttons, keyboard-accessible dialogs, visible focus, text equivalents for chart data, and reduced-motion support. Drag-and-drop and color-only status are not required.

## AI integration opportunities

| Moment | Model role and effort | Typed/validated result | Keep out of AI |
|---|---|---|---|
| Parse a short event description | **Low** effort extraction. | Candidate event fields, preferences, hard constraints, missing questions, and confidence/uncertainty indicators under a bounded schema. | Persisting fields without user review; creating facts not in the prompt. |
| Generate a useful event blueprint | **Medium** effort when event-specific planning, personalization, and multiple constraints materially improve quality. | Editable concept, budget-category suggestions without authoritative amounts, proposed milestones/tasks, vendor categories, and a small number of personalized ideas. | Currency arithmetic, real vendor research, claimed availability/quotes, booked/completed states, database writes. |
| Explain Ripple results | **Medium** when several calculated consequences interact; **low** for a short explanation of one simple result. | Brief explanation that references supplied deterministic result IDs/values, followed by optional recommendation text. | Recomputing numbers or replacing a hard-rule warning with an ungrounded claim. |
| Generate a short checklist or answer a simple event question | **Low** effort. | Bounded items/answer grounded in the user's saved event and clearly labeled unknowns. | Repeating full plan generation, broad unbounded conversation context, changing persisted event state. |
| Recommend an adjustment | **Medium** if balancing several stated preferences and constraints. | Candidate alternatives with rationale, trade-offs, and references to known inputs. | Guaranteeing an alternative is feasible until deterministic validation/calculation succeeds. |

Use structured outputs and application validation. Keep context windows and response sizes bounded, record usage/cost estimates, and handle timeout, refusal, and malformed outputs with recoverable UI states. Offline demo mode uses deterministic sample data and carries an explicit demo label; it does not imitate an OpenAI response. No function calling is needed for the MVP because it adds no meaningful benefit to these user-confirmed planning flows.

## Feature feasibility assessment

Qualitative ratings use **High / Medium / Low**. Complexity and deadline risk are relative to a competition MVP; accessibility and reliability describe how achievable a good implementation is with the locked stack and trust rules. They are estimates, not measured project status.

| Feature | User impact | Challenge alignment | Complexity | Demo value | Accessibility feasibility | Reliability feasibility | Deadline risk | Decision |
|---|---|---|---|---|---|---|---|---|
| AI Event Architect | High | High | Medium | High | High | Medium | Medium | P0, bounded intake and reviewed structured plan. |
| Event Command Center | High | High | Medium | High | High | High | Medium | P0, derive summaries from saved plan data. |
| Budget Studio | High | High | Medium | High | High | High | Medium | P0, deterministic money and clear source labels. |
| Ripple Engine / “Why this changed” | High | High | High | Very high | Medium–High with text-first impact list | High when inputs/rules are explicit | High | P0, one reliable guest-count path before broader what-if coverage. |
| Moment Map | High | High | Medium | High | High as a semantic task list plus optional timeline | High with deterministic dates/dependencies | Medium | P0 basic tasks, ownership, milestones, dependencies. |
| Vendor Workspace | Medium–High | High | Medium | Medium | High | High for user-managed checklist; low for unsupported live vendor facts | Medium | P0 basic checklist; richer workspace P1. |
| AI Event Copilot | Medium | Medium–High | Medium | Medium | High if not chat-only | Medium | Medium | P1, event-aware read-only answers after core flow. |
| Scenario Comparison | Medium | Medium | High | High | Medium–High with table/text comparison | Medium–High once deterministic scenarios are stable | High | P1, defer multi-scenario UI until Ripple core is verified. |

Accessibility is a baseline across the product, not an optional feature. Text values, forms, keyboard operation, focus management, clear errors, and responsive layouts must be part of P0. A sophisticated graph or motion treatment is optional; accurate, understandable consequences are essential.

## Visual design direction (not final design)

The visual identity should feel **editorial, warm, and operationally calm**: a polished planning desk with a subtle sense of occasion. The experience needs enough warmth to feel personal and enough restraint for users to compare money, deadlines, risks, and decisions without distraction.

Direction for Stage 04, leaving exact style selection to the Visual Director:

- Use a strong typographic hierarchy and generous, consistent spacing so event identity, decision status, and next action are immediately clear.
- Explore celebration-inspired color as a controlled accent system for event identity and status, while keeping budget figures and warnings legible and consistent.
- Make charts explain a decision; pair each visualization with labels, totals, and a text/table alternative.
- Use motion sparingly to show an impact preview unfolding or an approved change settling into the plan. Respect reduced-motion preference and never use animation to obscure pending confirmation.
- Build a distinctive event workspace rather than a conventional pile of identical cards. Keep navigation and modules connected to the selected event.
- Design intentional empty, incomplete-data, loading, error, and offline-demo states. “Not enough information to calculate” is a designed state, not a blank chart.
- Exact palette, fonts, component style, spatial layout, and motion details are deliberately undecided here. Stage 04 must use `/gpt-taste` and choose one primary style and no more than two supporting styles.

## Demo storyboards

All prices, per-person rates, capacities, seating ratios, and category amounts below are **editable illustrative planning assumptions**, not live market quotations. Demo copy must say so. A live model response may be described as live only if the configured GPT-6 Luna request actually succeeded; otherwise show the offline-demo label.

### Shared demonstration arc

1. Start with a natural-language event idea and a few structured constraints.
2. Show the interpretation as a reviewable brief, including missing details.
3. Open the command center and show budget, next actions, and editable plan pieces.
4. Change one key value in Ripple Engine.
5. Follow the “Why this changed” trail from trigger to calculation to affected work and risk.
6. Review one or more recommendation options, then explicitly confirm or cancel.
7. End with the persisted plan and change receipt (or unchanged plan if canceled).

### A. Nagpur wedding — 150 guests, ₹6,00,000 budget

**Opening prompt:** “Plan a warm wedding in Nagpur for 150 guests. Keep the full celebration within ₹6,00,000 and help me understand what changes if the guest list grows.” Date, dietary requirements, actual venue capacity, and invitation-per-household policy are not supplied and must remain questions/unknowns.

**Editable demo baseline:** Set an illustrative catering assumption of ₹1,000 per person (₹1,50,000 at 150 guests), current total planned spend ₹5,80,000, venue capacity 180 if that input is selected, and 10 seats per table if that seating rule is selected. Other category amounts are clearly labeled editable assumptions whose sum with catering is ₹5,80,000. No amount is represented as a quote.

**Ripple beat:** Increase attendance from 150 to 200. The deterministic trail shows catering +₹50,000; new planned total ₹6,30,000, or ₹30,000 over budget; capacity warning (200 > configured 180); seating rises from 15 to 20 tables under the 10-seat assumption; catering/budget and linked venue/seating follow-up tasks are affected. Invitation quantity is “needs input” until the user supplies an invitation-per-household rule.

**Decision beat:** MomentOS presents actions such as reviewing the venue limit, revising the catering assumption/menu scope, or identifying at least ₹30,000 of budget changes. Any proposed savings are separately editable and recalculated by deterministic rules. The user selects and confirms or cancels; no automatic save occurs.

**Demonstration value:** Makes the competition's budget/timeline/vendor needs tangible and shows the Ripple differentiator in a single legible, arithmetic-checkable story.

### B. Birthday celebration — 60 guests, ₹80,000 budget

**Opening prompt:** “Plan a joyful birthday for 60 people with a ₹80,000 budget, good food, and a small activity for kids.” Location, age, date, venue, and dietary needs are asked or marked unknown rather than assumed.

**Editable illustrative baseline:** Venue ₹15,000; food at ₹450/person = ₹27,000; cake ₹6,000; décor ₹10,000; activity/entertainment ₹8,000; favors at ₹100/person = ₹6,000; contingency ₹8,000. Total: ₹80,000. Every amount and per-person rate is editable and marked illustrative.

**Ripple beat:** Raise attendance from 60 to 75. Deterministic food increase is ₹6,750 and favor increase is ₹1,500; total impact +₹8,250, revised planned total ₹88,250, or ₹8,250 above budget. Show 15 additional seats/favor units and request venue capacity if it is unknown.

**Decision beat:** Offer ways to edit assumptions or reduce a category; explain the corresponding trade-offs, recalculate amounts, and ask for confirmation. AI may suggest more age-appropriate activity ideas using supplied preferences but cannot invent the guest of honor's interests.

**Demonstration value:** Shows that MomentOS personalizes around stated preferences while keeping a small household budget and guest-related changes understandable.

### C. Community gathering — 300 attendees, ₹1,50,000 budget

**Opening prompt:** “Help our neighborhood plan an accessible community gathering for about 300 people, keeping essentials covered and the spend under ₹1,50,000.” Date, venue capacity, access requirements, permit requirements, and volunteer availability are input questions, not assumptions.

**Editable illustrative baseline:** Venue ₹20,000; food/water at ₹250/person = ₹75,000; AV ₹15,000; permits/safety planning allowance ₹10,000; signage/materials ₹8,000; volunteer logistics ₹7,000; contingency ₹15,000. Total: ₹1,50,000. Mark all as planning assumptions, not local quotes or legal advice.

**Ripple beat:** Raise attendance from 300 to 360. Food/water increases by ₹15,000; revised planned total becomes ₹1,65,000, ₹15,000 over budget. Show 60 more places/food units, ask for venue capacity, and identify volunteer/supply and vendor follow-ups for review.

**Decision beat:** Coordinator can inspect changes, update known capacity and volunteer inputs, consider optional spending alternatives, and confirm only the selected plan changes. The system does not claim a venue is safe or compliant from an unknown capacity/permit field.

**Demonstration value:** Shows support beyond private celebrations and connects attendance changes to capacity, volunteer work, budget, and accessibility needs.

### Demo presentation and disclosure

The product should be able to load the three representative examples as clearly labeled editable demo events. A polished walkthrough can go deep on the wedding Ripple path and use the birthday/community stories to show breadth without building a separate application for each event type. Keep a persistent but unobtrusive state label: **Live AI** only after a real successful GPT-6 Luna response, otherwise **Offline demo — sample plan and illustrative assumptions**. Never pass an offline fixture off as AI output, and never label an illustrative amount a vendor quotation.

## MVP scope

### Include

- One cohesive, persistent event-planning workspace supporting weddings, birthdays, and community events.
- Guided AI Event Architect with structured intake, low-effort extraction, medium-effort plan generation when it adds value, review/edit, and clear handling of missing information.
- Generated editable blueprint with concept, budget categories, tasks/milestones, vendor-category checklist, and personalized ideas.
- Command Center that reflects saved event data and highlights actual next steps.
- Budget Studio with editable illustrative assumptions/user-entered amounts and deterministic totals, remaining balance, and warnings.
- Moment Map basic milestone/task list with owners, deadlines, statuses, dependencies, and schedule constraints.
- Vendor category checklist with user-entered contact/estimate/status and clear provenance.
- Flagship guest-count Ripple path: before/after preview, deterministic catering/seat/capacity/budget/task impacts, “Why this changed” trail, missing-input warnings, recommendation options, explicit confirmation/cancel, and a change receipt after confirmation.
- Clearly labeled deterministic offline demo; provide wedding, birthday, and community scenarios with adjustable illustrative assumptions.
- Accessible loading, empty, error, offline, and confirmation states; mobile-responsive core flow.
- Public deployment as a release requirement only after explicit deployment authorization.

### Add after the complete P0 loop is reliable (P1)

- Read-only contextual AI Copilot.
- Richer Vendor Workspace and quote comparison for user-entered information.
- Named scenario comparison (for example 150 vs 200 guests or premium vs economical venue).
- Broader Ripple inputs, optional budget visualizations, and additional personalization.

## Excluded from the MVP and why

| Excluded/deferred capability | Reason |
|---|---|
| Real-time vendor search, quote fetching, availability, booking, or payment | Requires trustworthy external data, integration/security work, and would risk fabricated or misleading vendor claims. The challenge can be met with a useful user-managed checklist. |
| Advanced multi-user collaboration/roles | Adds ownership, permission, and coordination complexity before the single-session planning loop is proven. |
| Automated email/SMS/push reminders | Adds third-party setup, privacy, and delivery reliability work; a clear persisted timeline/checklist is higher priority. |
| Autonomous agents, tool-driven purchasing, or model-controlled event updates | Violates explicit confirmation and controlled database authority. |
| Arbitrary open-ended multi-scenario optimizer | High computational, UX, and explanation complexity. Start with transparent, bounded what-if comparisons after the base Ripple calculations are reliable. |
| Exact market pricing, local vendor recommendations, or regulatory/permit guarantees | Not supported without verified sources and can mislead users. All examples remain illustrative. |
| Full event-day operations platform or exhaustive templates for every tradition | Scope is too broad for the deadline. Keep tasks and event-day activities editable; expand from demonstrated user need later. |
| Final visual system or detailed screen specifications in Stage 02 | The user assigns design selection to Stage 04 and requires `/gpt-taste`/Visual Director then. This document sets direction only. |

## Handoff to Stage 03

Carry forward the positioning “a working plan that explains what each decision changes,” the “Why this changed” Ripple impact trail, the three editable illustrative scenarios, the eight product modules, and the P0 vertical flow. Stage 03 should resolve any remaining product rules and consolidate this ideation with Stage 01 into final context. Do not implement code or begin Stage 03 until the user assigns it.
