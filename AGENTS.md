# MomentOS — Repository Instructions

These instructions apply to this project and all files beneath the currently opened project root: `G:\Hackathons\MomentOs Event Planner`. This is the only authorized project workspace for all stages. Resolve and confirm the workspace root before making changes. Keep source, tests, generated assets, project configuration, and documentation inside it. Do not use another project directory as a workspace. Do not move, delete, or modify unrelated project directories. External package caches and normal tool installation locations are allowed only when needed for development.

The user’s MomentOS Master System is authoritative. Preserve the product and technical decisions below. Do not infer authorization for a later stage from prior prompts or context; execute only the stage the user assigns.

## Project identity and competition

- Name: **MomentOS**
- Tagline: **The AI Operating System for Every Celebration**
- Competition: Hack2Skill PromptWars Virtual, Challenge 5 — Celebration & Event Planner
- Submission deadline: November 1, 2026, 11:59 PM IST
- Recommended Codex model: GPT-6 Luna; recommended reasoning effort: EXTRA HIGH.
- Official challenge: create a GenAI planning assistant for weddings, birthdays, and community events, including budgets, timelines, vendor checklists, and personalized ideas.
- Expected submission materials: a public GitHub repository under 10 MB, functioning deployed app URL, accessible demo video URL, deployed-changes description, explanation of GenAI services used, and LinkedIn post URL.
- Never invent submission results, deployment status, or an evaluation score.

## Product vision

MomentOS is an intelligent, interactive event-planning workspace that turns an idea into an actionable, editable plan, not a generic event chatbot. Support weddings, birthdays, and community events end to end. Product areas:

1. AI Event Architect
2. Event Command Center
3. Smart Budget Studio
4. Ripple Engine
5. Timeline & Task Planner
6. Vendor Workspace
7. AI Event Copilot
8. Scenario Comparison

### Ripple Engine — signature differentiator

Simulate consequences when event inputs change. For example, changing a wedding from 150 to 200 guests should calculate and visualize additional catering cost, seating needs, venue-capacity warnings, invitation implications, affected budget categories, task/vendor adjustments, budget overrun or savings, and possible cost optimizations.

Use deterministic Python calculations for authoritative financial and dependency results. GPT-6 Luna may explain results and recommend options. The user must explicitly confirm proposed changes before they are saved.

## Frozen technical architecture

- Frontend: React, TypeScript, Vite, Tailwind CSS, accessible component primitives, Recharts, and Motion where useful.
- Backend: Python, Flask, SQLAlchemy, Alembic, Pydantic validation, and the official OpenAI Python SDK.
- Database: SQLite in local development; PostgreSQL in production.
- Testing tools: Pytest, Vitest, Playwright, and automated accessibility checks.
- Prefer same-origin Flask serving of the built frontend and API, or an equivalently secure deployment architecture.
- Live AI model: exact API model ID `gpt-6-luna`, configured by `OPENAI_MODEL=gpt-6-luna`.
- Use the official OpenAI Python SDK and Responses API. Use Structured Outputs for typed application data. Use function calling only when it has meaningful benefit.
- Never silently replace GPT-6 Luna with GPT-5 Nano, GPT-5 Mini, GPT-6 Sol, GPT-6 Astra, or another model. If GPT-6 Luna is unavailable to the configured API project, report the issue.
- Use low reasoning effort for extraction, simple recommendations, and summaries; medium for event planning, customization, and multi-constraint explanations; high only for exceptional tasks and within configured application limits.
- The model never receives uncontrolled authority to modify the database.

Do not change frozen decisions without user authorization.

## AI responsibilities and business rules

GPT-6 Luna may interpret natural-language event descriptions, extract requirements, generate personalized concepts and themes, suggest timelines and tasks, explain budget implications, answer event-specific questions, and recommend planning improvements.

The model must not be the authority for currency arithmetic; fabricate vendor availability or quotations; execute uncontrolled SQL; change persisted event data without authorized confirmation; invent task completion, bookings, or user data; override hard budget/timeline constraints; or invent facts about the user. Validate numerical and operational AI suggestions against deterministic business rules.

## Engineering, security, and quality

Build actual functionality rather than static mockups. Implement persistent event data, typed APIs, strong input validation, secure session isolation, accessible UI, responsive layouts, proper loading and recovery states, and deterministic offline demonstration data. Clearly label offline demo mode; never impersonate a successful OpenAI response.

- All live GenAI requests go through the backend. Never expose `OPENAI_API_KEY` in frontend code.
- Keep `.env` and secrets out of version control. Never write secret values into this file, logs, source, generated artifacts, or documentation. Document only secret names and purposes. Do not read or echo secret values unless explicitly required for a task.
- Bound context/output sizes, avoid unnecessary AI calls, set rate limits and timeouts, and use bounded retries.
- Record model usage and estimated cost without logging sensitive credentials.
- Use privacy-conscious API settings where supported.
- Treat user/vendor content as untrusted and mitigate prompt injection.
- Protect session ownership and cookie-authenticated state-changing routes from CSRF.
- Handle malformed, incomplete, and refused AI responses.
- Never let the model bypass deterministic budget/timeline constraints.

Visual quality should match a premium consumer product: refined typography, deliberate color and spacing, sophisticated useful layouts/charts, purposeful motion, polished responsive/empty/loading states. Avoid generic AI SaaS layouts, inconsistent cards, excessive gradients, fake interactions, clutter, and decoration without user value.

During Stage 04, use `/gpt-taste` and its Visual Director method: choose one primary style and at most two supporting styles.

## Strict nine-stage prompt-engine workflow

Follow this exact order. Do not skip, merge, rename, or reorder stages without authorization.

- `00 — Master System`
- `01 — Problem Analyst`
- `02 — Ideation`
- `03 — Final Context`
- `04 — Frontend (/gpt-taste)`
- `05 — Backend`
- `06 — Integration`
- `07 — DOM Verification`
- `08 — Demo Script`

Execute only the stage currently assigned. Each stage must read previous handoff documents, respect frozen decisions, complete that stage’s deliverables, run applicable verification, report files changed, checks actually run, findings, and blockers, then stop for the next prompt. Never report unexecuted checks as passing.

Stages 00–07 are complete. Stage 01 Problem Analyst is documented at `docs/01_problem_analysis.md`; Stage 02 Ideation at `docs/02_ideation.md`; Stage 03 Final Context in `docs/03_final_context.md` and its five supporting contracts; Stage 04 frontend in `docs/04_frontend_handoff.md`; Stage 05 backend in `docs/05_backend_handoff.md`; Stage 06 integration in `docs/06_integration_verification.md`; and Stage 07 DOM verification/production-readiness audit in `docs/07_dom_verification.md`. Stage 08 demo, deployment, and competition-submission preparation is documented in `README.md`, `Dockerfile`, `render.yaml`, `render-free.yaml`, and `docs/08_*`. The source repository is already published at `https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner`; preserve its history and do not push further changes without explicit authorization. Free deployment preparation is local only and no cloud resources or application deployment exist. Provisioning or deploying services, video upload, LinkedIn posting, and competition submission still require the user's explicit authorization. Do not perform those external actions until authorized.

## Autonomy and external actions

Install useful tools and dependencies when reasonably needed, while following the workspace and storage constraints. Preserve unrelated work. Do not initiate paid third-party services, publish the repository, or submit to the competition without explicit authorization. Keep visual assets optimized for the repository size limit.
