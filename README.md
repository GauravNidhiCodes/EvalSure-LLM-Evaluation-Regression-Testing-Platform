# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Backend API, SDK, CLI, metrics, experiments, regression, traces, GitHub Actions CI
- **Web dashboard** (`apps/web`) with JWT login/register and project API-key management

Not yet: OAuth, billing, multi-tenancy, Redis workers, websockets.

## Architecture

```
apps/api      FastAPI + PostgreSQL (source of truth)
apps/web      Next.js App Router + TypeScript + Tailwind
packages/sdk  Python SDK
packages/cli  Typer CLI (`evalsure`)
```

## Authentication

### Web Dashboard — JWT

1. Register at `/register` or sign in at `/login`
2. The Next.js app stores the access token in an **httpOnly** cookie (not shown in the UI)
3. Protected routes (`/dashboard`, `/projects`, `/datasets`, `/experiments`, `/runs`, `/traces`, …) redirect unauthenticated users to `/login`
4. Sign out clears the cookie (local session only — no server-side token denylist)

### SDK / CLI / API — Project API keys

1. Sign in to the dashboard (JWT)
2. Open a project → **API keys** (`/projects/[id]/settings/api-keys`)
3. Create a key → plaintext shown **once** → store it as `EVALSURE_API_KEY` / SDK `api_key`
4. Only a hash is persisted; list endpoints never return plaintext
5. Revoke when finished — revoked keys fail authentication immediately

Lifecycle:

```
Create → display once → store hash → use (X-API-Key) → revoke
```

### Backend environment variables

| Variable | Purpose |
|----------|---------|
| `EVALSURE_JWT_SECRET` | HMAC secret for access tokens (required; also accepts `JWT_SECRET`) |
| `EVALSURE_JWT_ALGORITHM` | Default `HS256` |
| `EVALSURE_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `EVALSURE_CORS_ORIGINS` | Comma-separated dashboard origins (default `http://localhost:3000`) |

Production secrets must come from environment / secret management — never commit real values.

## Run backend

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Run dashboard

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 → `/login` (or `/dashboard` when authenticated).

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (default `http://localhost:8000`) |
| `EVALSURE_ACCESS_TOKEN` | Optional server-only JWT fallback for CI (never `NEXT_PUBLIC_`) |

### Dashboard routes

| Route | View |
|-------|------|
| `/login` | JWT sign-in |
| `/register` | Create account |
| `/dashboard` | Overview counts + recent runs |
| `/projects` | Project list |
| `/projects/[id]` | Project detail + links |
| `/projects/[id]/settings/api-keys` | Create / list / revoke API keys |
| `/projects/[id]/datasets` | Datasets |
| `/projects/[id]/experiments` | Experiments |
| `/projects/[id]/runs` | Runs (aggregated from experiments) |
| `/datasets/[id]` | Dataset + versions |
| `/datasets/[id]/versions/[versionId]` | Test cases |
| `/experiments/[id]` | Experiment, policies, runs |
| `/runs/[id]` | Metrics, regression, case results |
| `/runs/[id]/compare` | Baseline vs current run comparison |
| `/runs/[id]/traces` | Trace timeline |
| `/traces` | Pick a run to inspect traces |
| `/settings` | API connection / session status |

### Run Comparison

Compare a **completed** evaluation run against its experiment **baseline** at `/runs/[runId]/compare` (also linked from run detail and experiment recent runs when a baseline exists).

The UI loads current + baseline runs and case results from the API. Metric deltas use `current − baseline`. Regression PASS / FAIL / NOT_EVALUATED and regressed cases come from the backend regression payload — the dashboard does not re-implement the regression engine.

| Concept | Meaning |
|---------|---------|
| Baseline vs current | Experiment baseline run vs the run you opened |
| Metric delta | `current − baseline` (per aggregate / case score) |
| Regression status | Backend `PASS` / `FAIL` / `NOT_EVALUATED` |
| Regressed test cases | Cases listed in API `regression.regressed_cases` |
| Case comparison | Side-by-side scores; missing sides → `NOT_COMPARABLE` |

Example:

```
Baseline:  string_similarity = 0.94
Current:   string_similarity = 0.86
Delta:     -0.08
Policy:    max allowed drop = 0.05
Result:    REGRESSED
```

If the run has no baseline, the page shows: **No baseline configured for this run.**

## SDK / CLI / CI

See earlier sections: `packages/sdk`, `packages/cli`, `.github/workflows/evalsure.yml`, `examples/ci/`.

```bash
pip install -e "packages/sdk[dev]" -e "packages/cli[dev]"
pytest packages/sdk packages/cli
cd apps/api && pytest
cd apps/web && npm test && npm run build
```
