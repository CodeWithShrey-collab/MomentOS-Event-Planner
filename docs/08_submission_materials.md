# PromptWars Challenge 5 — Submission Materials

No public repository, deployed app, public demo video, LinkedIn post, or competition form submission currently exists. Replace placeholders only with URLs that have been published and verified. Do not submit until the final checklist is complete.

## Submission fields

### 1. Challenge selection

**Challenge 5 — Celebration & Event Planner**

### 2. Public GitHub repository URL

**Pending authorization and publication:** `[PUBLIC_GITHUB_REPOSITORY_URL]`

### 3. Project deployment URL

**Pending authorization and verified production deployment:** `[PUBLIC_HTTPS_DEPLOYMENT_URL]`

### 4. Project demo video URL

**Pending recording, authorized upload, and signed-out accessibility check:** `[PUBLIC_DEMO_VIDEO_URL]`

### 5. Description of changes/updates in the deployed version

**Draft — confirm against the actual deployed release before submission (within the 1,024-character field limit):**

> MomentOS is an AI-powered planning workspace for weddings, birthdays, and community events. The deployed release connects a React and TypeScript interface to a Flask API with persistent PostgreSQL storage, secure guest sessions, CSRF protection, and version-checked updates. GPT-6 Luna helps interpret event briefs and generate structured planning ideas. The deterministic Python Ripple Engine previews budget, guest-count, capacity, and task impacts before a user confirms a change. The workspace includes a command center, budget studio, timeline, vendor checklist, contextual Copilot, and scenario comparison. Prices and vendor details are editable illustrative assumptions, not live quotations.

**Character count:** 721 including spaces and punctuation (excluding the Markdown quote marker). Recount after any edits.

### 6. GenAI services utilized and where they were used

**Submission text (within the 1,024-character field limit):**

> MomentOS uses OpenAI GPT-6 Luna (`gpt-6-luna`) through the official OpenAI Python SDK and Responses API, called only by the Flask backend. Structured Outputs are validated with Pydantic for event-requirement extraction and blueprint generation; the model also provides personalized ideas, task and vendor-checklist suggestions, Ripple explanations, and event-aware Copilot answers based on minimal authorized context. GPT-6 Luna explains trade-offs but does not write to the database or determine financial results. Deterministic Python code performs budget arithmetic, per-guest recalculation, venue-capacity and schedule checks, dependency validation, and Ripple simulations. Proposed changes require explicit user confirmation. The application also offers a clearly labeled deterministic demo mode that makes no provider request.

**Character count:** 824 including spaces and punctuation (excluding the Markdown quote marker). Recount after any edits.

### 7. LinkedIn post URL

**Pending authorized publication:** `[PUBLIC_LINKEDIN_POST_URL]`

## LinkedIn announcement draft

> I’ve been building MomentOS — “The AI Operating System for Every Celebration” — for Hack2Skill PromptWars Challenge 5: Celebration & Event Planner.
>
> The idea is simple: event plans are connected systems. A change in guest count can affect catering, seating, capacity, tasks, and the total budget. MomentOS brings those consequences into an editable planning workspace.
>
> The product combines a React and TypeScript frontend with a Python Flask backend, persistent event planning data, and GPT-6 Luna through the OpenAI Responses API. Its signature Ripple Engine uses deterministic Python calculations to preview the effects of a change before the user confirms it. The workspace also includes an Event Architect, Budget Studio, timeline, vendor checklist, contextual Copilot, and scenario comparison.
>
> AI helps interpret the brief and explain options; the backend remains authoritative for calculations and saved changes. Vendor details and prices are illustrative unless entered and verified by the user.
>
> Project: [PUBLIC_GITHUB_REPOSITORY_URL]
> Try MomentOS: [PUBLIC_HTTPS_DEPLOYMENT_URL]
> Demo: [PUBLIC_DEMO_VIDEO_URL]
>
> Building this has been a useful exercise in bringing structured AI, deterministic business rules, privacy boundaries, and accessible product design together.
>
> #PromptWars #Hack2Skill #EventPlanning #GPT6Luna #React #Flask #AI

## Pre-submission accuracy check

- Replace every placeholder with a public URL and verify it signed out.
- Make the deployed-changes paragraph describe the actual deployed commit and production services; delete any capability not working in the deployed build.
- State only GPT-6 Luna if that is the model actually configured; never claim another model.
- Do not describe mocked provider tests as live AI validation.
- Do not claim awards, rankings, judge feedback, user numbers, vendor integrations, availability, or live market prices without independent evidence.
- Check both descriptive answers are under 1,024 characters in the actual form.
- Do not publish the LinkedIn draft or submit the competition form without explicit authorization.
