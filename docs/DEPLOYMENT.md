# Deployment

NexGuard deploys as two units: the **frontend** to Vercel and the **backend
(API + Postgres + Redis)** to Render (or Railway/any container host). Everything
stays local-first — the only external service is the model host you choose.

## Local — full stack (fastest)

```bash
docker compose -f docker/docker-compose.yml up --build
#   API → :8000   ·   Console → :3000   ·   (observability profile adds Grafana → :3001)
docker compose -f docker/docker-compose.yml --profile observability up --build
```

The `seed` service migrates, trains detectors, scores the fixture into alerts, and
creates demo users automatically.

## Backend → Render (Blueprint)

A [`render.yaml`](../render.yaml) blueprint provisions the API (Docker), a
PostgreSQL database, a Redis instance, and a 1 GB disk for model artifacts.

1. Push this repo to GitHub.
2. Render → **New + → Blueprint** → select the repo. It reads `render.yaml`.
3. Set `NEXGUARD_CORS_ORIGINS` to your Vercel URL (e.g. `https://nexguard.vercel.app`).
   `NEXGUARD_JWT_SECRET` is auto-generated; the DB/Redis URLs are wired for you.
4. On first deploy, migrations run automatically (`alembic upgrade head`). Then seed
   the demo once from the Render **Shell**:
   ```bash
   nexguard seed
   ```
   (This trains the detectors and writes artifacts to the mounted `/models` disk, so
   they survive restarts.)

> Postgres URL note: Render/Railway hand out `postgres://` URLs; the app normalizes
> them to the async `postgresql+asyncpg://` driver automatically.

**Railway** is equivalent: add PostgreSQL + Redis plugins, deploy the backend from
the repo with **Root Directory = `backend`** (Railway builds `backend/Dockerfile`),
set the same `NEXGUARD_*` env vars, and run `alembic upgrade head && nexguard seed`.

## Frontend → Vercel

1. Vercel → **Add New… → Project** → import the repo.
2. Set **Root Directory** to `frontend` (Next.js is auto-detected; standalone
   output and security headers are already configured).
3. Add env var `NEXT_PUBLIC_API_URL` = your Render API URL (e.g.
   `https://nexguard-api.onrender.com`). It is baked at build time and also derives
   the WebSocket URL.
4. Deploy. Then update the backend's `NEXGUARD_CORS_ORIGINS` to the Vercel URL.

Sign in with the seeded demo credentials shown on the login screen.

## Real LLM reports (optional)

The default `stub` LLM keeps everything working with zero external dependencies.
For real triage reports, run **Ollama** (locally via the `ollama` compose profile,
or a reachable host) and set `NEXGUARD_LLM_PROVIDER=ollama` +
`NEXGUARD_OLLAMA_BASE_URL`.

## Caveats

- Free tiers sleep and are resource-limited; training during `seed` needs a minute.
- The compose demo ships a demo JWT secret and Grafana password — replace both for
  anything real (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- Rate limiting is per-process; back it with Redis for multi-instance.
