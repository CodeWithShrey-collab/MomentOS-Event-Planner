# MomentOS — Free Deployment Checklist

**Status (2026-10-31): deployed.** The existing Render Free service is publicly available at [https://momentos-event-planner-free.onrender.com](https://momentos-event-planner-free.onrender.com); its readiness endpoint returned HTTP 200 on this date. This runbook remains a checklist for repeating deployment verification and for checks that are not established by a readiness response. OpenAI requests remain usage-billed; provider quotas/overages can change. Do not create duplicate resources or change infrastructure without authorization.

## Before provisioning

- [ ] Confirm `render-free.yaml` is the selected Render Blueprint path. Do not import the paid root `render.yaml`.
- [ ] Review the Blueprint preview and confirm it creates exactly one `free` Docker web service and no Render Postgres/Key Value resources.
- [ ] Confirm current free-tier terms, usage/billing safeguards, and regions in Render, Neon, and Upstash dashboards.
- [ ] Confirm an approved GPT-6 Luna usage budget; no model substitution is permitted.

## External accounts and environment

- [ ] Create a Neon Free PostgreSQL project in a region close to Render; keep autosuspend enabled.
- [ ] Copy a direct Neon connection string from **Connect**, with pooling turned off for repeatable Alembic migrations. Keep it private.
- [ ] Create an Upstash Free Redis database near Render.
- [ ] Copy **Connect → TCP** `rediss://` connection URL, not REST HTTPS. Keep it private.
- [ ] Create the Render service from `render-free.yaml` path or configure the manual Docker service exactly as in the [guide](08_free_deployment_guide.md).
- [ ] Set `APP_ENV=production`, `AI_MODE=live`, `OPENAI_MODEL=gpt-6-luna`, `OPENAI_REASONING_EFFORT=low`, secure cookies, exact HTTPS `APP_BASE_URL`/`TRUSTED_ORIGINS`, Neon `DATABASE_URL`, and Upstash `RATE_LIMIT_STORAGE_URI`.
- [ ] Put `OPENAI_API_KEY`, Neon URL, Upstash URL, and any manual `SECRET_KEY` only in the Render dashboard secret fields.
- [ ] Set `RATE_LIMIT_CLIENT_IP_SOURCE=render_cf_connecting_ip` only for the public Render web service using Cloudflare ingress. Keep `PROXY_FIX_X_FOR=0`, `PROXY_FIX_X_PROTO=0`, and `PROXY_FIX_X_HOST=0`; production startup rejects nonzero forwarded-header trust.
- [ ] Ensure request quotas remain bounded and cost monitoring/alerts are enabled where available.

## Startup and deployment checks

- [ ] Confirm preflight runs DB `SELECT 1` and Redis `PING`; logs contain no URLs, credentials, prompts, or event data.
- [ ] Confirm Alembic `flask db upgrade` finishes successfully before Gunicorn starts. A failed preflight/migration must leave the service unhealthy.
- [ ] Confirm Render Free service serves the Vite build and `/api/v1/health/ready` is healthy.
- [ ] Confirm root and nested SPA URLs load over HTTPS and HTTPS cookies are Secure, HttpOnly, and SameSite=Lax.
- [ ] Confirm session isolation, CSRF, rate limiting, ETags, idempotency, and safe errors remain active.
- [ ] Confirm request limits use a validated single `CF-Connecting-IP`; if absent/malformed, limits fall back to the socket peer and remain enabled.
- [ ] Create an illustrative test event and verify create/read/update after page refresh.
- [ ] Restart the Render web service (do not delete/recreate Neon); verify the event remains persisted.
- [ ] Verify Ripple preview/cancel leaves stored event unchanged and explicit confirmation persists the result.
- [ ] Only with an authorized budget, make one controlled live GPT-6 Luna request and verify validated output, save, usage metadata, and no browser-visible secret.
- [ ] Review Render, Neon, Upstash, and OpenAI quota/usage dashboards after testing.
- [x] Record the public URL: https://momentos-event-planner-free.onrender.com. Recheck readiness before relying on service health; do not infer untested workflow behavior from the landing page.

## Operational limits

- Render Free sleeps after 15 minutes without inbound traffic; cold starts take about a minute. Its filesystem is ephemeral, the service can restart, and persistent disks/SSH/multiple instances are unavailable.
- Neon Free has per-project storage/compute quotas and may autosuspend. A first database request can wait for compute to wake.
- Upstash Free has command, storage, and bandwidth limits. Redis errors fail readiness/rate-limited operations; no memory fallback is permitted.
- Free tier quotas are not a production SLA. OpenAI is billed independently and can incur costs even when hosting resources are free.
- The public readiness response checks the configured database, expected schema, and Redis ping. It is a point-in-time dependency check, not a substitute for persistence across restart, proxy-header behavior, or a complete live AI workflow test.
