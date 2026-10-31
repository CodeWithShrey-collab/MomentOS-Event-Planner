# Stage 08 — Final Release Checklist

**Current status (2026-11-01):** the source repository is public at [https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner](https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner), and the application is deployed at [https://momentos-event-planner-free.onrender.com](https://momentos-event-planner-free.onrender.com). The public readiness endpoint returned HTTP 200 with PostgreSQL and Redis ready and AI configured. The exact Render source SHA is not confirmed. The local vendor-quotation and planning-guidance corrections described in this release are not pushed or deployed. This checklist is not a record of previous competition form entries; the project owner reports that Attempts 1 and 2 have been evaluated.

## Local preparation completed

- [x] Authorized root confirmed as `G:\Hackathons\MomentOs Event Planner`.
- [x] Root README with product, architecture, local setup, test commands, security notes, screenshots, and limitations.
- [x] Docker multi-stage build for a single-origin React/Flask app, Gunicorn runtime, SPA assets, and database migration command.
- [x] Render Blueprint with HTTPS-ready origin configuration, generated `SECRET_KEY`, live GPT-6 Luna mode, secret prompt for `OPENAI_API_KEY`, PostgreSQL, shared Redis-compatible rate limits, readiness check, and disabled auto-deploy.
- [x] Production startup rejects demo AI, missing provider credentials, SQLite, memory rate limits, non-HTTPS origins, insecure cookies, wrong Render rate-limit identity source, and nonzero forwarded-header trust.
- [x] `.gitignore` and `.dockerignore` exclude private env files, databases, dependencies, build output, screenshots, caches, logs, and private key/certificate files.
- [x] README screenshots copied from verified Stage 07 browser captures; no screenshot is represented as a live-AI result.
- [x] `docs/08_publication_manifest.txt` lists intended public files exactly; private `context.md` and local `.env` are excluded.
- [x] Published source set is **2.10 MiB across 95 files**, well below 10 MB; the local Git object store measured **1.45 MiB** at publication.
- [x] Submission text, demo script, LinkedIn draft, and deployment guide prepared; the public app URL is recorded where verified, while unpublished video and LinkedIn URLs remain placeholders.

## Local verification and environment facts

| Area | Result |
|---|---|
| Production configuration regression tests | Included in the complete backend suite: 68 passed. |
| Full backend test suite | `python -B -m pytest -p no:cacheprovider backend/tests -q`: 68 passed in 4.87 s. |
| TypeScript, ESLint, Vitest, production frontend build | Typecheck passed; ESLint passed; Vitest 3 files / 8 tests passed; Vite production build passed. |
| Offline demo Playwright | 1 passed in 21.6 s after setting the explicit Python/browser paths. The first attempt without `MOMENTOS_PYTHON` failed because the Windows Python app-execution alias was unavailable. |
| Flask-backed mocked-provider Playwright | 3 passed in 1.3 min: real React→Flask HTTP/session/CSRF/database workflow, 4 viewport sweep, axe scans, contrast capture. No OpenAI call. |
| YAML, manifest, secret and ignore checks | Render YAML parsed and structural assertions passed; 95 manifest entries exist with no missing/forbidden paths; estimate 2.10 MiB; zero credential-pattern matches in candidate text or production bundle; `.env` ignored and `.env.example` safe. Render CLI schema validation was not run. |
| PostgreSQL migration compatibility | Offline Alembic SQL generation passed for PostgreSQL dialect (17 `CREATE TABLE`, 14 `CREATE INDEX`, both revisions present). This did not connect to a PostgreSQL server. |
| Docker image build | Not run: Docker CLI exists but the Docker Desktop Linux engine was unavailable. |
| PostgreSQL test | Not run: a local PostgreSQL Windows service was detected, but its data was not confirmed disposable and was not accessed or changed. No Docker daemon was available for an isolated Postgres container. |
| Git history/repository size | Published on `main` at [the public repository](https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner); 95 files, 2.10 MiB source set, 1.45 MiB local Git object store. Initial publication commit `9963f2b`; current published head at first push `2d3f6c2`. |

## Repository publication (complete)

- [x] Authorized repository created and verified as public and empty before publication.
- [x] Git initialized only in this project root; `main` pushed to the authorized repository.
- [x] `.env`, `context.md`, databases, dependencies, build output, test artifacts, caches, and private keys excluded; committed history scanned for credential patterns.
- [x] Published repository and local Git object store verified below 10 MB.
- [ ] Select and add a license if desired; none has been added.

## Existing free deployment and remaining checks

- [x] One Render Free Docker web service is publicly reachable at `https://momentos-event-planner-free.onrender.com`; no duplicate service was created for this release.
- [x] Readiness on 2026-11-01 reported PostgreSQL ready, Redis ready, and AI configured. This check verifies dependency reachability/schema and configuration, not every application workflow.
- [ ] Verify the exact Render deployed Git SHA through the service dashboard or authorized Render API.
- [ ] After the current local fixes are approved and released, verify the deployed build and the vendor quote/timing/follow-up flows.
- [ ] Verify persisted event changes across a controlled service restart, deployed cookie/CSRF behavior, and production proxy identity before claiming those checks.
- [ ] Keep production secrets in Render's secret environment only; never place them in the Blueprint, Git, issue, chat, or video.

## Video, LinkedIn, and competition form (each requires authorization)

- [ ] Record the real deployed app according to `docs/08_demo_script.md`; use live provider mode only after its cost budget is approved.
- [ ] Review recording for personal data, secrets, and mocked-success indicators.
- [ ] Obtain authorization before public or link-accessible video upload; verify the URL signed out.
- [ ] Obtain authorization before posting the LinkedIn draft; verify linked URLs.
- [ ] Use the remaining competition attempt only after repository, deployed release, and video URLs are public and verified; double-check each text field remains within 1,024 characters. No new attempt is submitted by this work.
- [ ] Do not claim a competition result, award, or score that has not been announced and independently verified.

## Release blockers at handoff

1. The precise Render source SHA is unavailable; the deployed frontend bundle was previously matched to the local pre-correction build, while the current code corrections remain local.
2. Readiness confirms PostgreSQL and Redis reachability, but persistent writes across restart, migration history, TLS/cookie behavior, and production session isolation still need controlled verification.
3. A complete live-browser GPT-6 Luna journey remains unverified; browser tests use mocked provider responses.
4. The demo-video and LinkedIn URLs remain placeholders in this project. Publishing either, or using the final competition attempt, requires the project owner's explicit action.
