# MomentOS — Free-Tier Deployment Guide

**Status (2026-10-31):** the user-created Neon and Upstash databases and one Render Free web service already exist. The latest deployment is unhealthy; the Docker image builds, but startup fails at the PostgreSQL connectivity preflight. Redis, migrations, and Flask readiness have not yet been verified in Render. No additional resources were created. The existing paid-service design in [`render.yaml`](../render.yaml) remains separate. This guide uses the free-only [`render-free.yaml`](../render-free.yaml).

The target is one Render Free Docker web service, Neon Free PostgreSQL, and Upstash Free Redis. This is a zero-fixed-cost preview configuration inside provider allowances, not a production SLA or a guarantee of zero usage charges. OpenAI remains usage-billed. Free-tier limits and terms can change; verify them in each dashboard before creating resources.

## Free-tier limits to plan around

Checked 2026-10-31 against provider pages:

| Service | Current free allowance relevant to MomentOS | Behavior to expect |
|---|---|---|
| Render Web Service | `free` plan, 0.1 CPU and 512 MB RAM; 750 free instance hours per workspace/month | Sleeps after 15 minutes without inbound traffic; waking takes about a minute. Filesystem is ephemeral, so never store event data locally. Free services can restart, have no persistent disk, and Render advises against using them for production applications. Render may suspend a free service for uncommonly high outbound traffic, including external database/API calls. Bandwidth and build-pipeline quotas apply; overages may bill if a payment method is attached, or suspend services/builds when it is not. |
| Neon PostgreSQL | $0 Free plan; currently 100 CU-hours and 1 GB database storage per project | Compute can autosuspend to zero and wake on a connection. Monitor compute and storage. The app connects directly for migration compatibility and limits its own connection pool. |
| Upstash Redis | $0 Free Redis; currently 256 MB data, 10 GB monthly bandwidth, and 500,000 monthly commands | Use the TCP connection URL, not the REST URL. Limits can cause rate limiting or failed requests; readiness reports Redis unavailable and the app does not switch to in-memory limits. |
| OpenAI | Usage-based billing; current standard short-context GPT-6 Luna rates are input $0.10, cached input $0.01, output $0.50 per million tokens | Provider usage is not included in the hosting free tiers. Keep the app quota at 20 AI requests/session/day and 5/minute, and monitor provider usage. |

Sources: [Render Free services and limits](https://render.com/docs/free), [Render compute plans](https://render.com/docs/compute-plans), [Render regions](https://render.com/docs/regions), [Neon pricing](https://neon.com/pricing), [Neon scale-to-zero](https://neon.com/docs/introduction/scale-to-zero), [Upstash Redis pricing](https://upstash.com/pricing/redis), [OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

## Choose the correct Render configuration

The repository root [`render.yaml`](../render.yaml) is the existing **paid** blueprint. It declares paid Render Postgres and Key Value resources. Do not import it for this setup.

Render defaults to `render.yaml`, but supports selecting an alternative Blueprint path:

1. Push the approved code and `render-free.yaml` to the public GitHub repository.
2. In the Render Dashboard, choose **New → Blueprint**, connect the MomentOS repository and `main` branch.
3. In **Blueprint Path**, enter exactly `render-free.yaml`.
4. Review the preview carefully. It must list exactly one web service with plan `free`, and no Render database or Key Value service.
5. Do not click **Deploy Blueprint** until the environment and proxy items below are ready and deployment is explicitly authorized.

If the Blueprint Path is omitted, Render uses `render.yaml`; importing the wrong file can provision paid services.

The existing [`Dockerfile`](../Dockerfile) builds React assets and runs Flask/Gunicorn in one origin. The free blueprint overrides only the Docker command, using [`backend/start-free-render.sh`](../backend/start-free-render.sh) to validate dependencies, migrate, then start Gunicorn.

## Create Neon PostgreSQL

1. Sign in to the [Neon Console](https://console.neon.tech/) and choose **Create project**.
2. Select the Free plan, PostgreSQL, and a region close to Render Singapore. Keep the project and branch defaults unless you have an approved database plan.
3. Keep autosuspend enabled to conserve compute. Do not configure a paid plan or add a card as part of this preparation.
4. Open **Connect**, select the branch, database, and role, then turn **Connection pooling off** and copy the direct connection string. Neon recommends direct connections for schema migrations because transaction poolers can be unsuitable for migration tools.
5. Keep the copied string private. Do not put it in Git, chat, screenshots, or `.env.example`.

The app accepts standard Neon `postgresql://`/`postgres://` URLs and `postgresql+psycopg://` URLs. It preserves encoded username/password and existing query options (such as `channel_binding=require`), selects the psycopg 3 driver, enforces `sslmode=verify-full`, and points libpq at the Debian CA bundle `/etc/ssl/certs/ca-certificates.crt`. This is necessary because libpq otherwise looks for `~/.postgresql/root.crt`; installing OS CA certificates alone does not select them for PostgreSQL verification. The Docker build now fails if the expected bundle is absent. The connection timeout is bounded at ten seconds unless supplied by the URL. Production never accepts SQLite. The current Render log only identified a PostgreSQL `OperationalError`; TLS trust is a confirmed configuration gap and likely cause, but must be confirmed by the new sanitized diagnostics after an authorized deployment.

Neon’s Free pricing currently lists 100 CU-hours and 1 GB per project. A sleeping Render service and Neon autosuspend may both add wake-up delay. The SQLAlchemy pool is bounded to two connections per worker, has no overflow, checks stale sockets before reuse, recycles connections, and uses a short pool timeout.

## Create Upstash Redis

1. Sign in to the [Upstash Console](https://console.upstash.com/) and choose **Create Database → Redis**.
2. Select the Free plan and a region close to Render.
3. On the database page, open **Connect → TCP** and copy the Redis connection URL. It should have the form `rediss://default:<token>@<endpoint>:6379`.
4. Use that URL for `RATE_LIMIT_STORAGE_URI`. Do not copy the Upstash REST URL or use `https://`.
5. Store it only in the Render environment-variable UI. Never commit or share it.

`rediss://` enables TLS; the app explicitly requires certificate and hostname verification. Production configuration rejects `redis://` and `memory://`. Startup pings Redis before migrations; `/api/v1/health/ready` also checks it. An unavailable store prevents startup/readiness rather than disabling limits.

## Configure Render Free Web Service

### Blueprint option

Use the exact `render-free.yaml` Blueprint Path described above. It declares one `runtime: docker`, `plan: free` web service in Singapore. `DATABASE_URL`, `RATE_LIMIT_STORAGE_URI`, `OPENAI_API_KEY`, and exact public origin values are dashboard-supplied; the secret key is generated by Render. The file has no paid resource declarations.

### Manual option

1. In Render, choose **New → Web Service** and connect the published MomentOS repository.
2. Select **Docker** runtime, root directory `.`, Dockerfile `./Dockerfile`, region Singapore, and instance type **Free**.
3. Set Docker Command to `sh /app/backend/start-free-render.sh`.
4. Set health check path to `/api/v1/health/ready`.
5. Set **Auto-Deploy Off** while reviewing the service.
6. Add the environment variables below in the Render Dashboard. Use **Generate** for `SECRET_KEY` (or a private random value of at least 32 characters). Never add secrets to YAML.
7. Set `APP_BASE_URL` and `TRUSTED_ORIGINS` to the exact service HTTPS origin, with no path or trailing slash. Use the default URL shown by Render; confirm both values exactly match the URL displayed for the service. If Render does not expose the assigned URL until after the first Blueprint sync, the application intentionally fails closed until you set the exact origin and manually redeploy.

### Required environment values

| Variable | Required value |
|---|---|
| `APP_ENV` | `production` |
| `APP_BASE_URL` | Exact service origin, e.g. `https://<service>.onrender.com` |
| `TRUSTED_ORIGINS` | Same exact HTTPS origin; add only additional exact HTTPS origins if actually used |
| `SECRET_KEY` | Generated by Render or a private random string of at least 32 characters |
| `DATABASE_URL` | Private direct Neon PostgreSQL connection string copied from Neon Console |
| `RATE_LIMIT_STORAGE_URI` | Private Upstash TCP `rediss://` URL |
| `AI_MODE` | `live` |
| `OPENAI_API_KEY` | Private OpenAI API key in Render’s secret field |
| `OPENAI_MODEL` | `gpt-6-luna` (fixed; no model fallback) |
| `OPENAI_REASONING_EFFORT` | `low` default; complex calls use only their existing operation-specific medium setting |
| `SESSION_COOKIE_SECURE` | `true` |
| `SESSION_COOKIE_SAMESITE` | `Lax` |
| `RATE_LIMIT_CLIENT_IP_SOURCE` | `render_cf_connecting_ip`; only for a public Render web service using its documented Cloudflare ingress |
| `PROXY_FIX_X_FOR` | `0` |
| `PROXY_FIX_X_PROTO` | `0` |
| `PROXY_FIX_X_HOST` | `0` |

### Proxy and client-IP trust

Do not set nonzero `ProxyFix` counts on Render. Werkzeug requires the exact number of trusted proxies separately for each forwarded header and warns those values can be forged. Render confirms that HTTPS terminates at its load balancer and the service receives HTTP, but does not publish fixed `X-Forwarded-For` / `X-Forwarded-Proto` hop counts. For client rate-limit identity, Render's public service guidance documents that Cloudflare writes and overwrites `CF-Connecting-IP` with the caller address. MomentOS validates that header as one IPv4/IPv6 address and uses it only for Flask-Limiter; missing or malformed values fall back to the socket peer, preserving a shared limit instead of trusting XFF. The app does not use forwarded scheme/host values for origin security: exact `APP_BASE_URL`/`TRUSTED_ORIGINS` validation and Secure, HttpOnly, SameSite=Lax cookies remain authoritative.

This is supported for Render's **public** web-service ingress, where Cloudflare is in the request path. It is not applicable to a private service, direct Gunicorn exposure, or a different proxy/CDN topology. If the hosting path changes, change the rate-limit identity source only after that provider documents an equivalent overwritten client-IP header. A deployment-time diagnostic is not required to choose hop counts because all counts are zero; if you later confirm ingress behavior operationally, record only whether a single valid `CF-Connecting-IP` was present and never log the value, other headers, or request data.

The repository has not been deployed to Render, so MomentOS has not observed the header on a live request. The supported values below are based on Render's documented public ingress behavior; the deployment check still needs to confirm the service is a public Render web service and that the shared Upstash store is healthy.

### Local verification status (2026-10-31)

- Backend: `backend/tests` — 80 passed; focused proxy/session/CSRF/rate-limit/production-settings selection — 16 passed, 27 deselected.
- Frontend: typecheck passed; ESLint passed; Vitest 3 files / 8 tests passed; production build passed.
- Browser: the existing Flask-backed Playwright workflow passed (1 test).
- Render Blueprints: both YAML files parsed successfully.
- Not verified: live Render ingress, Neon/PostgreSQL, Upstash, deployed TLS/cookies, or a public deployment. No credentials or external services were used for these checks.

Evidence: [Render Web Services](https://render.com/docs/web-services) documents TLS termination at its load balancer and HTTP forwarding to the service. [Render's DDoS/rate-limit guidance](https://render.com/articles/how-render-handles-ddos-attacks) identifies Cloudflare and Render load balancers in the public path but does not specify XFF hop counts. [Render's public-service client-IP guidance](https://render.com/articles/host-pocketbase-on-render) says Cloudflare overwrites `CF-Connecting-IP` with the visitor IP and explains why XFF may contain caller-controlled entries. [Werkzeug ProxyFix](https://werkzeug.palletsprojects.com/en/stable/middleware/proxy_fix/) requires a separate exact trusted-proxy count for each forwarded header and warns about forged values.

The app validates the exact HTTPS origin, secure HttpOnly/SameSite=Lax cookies, live AI and exact GPT-6 Luna model, database, Redis TLS URL, the Render-specific client-IP source, and zero forwarded-header trust at startup. Session ownership, CSRF, ETags, idempotency, AI limits, Pydantic validation, and safe errors remain enabled.

The usage estimator applies the standard short-context input/output rates and discounts cached input tokens when the provider reports them. It is an estimate, not billing data; it does not model cache-write surcharges or other pricing tiers. The app's bounded contexts are intended to remain within the documented short-context tier. Verify OpenAI pricing before launch.

## Startup, migration, and health behavior

The free startup script runs these steps in order and stops on the first failure:

1. Import the Flask app; Pydantic validates production settings without printing secret values.
2. Run bounded, read-only PostgreSQL `SELECT 1` probes first, then TLS Redis `PING` probes (up to three attempts per dependency, two-second waits). Failures emit allowlisted categories such as `PREFLIGHT_DATABASE_TLS_FAILED` or `PREFLIGHT_REDIS_TIMEOUT`; PostgreSQL SQLSTATE may be included after validation. Driver text, URLs, usernames, hosts, and credentials are never emitted.
3. Run `flask db upgrade` using the checked-in Alembic migrations.
4. Start one Gunicorn worker with two threads and bounded timeouts.

There is no production `db.create_all()`, no migration downgrade/reset, and no database recreation. `numInstances: 1` and auto-deploy off keep this a single-instance migration path. If preflight or a migration fails, Gunicorn does not start and the service remains unhealthy. `/api/v1/health/ready` requires the migrated database, reachable Redis, and configured live AI; `/api/v1/health/live` reports process liveness.

## Post-deployment verification

After you authorize deployment and enter the secrets:

1. Open the Render service URL over HTTPS and wait through any cold start.
2. Check `/api/v1/health/live` and `/api/v1/health/ready`; readiness must show database, rate-limit store, and AI configured without exposing endpoints or credentials.
3. Refresh a nested SPA route and verify the React app loads. Check browser console and Network for errors.
4. Create a small test event, refresh, and confirm it reloads. Do not store real personal event information in a public demo.
5. From the Render dashboard, restart the free web service. Confirm the same event remains in Neon afterward. Do not restart/delete the Neon project.
6. Test a Ripple preview, cancel it, and confirm the persisted guest count did not change; then test an explicitly confirmed change.
7. Only after a cost budget is authorized, make one small live GPT-6 Luna blueprint request. Confirm the saved plan and usage record; never repeat automatically or expose prompts/keys in logs.
8. Check OpenAI usage, Neon compute/storage, Upstash command/data/bandwidth, and Render instance hours, bandwidth, and build minutes. Set provider budget alerts/limits where available.

No live API request, cloud resource, remote database/Redis connection, migration against a hosted database, Docker image build, or deployment was performed during this preparation. Automated tests use isolated local databases and mocked AI responses.

## Local verification recorded 2026-10-31

- Backend: **77 passed** with Pytest, including production configuration validation, sanitized startup preflight, repeatable Alembic upgrade on disposable in-memory SQLite, PostgreSQL URL normalization, bounded pool settings, TLS verification in the installed Flask-Limiter Redis backend, readiness behavior, and cached-token cost estimates.
- Frontend: TypeScript check passed; ESLint passed; Vitest **8 passed**; Vite production build passed.
- Browser: offline demo Playwright **1 passed**; Flask-backed mocked-provider Playwright **3 passed**, including the main planning/Ripple journey, cross-session isolation, and responsive/axe scans. These use an isolated SQLite database and do not represent a live OpenAI or hosted database test.
- Deployment files: `render-free.yaml` parsed and assertions confirmed exactly one `free` Docker web service, required dashboard placeholders, GPT-6 Luna settings, and no paid Render database/Key Value resources. `backend/start-free-render.sh` passed shell syntax validation with Git Bash. `git diff --check` passed.
- Security: `.env`, `context.md`, local database files, dependencies, builds, caches, and browser artifacts are ignored as expected. A pattern scan of **99 non-ignored candidate files (2.14 MiB)** found no credential-shaped values; `.env.example` contains an empty OpenAI key value and test credentials are labeled placeholders. The private `.env` file was excluded from reading.
- Docker: `docker build --tag momentos-free-verify:local .` **passed**. The built image ran with isolated demo settings and in-memory SQLite; `/api/v1/health/ready`, `/`, `/events/new?type=wedding`, and the emitted JavaScript asset each returned HTTP 200. The container was removed after the check; the local image tag remains available.
- Production command: `backend/start-free-render.sh` was run inside that image with unreachable loopback-only database/Redis endpoints. It returned sanitized `OperationalError` from `production-preflight`, exited nonzero, and did not start Gunicorn. This verifies fail-closed behavior, not a successful production migration/startup.
- Not verified: real PostgreSQL/Neon migrations and persistence, a real Upstash connection, deployed TLS/cookie behavior, concurrent production traffic, live GPT-6 Luna requests during this preparation, and any public deployment. The Render proxy-count blocker is resolved without trusting forwarded-header hop counts; the documented Cloudflare client-IP header is used only for rate limiting.

## Official references

- [Render Blueprint setup and custom Blueprint path](https://render.com/docs/infrastructure-as-code)
- [Render Blueprint YAML reference](https://render.com/docs/blueprint-spec)
- [Render Free service limits](https://render.com/docs/free)
- [Render deploy commands and pre-deploy restrictions](https://render.com/docs/deploys)
- [Neon secure connections and `verify-full`](https://neon.com/docs/connect/connect-securely)
- [Neon connection pooling and migration guidance](https://neon.com/docs/connect/connection-pooling)
- [PostgreSQL libpq connection parameters and system CA roots](https://www.postgresql.org/docs/current/libpq-connect.html)
- [Psycopg 3 binary installation and bundled libpq](https://www.psycopg.org/psycopg3/docs/basic/install.html)
- [Neon pricing and current Free limits](https://neon.com/pricing)
- [Upstash TCP/TLS connection setup for Render](https://upstash.com/docs/redis/quickstarts/render)
- [redis-py TLS connection parameters](https://redis.readthedocs.io/en/stable/connections.html)
- [Upstash Redis pricing and Free limits](https://upstash.com/pricing/redis)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
