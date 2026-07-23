# Deployment

NexGuard deploys as two units: the **frontend** to Vercel and the **backend
(API + Postgres + Redis)** to Render (or Railway/any container host). Everything
stays local-first — the only external service is the model host you choose.

## Live demo

| Unit | URL |
|------|-----|
| **Console (Vercel)** | https://nexguard-sandy.vercel.app |
| **API (Railway)** | https://nexguard-api-production-713d.up.railway.app · [`/docs`](https://nexguard-api-production-713d.up.railway.app/docs) · [`/health`](https://nexguard-api-production-713d.up.railway.app/health) |

Sign in with the seeded demo analyst (shown on the login screen):
`analyst@nexguard.local` / `NexGuardAnalyst!23`.

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

### Railway

The live API runs on Railway, configured by [`backend/railway.toml`](../backend/railway.toml)
(Docker build, `startCommand = nexguard serve --port 8000`, `/health` check). Deploy
from `backend/` with the Railway CLI:

```bash
cd backend
railway login
railway init --name nexguard          # create the project
railway add --database postgres        # + redis
railway add --database redis
railway add --service nexguard-api     # the API service
railway volume add --mount-path /models   # (optional) persist model artifacts
```

Then set env vars on `nexguard-api` (`railway variables --set …`): `NEXGUARD_ENV=production`,
`NEXGUARD_EVENT_BUS=memory` (single instance), `NEXGUARD_LLM_PROVIDER=stub`,
`NEXGUARD_JWT_SECRET=<strong>`, and — importantly — point the DB at the **public**
connection string so the container isn't subject to private-network cold-start:
`NEXGUARD_DATABASE_URL=${{Postgres.DATABASE_PUBLIC_URL}}`. Deploy with `railway up`,
then `railway domain --port 8000`.

**Two Railway gotchas learned the hard way** (both encoded above):

1. Railway only wraps `startCommand` in a shell when it contains a shell operator
   (`&&`), so `${PORT:-8000}` in a bare command is passed *literally*. Use a literal
   port (`--port 8000`); the image `EXPOSE`s 8000.
2. Running `alembic upgrade head` at container boot hangs on Railway's DB connect
   (private-network cold start). Apply migrations and seed **once, out of band**
   against the public proxy instead of on every boot:
   ```bash
   NEXGUARD_DATABASE_URL="<DATABASE_PUBLIC_URL>" \
     uv run --extra postgres alembic upgrade head
   NEXGUARD_DATABASE_URL="<DATABASE_PUBLIC_URL>" NEXGUARD_EVENT_BUS=memory \
     uv run --extra postgres nexguard seed
   ```
   The app's production startup needs no DB and `/health` is DB-free, so `serve`
   becomes healthy immediately; the DB is only touched on real API calls.

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
