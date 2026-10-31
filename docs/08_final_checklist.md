# Stage 08 — Final Release Checklist

**Prepared locally only.** Public deployment, Git initialization/publication, paid resource provisioning, video upload, LinkedIn posting, and competition submission remain unauthorized and have not been performed.

## Local preparation completed

- [x] Authorized root confirmed as `G:\Hackathons\MomentOs Event Planner`.
- [x] Root README with product, architecture, local setup, test commands, security notes, screenshots, and limitations.
- [x] Docker multi-stage build for a single-origin React/Flask app, Gunicorn runtime, SPA assets, and database migration command.
- [x] Render Blueprint with HTTPS-ready origin configuration, generated `SECRET_KEY`, live GPT-6 Luna mode, secret prompt for `OPENAI_API_KEY`, PostgreSQL, shared Redis-compatible rate limits, readiness check, and disabled auto-deploy.
- [x] Production startup rejects demo AI, missing provider credentials, SQLite, memory rate limits, non-HTTPS origins, insecure cookies, and missing proxy trust counts.
- [x] `.gitignore` and `.dockerignore` exclude private env files, databases, dependencies, build output, screenshots, caches, logs, and private key/certificate files.
- [x] README screenshots copied from verified Stage 07 browser captures; no screenshot is represented as a live-AI result.
- [x] `docs/08_publication_manifest.txt` lists intended public files exactly; private `context.md` and local `.env` are excluded.
- [x] Intended publication set is **2.10 MiB across 95 files**, well below 10 MB; Git object packing cannot be measured because no Git repository exists.
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
| Git history/repository size | Not available: this folder contains no `.git` metadata. No Git repository was initialized. |

## Repository publication (requires authorization)

- [ ] User authorizes Git initialization inside this project root and a public repository under the user's GitHub account.
- [ ] User chooses a repository license; none has been invented or added.
- [ ] Read the exact [publication manifest](08_publication_manifest.txt), then review the filesystem and `.gitignore` results again immediately before staging.
- [ ] Confirm `.env`, local SQLite/PostgreSQL dumps, all databases, dependencies, build output, test artifacts, caches, logs, private keys, and personal data are absent from staging.
- [ ] Initialize Git only in this project root. Do not stage via `git add .`.
- [ ] Inspect staged names and content, then check staged size and `.env.example` before commit/push.
- [ ] Confirm the public GitHub repository stays below 10 MB after the initial commit.

Safe commands **after explicit authorization** (run from the authorized root; replace remote placeholder only with the user's confirmed GitHub URL):

```powershell
git init -b main
git status --short --ignored
git check-ignore -v .env backend/instance/momentos.sqlite3 frontend/node_modules frontend/dist frontend/test-artifacts
git add --pathspec-from-file=docs/08_publication_manifest.txt
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
# Inspect every staged file and scan staged content for credentials before continuing.
git commit -m "Prepare MomentOS PromptWars submission"
git remote add origin <CONFIRMED_GITHUB_REMOTE_URL>
git push -u origin main
```

Do not execute these commands until authorization is given. Do not use `git add .`.

## Paid deployment (requires authorization)

- [ ] User approves Render and the current estimated minimum of about **$23 USD/month** for the prepared app, Postgres, and Key Value plans, subject to live prices and storage/egress charges.
- [ ] User approves creation of one always-on web service, one PostgreSQL database, and one Key Value service.
- [ ] Confirm live dashboard totals, billing/spend controls, region (Singapore), plan size, disk size, and retention before provisioning.
- [ ] Enter the currently rotated OpenAI API key only in Render's secret UI; never put it in the Blueprint, Git, issue, chat, or video.
- [ ] Confirm production values and trusted proxy counts before first launch.
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

1. No Git repository or public GitHub repository exists; explicit authorization is needed before initialization/publication.
2. No production resources or deployment exist; explicit authorization is needed before paid provisioning/public deployment.
3. Production PostgreSQL and image build were not tested in this environment; test them after authorization and before making the URL public.
4. Proxy header trust, secure cookies, CSRF, persistent data through restart, and production session isolation require deployment verification.
5. Full live-browser AI has not been verified; only Stage 06's live blueprint/save/reload and mocked-provider browser workflows are verified.
6. Demo video, LinkedIn post, and competition submission URLs do not yet exist; recording/upload/posting/submission require explicit authorization.
