# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Backend API, SDK, CLI, metrics, experiments, regression, traces, GitHub Actions CI
- Web dashboard with JWT login/register and project API-key management
- **Docker Compose** for reproducible local deployment (`db` + `api` + `web`)

Not yet: OAuth, billing, multi-tenancy, Redis workers, Kubernetes, cloud deploy.

## Architecture

```
apps/api      FastAPI + PostgreSQL (source of truth)
apps/web      Next.js App Router + TypeScript + Tailwind
packages/sdk  Python SDK
packages/cli  Typer CLI (`evalsure`)
```

## Quick Start with Docker

```bash
git clone <repo>
cd EvalSure
cp .env.example .env
# Edit .env — at minimum set a strong EVALSURE_JWT_SECRET
docker compose up --build
```

Expected services:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| PostgreSQL | localhost:5432 (optional host access) |

On API startup the container runs `alembic upgrade head` (non-destructive), then serves FastAPI.

### Docker commands

```bash
docker compose up --build          # start (foreground)
docker compose up -d --build       # start detached
docker compose down                # stop (keeps DB volume)
docker compose logs -f             # follow logs
docker compose build --no-cache    # rebuild images
```

`docker compose down` **preserves** the `postgres_data` volume.  
`docker compose down -v` **destroys** database data — only use intentionally.

## Option A — Local development (without Docker)

**API**

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env
# Start PostgreSQL separately, then:
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Dashboard**

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 → `/login`.

## Option B — Docker Compose

Use the Quick Start above. Compose builds `apps/api` and `apps/web`, runs official PostgreSQL 16, and wires networking via service names `db` / `api` / `web`.

- Browser calls the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- Next.js server components call `EVALSURE_API_INTERNAL_URL` (default `http://api:8000`)

## Environment variables

Root `.env` (from `.env.example`) for Compose. Never commit secrets.

**Required**

| Variable | Purpose |
|----------|---------|
| `EVALSURE_JWT_SECRET` | JWT HMAC secret (min 16 chars) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database bootstrap |

**Optional**

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_PORT` / `API_PORT` / `WEB_PORT` | 5432 / 8000 / 3000 | Published host ports |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser → API |
| `EVALSURE_API_INTERNAL_URL` | `http://api:8000` | Web container → API |
| `EVALSURE_JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `EVALSURE_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Token lifetime |
| `EVALSURE_CORS_ORIGINS` | `http://localhost:3000` | CORS allowlist |
| `EVALSURE_JUDGE_*` | (empty key) | LLM judge (optional) |

For non-Docker API-only work, see `apps/api/.env.example`.

## API conventions

### Pagination

List endpoints use `?page=1&page_size=50` (max `page_size=200`) and return:

```json
{ "items": [...], "page": 1, "page_size": 50, "total": 124 }
```

### Errors

Errors use a stable shape (no stack traces):

```json
{ "error": { "code": "RUN_NOT_FOUND", "message": "Evaluation run was not found." } }
```

### Request ID

Send optional `X-Request-ID`. The API echoes it on responses and includes it in structured logs. Never log passwords, API keys, or JWT secrets.

### Health

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | Process liveness |
| `GET /ready` | Database readiness (`SELECT 1`) |

### CI exit codes (CLI)

| Code | Meaning |
|------|---------|
| 0 | Pass |
| 1 | Regression failure |
| 2 | Usage / configuration error |
| 3 | API / network / authentication error |

## Authentication

### Web Dashboard — JWT

1. Register at `/register` or sign in at `/login`
2. httpOnly cookie session (token not shown in UI)
3. Protected routes redirect to `/login`
4. Sign out clears the cookie (no server-side denylist)

### SDK / CLI / API — Project API keys

Create under `/projects/[id]/settings/api-keys` → plaintext once → hash stored → revoke when done.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| API unhealthy / migrations fail | `docker compose logs api`; DB health; JWT secret set |
| Frontend cannot load data | `NEXT_PUBLIC_API_URL` for browser; `EVALSURE_API_INTERNAL_URL` for SSR |
| CORS errors | `EVALSURE_CORS_ORIGINS` must include the dashboard origin |
| Port already in use | Change `API_PORT` / `WEB_PORT` / `POSTGRES_PORT` in `.env` |

## Dashboard routes

| Route | View |
|-------|------|
| `/login` / `/register` | Auth |
| `/dashboard` | Overview |
| `/projects` … `/settings/api-keys` | Projects & keys |
| `/runs/[id]/compare` | Baseline comparison |
| `/runs/[id]/traces` | Traces |

## SDK / CLI / CI

```bash
pip install -e "packages/sdk[dev]" -e "packages/cli[dev]"
pytest packages/sdk packages/cli
cd apps/api && pytest
cd apps/web && npm test && npm run build
```
