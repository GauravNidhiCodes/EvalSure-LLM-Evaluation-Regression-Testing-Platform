# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Backend API, SDK, CLI, metrics, experiments, regression, traces, GitHub Actions CI
- **Web dashboard foundation** (`apps/web`) — read-only developer UI

Not yet: frontend login UI, Redis workers, websockets.

## Architecture

```
apps/api      FastAPI + PostgreSQL (source of truth)
apps/web      Next.js App Router + TypeScript + Tailwind
packages/sdk  Python SDK
packages/cli  Typer CLI (`evalsure`)
```

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
# Set EVALSURE_ACCESS_TOKEN to a JWT from POST /api/v1/auth/login
npm install
npm run dev
```

Open http://localhost:3000 → redirects to `/dashboard`.

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (default `http://localhost:8000`) |
| `EVALSURE_ACCESS_TOKEN` | Server-only JWT (never `NEXT_PUBLIC_`) |

### Dashboard routes

| Route | View |
|-------|------|
| `/dashboard` | Overview counts + recent runs |
| `/projects` | Project list |
| `/projects/[id]` | Project detail + links |
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
| `/settings` | API connection status |

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
cd apps/web && npm run build
```
