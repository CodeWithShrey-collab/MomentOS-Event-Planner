# Stage 08 — Final Release Checklist

**Current status:** the source repository is public at [https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner](https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner). The app is not deployed. Paid resource provisioning, video upload, LinkedIn posting, and competition submission have not been performed.

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
- [x] Submission text, demo script, LinkedIn draft, and deployment guide prepared with explicit URL placeholders.

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

## Paid deployment (requires authorization)

- [ ] User approves Render and the current estimated minimum of about **$23 USD/month** for the prepared app, Postgres, and Key Value plans, subject to live prices and storage/egress charges.
- [ ] User approves creation of one always-on web service, one PostgreSQL database, and one Key Value service.
- [ ] Confirm live dashboard totals, billing/spend controls, region (Singapore), plan size, disk size, and retention before provisioning.
- [ ] Enter the currently rotated OpenAI API key only in Render's secret UI; never put it in the Blueprint, Git, issue, chat, or video.
- [ ] Confirm production values and the public Render Cloudflare ingress before first launch; keep all `PROXY_FIX_X_*` values at `0`.
- [ ] Run the deployment checklist in `docs/08_deployment_guide.md`, including the full public HTTPS browser journey and restart persistence.
- [ ] Add the deployment URL only after all production checks pass.

## Video, LinkedIn, and competition form (each requires authorization)

- [ ] Record the real deployed app according to `docs/08_demo_script.md`; use live provider mode only after its cost budget is approved.
- [ ] Review recording for personal data, secrets, and mocked-success indicators.
- [ ] Obtain authorization before public or link-accessible video upload; verify the URL signed out.
- [ ] Obtain authorization before posting the LinkedIn draft; verify linked URLs.
- [ ] Submit the competition form only after repository, deployment, and video URLs are public and verified; double-check each text field remains within 1,024 characters.
- [ ] Do not claim a competition result, award, or score that has not been announced and independently verified.

## Release blockers at handoff

1. No production resources or deployment exist; authorization is needed before paid provisioning/public deployment.
2. Production PostgreSQL and image build were not tested in this environment; verify them before release.
3. Proxy header trust, secure cookies, CSRF, persistent data through restart, and production session isolation require deployment verification.
4. Full live-browser AI has not been verified; only Stage 06's live blueprint/save/reload and mocked-provider browser workflows are verified.
5. Demo video, LinkedIn post, and competition submission URLs do not yet exist; recording/upload/posting/submission require explicit authorization.
