# Stage 08 — Production Deployment Guide

**Status:** source code is published at [GitHub](https://github.com/CodeWithShrey-collab/MomentOS-Event-Planner). Deployment configuration is prepared; no cloud resources or public application deployment have been created.
**Checked against provider documentation:** 2026-10-31. Pricing and plan limits can change; recheck the dashboards before provisioning.

## Recommended architecture

Use one Render Docker web service in Singapore. The image compiles the React/Vite client and runs it with Flask/Gunicorn; Flask serves the SPA and `/api/v1` from the same HTTPS origin. Use a private Render PostgreSQL database for durable event data and a private Render Key Value service for shared Flask-Limiter counters. The model stays `gpt-6-luna`; provider calls remain server-side.

Render has native Python, Docker services, managed PostgreSQL, Redis-compatible Key Value, environment-managed secrets, HTTPS, health checks, and declarative Blueprint configuration. Its official Flask quickstart uses Gunicorn. The single-origin layout avoids cross-origin cookie deployment complexity.

### Hosting options checked

| Provider | Flask + database fit | HTTPS / secrets | Free or low-cost reality | Operational effort |
|---|---|---|---|---|
| **Render (recommended)** | Native Python or Docker; managed PostgreSQL and Redis-compatible Key Value; one Flask service can serve built React assets | Managed TLS and dashboard secrets; health checks; Blueprint wiring | Current listed low tier: web 512 MB $7/mo + PostgreSQL 256 MB from $6/mo + Key Value 256 MB $10/mo (about **$23/mo**, before any extra storage, usage, taxes, or plan changes). Free web services sleep after 15 idle minutes and local files are ephemeral; free Postgres expires after 30 days, so free is for previews, not this persistent production app. | Lowest for this architecture; one Blueprint describes the services and private connections. |
| **Railway** | Flask/Gunicorn guide and PostgreSQL service template; can build a Docker image or deploy from a Git repository | Public generated domains and managed variables; verify HTTPS and service networking in the workspace before release | Official current pricing describes a trial credit, then a $1/month Free plan with resource limits; Hobby has a $5 minimum usage commitment and charges overages. Not a guaranteed free always-on production service. | Simple app workflows, but usage billing and service resource limits require monitoring. |
| **Fly.io** | Container deployment; managed PostgreSQL available | HTTPS certificates and secrets supported; more explicit machine/network configuration | Managed Postgres starts at $38/mo, plus application machines, storage, and egress. Small machine prices are metered; no permanent free production tier is assumed. | More operational work; higher managed database floor for this small app. |

Official references:

- [Render Flask deployment](https://render.com/docs/deploy-flask), [Render free instance limits](https://render.com/docs/free), [Render pricing](https://render.com/pricing), [Render PostgreSQL pricing overview](https://render.com/articles/managed-postgresql-pricing-2026), [Render Key Value pricing and behavior](https://render.com/docs/key-value).
- [Railway Flask guide](https://docs.railway.com/guides/flask), [Railway PostgreSQL](https://docs.railway.com/databases/postgresql), [Railway pricing](https://railway.com/pricing).
- [Fly.io pricing](https://fly.io/pricing/), [Fly.io Managed Postgres](https://fly.io/docs/postgres/).
- [Render Blueprint specification](https://render.com/docs/blueprint-spec), [pre-deploy migrations](https://render.com/docs/deploys), [environment secrets](https://render.com/docs/configure-environment-variables), [forwarded client IP guidance](https://render.com/articles/how-render-handles-ddos-attacks).

Render is recommended because it matches the prepared image, gives the app and PostgreSQL private same-region connections, provides shared rate-limit storage, and avoids operating a reverse proxy yourself. The calculated $23/month is a current listed baseline for the chosen low plans, not a quote or a free-tier claim. The Render dashboard may require a paid workspace/service setup; verify all totals and billing settings before accepting any provisioning flow.

## Prepared deployment files

- Root `Dockerfile`: Node 22 build stage, Python 3.12 runtime, compiled frontend served by Flask, one Gunicorn worker with four threads, bounded timeouts and request recycling.
- Root `.dockerignore`: excludes `.env`, local databases, dependencies, builds, and test artifacts from the Docker context.
- Root `render.yaml`: declares one web service, private PostgreSQL, and private rate-limit Key Value; uses generated server secret and prompts for the OpenAI key and exact public HTTPS origin. Automatic deployments are disabled in the Blueprint.
- `backend/wsgi.py`: production WSGI entrypoint (`wsgi:app` from the backend working directory).
- `backend/migrations/`: Alembic history; Render's paid pre-deploy command applies `flask db upgrade` before serving traffic.

This is configuration only. Importing the Blueprint creates paid resources and therefore requires explicit authorization.

## Production environment

Configure these through the host's secret/environment manager. Do not copy a local `.env` file to the host.

| Variable | Production value / purpose |
|---|---|
| `APP_ENV` | `production`; enables secure startup checks and production static path. |
| `APP_BASE_URL` | Exact canonical public HTTPS origin, e.g. `https://<assigned-host>`. No path, query, or fragment. |
| `TRUSTED_ORIGINS` | Exact comma-separated HTTPS origin allowlist; normally the same public origin only. |
| `SECRET_KEY` | Stable random secret, at least 32 characters; Render generates one in its secret store. |
| `SESSION_COOKIE_SECURE` | `true`; cookie is also HttpOnly and SameSite=Lax. |
| `DATABASE_URL` | Private PostgreSQL connection URL; the SQLAlchemy config normalizes `postgresql://` to the psycopg driver. |
| `RATE_LIMIT_STORAGE_URI` | Private `redis://` or `rediss://` Key Value URL shared by app processes. |
| `AI_MODE` | `live`; production startup rejects demo mode. |
| `OPENAI_API_KEY` | Rotated, active credential set only in the provider's secret manager. Never put it in a Blueprint, Docker image, frontend variable, or log. |
| `OPENAI_MODEL` | Exactly `gpt-6-luna`; application validation rejects substitutions. |
| `OPENAI_REASONING_EFFORT` | `low` by default; operation-specific medium effort remains bounded. |
| `OPENAI_MAX_OUTPUT_TOKENS` | `3000` configured in the Blueprint; app bounds the accepted range. |
| `AI_DAILY_REQUEST_LIMIT`, `AI_PER_MINUTE_LIMIT` | `20` and `5` in the prepared Blueprint; adjust only after reviewing expected spend. |
| `PROXY_FIX_X_FOR`, `PROXY_FIX_X_PROTO`, `PROXY_FIX_X_HOST` | `2`, `1`, `0` for the documented Render edge chain. These counts must be checked against the actual deployed forwarded headers before public launch. Other providers need their own exact values. |
| `MAX_CONTENT_LENGTH` | `262144` bytes. |

Production settings now fail closed if the app uses demo AI, lacks a key, selects SQLite or memory rate-limit storage, lacks HTTPS origins/secure cookies, or does not declare trusted forwarded-header counts. Flask debug is explicitly false. Redis support is included through the `Flask-Limiter[redis]` dependency.

## Request, cookie, and proxy behavior

The browser and API share the same origin. Flask checks the CSRF token and exact request origin on state-changing requests. Sessions are opaque, hashed server-side, HttpOnly, Secure, and SameSite=Lax. Event ownership, ETag preconditions, and idempotency continue to be enforced by the API.

Render documents traffic through Cloudflare and its load balancers and instructs applications to use `X-Forwarded-For` to identify the caller. The prepared `ProxyFix` uses bounded, explicit counts instead of trusting every forwarded value. Before launch, verify the actual chain from a deployed service, and attempt a request with forged leftmost forwarded values to confirm they cannot change the client address used by Flask-Limiter. If the chain differs, update counts to the provider's verified topology. Do not set unbounded trust.

HTTPS termination occurs at the provider. `SESSION_COOKIE_SECURE=true` is mandatory. CSRF origin checks use the browser's public `Origin` header and configured HTTPS allowlist.

## Build and database migration flow

The Render Blueprint uses a Docker build with pinned frontend and backend dependencies. The Vite production output is copied to `/app/frontend/dist`, and Flask serves it. The service binds Render's `PORT`; no Flask development server is used.

The pre-deploy migration runs:

```sh
python -m flask --app backend.wsgi:app db upgrade
```

This is a production pre-deploy command and is available only on paid Render web services. Take a database backup before changing an existing schema. Never use `db.create_all()` in production; application startup leaves schema changes to Alembic.

Local production-image preparation (Docker Engine must be running):

```sh
docker build -t momentos:local .
```

The local Docker Engine was not available during this preparation session, so no image build was claimed. PostgreSQL-dialect offline migration generation passed and emitted DDL for 17 tables and 14 indexes across both migration revisions. The Windows PostgreSQL service is running, but its data was not assumed disposable and was not accessed or modified; a real PostgreSQL migration and persistence test remains pending.

## Health checks and operations

- `GET /api/v1/health/live`: process liveness.
- `GET /api/v1/health/ready`: checks database reachability and migrated tables and reports whether live AI is configured; returns 503 when dependencies are unavailable.
- The prepared Render health check targets readiness, so incomplete migrations or missing dependencies block traffic.
- Keep one web instance and one Gunicorn worker at the selected small tier initially. Flask-Limiter uses the shared Key Value store, not per-worker memory.
- Monitor provider usage records, logs, database connections, Redis memory, response errors, and disk/storage use. Logs are sanitized; avoid logging request bodies or event prompts.
- Confirm managed database backup/restore policy and test a restore path before treating the service as production durable.
- Configure alerting for health failures and unexpected AI usage. Set provider spend limits independently where available.

## Deploy procedure (after authorization)

1. Use the published GitHub repository as the source. Obtain authorization before provisioning the selected paid services or deploying publicly.
2. Recheck the live Render prices, billing terms, storage assumptions, and workspace requirements.
3. Import this repository's `render.yaml`; review every resource and monthly estimate before confirming creation.
4. Set the canonical generated HTTPS domain in `APP_BASE_URL` and `TRUSTED_ORIGINS`; set the rotated `OPENAI_API_KEY` in the Render secret field.
5. Confirm `APP_ENV=production`, `AI_MODE=live`, exact model, secure cookie, private PostgreSQL/Redis URLs, and proxy counts before deployment.
6. Wait for migrations and readiness; inspect sanitized logs only.
7. Run the checklist in `docs/08_final_checklist.md`, beginning with HTTPS, SPA refresh, sessions, CSRF, and isolated event persistence.
8. Use one authorized live blueprint request and one authorized Copilot request at most for release verification; verify usage/token records without printing generated private content.
9. Test database persistence across app restart, session isolation, Ripple preview/cancel/commit, and mobile behavior.
10. Publish the deployment URL only after the full checklist passes. A deployment URL alone is not proof that the complete live journey works.

## Current readiness

Local app serving and prior frontend/backend suites are verified. The production startup configuration and deployment manifest are prepared and have targeted tests. No deployment, public URL, production PostgreSQL test, TLS/proxy verification, or full live-browser AI run has happened. Those are explicit release blockers, not completed results.
