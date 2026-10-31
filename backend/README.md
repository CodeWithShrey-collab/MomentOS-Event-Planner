# MomentOS Flask API

This directory contains the Flask API, SQLAlchemy models, Alembic migrations, deterministic planning services, and tests. In production, Flask serves the compiled React application and API from one origin. During local development, Vite runs separately and proxies `/api` to Flask.

## Local setup

Use Python 3.11 or newer. From the repository root in PowerShell:

```powershell
$env:FLASK_SKIP_DOTENV = '1'
$env:FLASK_APP = 'backend.wsgi:app'
$env:APP_ENV = 'development'
$env:AI_MODE = 'demo'
python -m pip install -r backend/requirements.txt
python -m flask db upgrade
python -m flask run
```

The local database defaults to `backend/instance/momentos.sqlite3`. The first run creates the directory through the application factory; migrations create the schema. Demo mode is deterministic, clearly marked in responses, and never calls OpenAI.

The backend's Pydantic settings load only the project-root `.env` as a local fallback; process environment variables take precedence. `FLASK_SKIP_DOTENV=1` disables Flask CLI's separate dotenv loader but does not disable the backend's explicit settings source. `.env` is excluded by the root `.gitignore`; `.env.example` contains an empty key placeholder. For deployed environments, prefer the platform's secret manager.

Run the automated backend suite from the repository root:

```powershell
python -B -m pytest -p no:cacheprovider backend/tests -q
```

## Live GPT-6 Luna configuration

Set these through the environment or a secret manager, then restart the API:

- `AI_MODE=live`
- `OPENAI_API_KEY` (secret; never place in frontend code or logs)
- `OPENAI_MODEL=gpt-6-luna` (the application rejects other model IDs)
- `OPENAI_REASONING_EFFORT=low` or `medium`
- `OPENAI_MAX_OUTPUT_TOKENS` (bounded from 700 to 8,000; includes reasoning tokens)
- `AI_DAILY_REQUEST_LIMIT` and `AI_PER_MINUTE_LIMIT`

Provider failures return typed safe errors; there is no fallback model. Live usage records contain operation, model, effort, provider request ID, token counts where available, elapsed time, outcome, and a versioned estimate. Prompt and response text are not stored by default. `store=False` is sent to the Responses API. The local automated tests use mocked provider responses only. A one-time live smoke test was run after the user rotated the credential: GPT-6 Luna returned a completed response (27 total tokens). No key or response content was printed.

After rotating/provisioning a valid key, run a single manually invoked connectivity check:

```powershell
$env:FLASK_SKIP_DOTENV = '1'
$env:FLASK_APP = 'backend.wsgi:app'
python -m flask openai-smoke
```

The command uses only `gpt-6-luna`, low reasoning, a 128-token output cap, a 15-second maximum timeout, and zero retries. It prints token counts when supplied and a sanitized status, never response text, request body, key, or provider error details. If the API reports an incomplete response due to `max_output_tokens`, it distinguishes that from a connection/model-access failure. The call can incur a small API charge. It is a CLI command, not an unauthenticated HTTP endpoint, and it is never called automatically at startup.

## Production configuration

Production configuration is validated at startup and requires:

- `APP_ENV=production`, `APP_BASE_URL=https://<public-host>`, and `TRUSTED_ORIGINS` containing only the exact allowed HTTPS origins.
- A generated, stable `SECRET_KEY` with at least 32 characters and `SESSION_COOKIE_SECURE=true`.
- `AI_MODE=live`, an `OPENAI_API_KEY` stored in the platform secret manager, and the locked `OPENAI_MODEL=gpt-6-luna`.
- A persistent PostgreSQL `DATABASE_URL` using the `psycopg` driver and shared Redis-compatible `RATE_LIMIT_STORAGE_URI`.
- `PROXY_FIX_X_FOR` and `PROXY_FIX_X_PROTO` set to the exact trusted proxy counts documented by the selected host. Never use a forwarded-header count copied from another provider without verifying the chain.

Apply migrations before the new app process receives traffic: `python -m flask --app backend.wsgi:app db upgrade`. The checked-in Render Blueprint runs that command as a paid pre-deploy step. `GET /api/v1/health/live` checks process liveness; `/api/v1/health/ready` verifies database schema readiness and reports whether live AI credentials are configured.

`Dockerfile` builds Vite assets and the Flask runtime into one image. The Render deployment definition is in the repository-root `render.yaml`; it describes a single-origin Flask app, persistent PostgreSQL, and Redis-compatible shared rate-limit storage. It does not provision services unless an authorized user imports the Blueprint. Read `docs/08_deployment_guide.md` before provisioning; the current low-tier estimate is paid and must be checked against the live provider dashboard.

No public service has been provisioned. Production PostgreSQL, TLS/proxy behavior, and live browser behavior remain to be verified after a separately authorized deployment.

## API and mutation rules

The versioned API is mounted at `/api/v1`. See `docs/03_api_contracts.md` for the frozen wire contract. Event writes enforce session ownership, CSRF and trusted-origin checks, `If-Match` version preconditions, and idempotency keys. Event planning data is stored as immutable normalized plan versions; task completion is a user action. Ripple previews are persisted as immutable, expiring simulations but do not update the event until an explicit, revalidated commit.
