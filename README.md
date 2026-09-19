# EVALSURE

An LLM evaluation and regression-testing platform.

## Why EVALSURE?

Traditional unit tests assume **deterministic** outputs: the same input always produces the same answer. LLM applications do not work that way — responses vary, phrasing drifts, and “correct” often means *good enough* rather than *byte-identical*.

EVALSURE treats evaluation like a product workflow:

1. Version **datasets** of inputs and expected outputs  
2. Run evaluations against **actual model outputs**  
3. Score with **metrics** (exact match, string similarity, optional LLM-as-a-judge)  
4. Pin a **baseline** run  
5. Detect **regressions** when a new run gets worse  
6. Inspect **traces** when something fails  

## Current status

### Implemented

- FastAPI backend + PostgreSQL (modular monolith)
- Evaluation datasets, immutable dataset versions, test cases
- Evaluation runs with backend-calculated metrics
- Metrics: `exact_match`, `string_similarity` / `similarity`, `llm_judge` (optional provider)
- Experiments, baselines, regression policies & evaluation
- Append-only evaluation traces (sanitized)
- Python SDK (`evalsure-sdk`) and CLI (`evalsure`)
- GitHub Actions CI quality gate (`evalsure ci run`, exit codes 0/1/2/3)
- Next.js web dashboard (JWT login/register, run compare, API keys UI)
- Docker Compose (`db` + `api` + `web`)
- Pagination, structured API errors, request IDs, readiness probe

### Intentionally deferred

- OAuth / social login, billing, multi-tenancy / orgs, RBAC
- Redis workers, websockets, Kubernetes, cloud deploy automation
- Hosting or proxying customer models

## Core capabilities

| Area | What you get |
|------|----------------|
| Datasets | Project-scoped datasets with immutable versions |
| Test cases | `external_id`, input, expected, metadata, tags |
| Evaluation runs | Submit actual outputs; backend scores metrics |
| Metrics | Exact match, string similarity, optional LLM judge |
| Experiments | Group runs; set baseline; configure regression policies |
| Regression | Aggregate + per-case checks vs baseline |
| Traces | Append-only timeline of run/case/metric events |
| SDK / CLI | Automate evaluations from Python or the shell |
| CI | Fail PRs when regression policies fail |
| Dashboard | Browse projects, runs, compare, traces, API keys |
| Auth | JWT for humans; hashed project API keys for machines |

## Architecture overview

```
Web Dashboard / CLI / SDK
           ↓
       FastAPI API
           ↓
       Service Layer
           ↓
   PostgreSQL (+ metrics / regression / traces)
```

EVALSURE is a **modular monolith**: one API process, one database, clear package boundaries (`apps/api`, `apps/web`, `packages/sdk`, `packages/cli`).

See [docs/architecture.md](docs/architecture.md) for module and data-model detail.

## Repository structure

```
EvalSure/
├── apps/api/           # FastAPI app, Alembic migrations, API tests
├── apps/web/           # Next.js dashboard
├── packages/sdk/       # Python client library
├── packages/cli/       # Typer CLI (`evalsure`)
├── examples/           # CI sample, basic walkthrough, regression demo
├── docs/               # Quickstart + architecture
├── docker-compose.yml  # db + api + web
└── .github/workflows/  # EVALSURE CI workflow template
```

Migrations live in `apps/api/alembic/`. Backend tests: `apps/api/tests/`. SDK/CLI tests: `packages/*/tests/`.

## Prerequisites

| Tool | Notes |
|------|--------|
| Python | **≥ 3.11** (API/SDK/CLI; CI workflow uses 3.12) |
| Node.js | **≥ 18** (dashboard; Docker image uses 22) |
| PostgreSQL | **16** recommended (Compose uses `postgres:16-alpine`) |
| Docker | Optional — for Compose workflow |
| Git | Clone / version control |

## EVALSURE workflow

```
Project
   ↓
Dataset
   ↓
Dataset Version  (immutable snapshot)
   ↓
Test Cases
   ↓
Evaluation Run   (submit actual outputs)
   ↓
Metrics          (backend scores)
   ↓
Baseline         (pin a COMPLETED run on an experiment)
   ↓
Regression Detection
```

## Quick start

**Docker (recommended for first run)**

```bash
git clone <repo-url>
cd EvalSure
cp .env.example .env
# Set a strong EVALSURE_JWT_SECRET in .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI (Swagger) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/health |
| Ready | http://localhost:8000/ready |

Then open http://localhost:3000/register, create an account, and create a project.

**Full step-by-step (API + dataset + run + regression):** [docs/quickstart.md](docs/quickstart.md)  
**Deterministic sample data:** [examples/basic/](examples/basic/) · **Full regression demo:** [examples/regression_demo/](examples/regression_demo/)

### Run the regression demo

With the API running (and `packages/sdk` installed):

```bash
export EVALSURE_API_URL=http://localhost:8000
python examples/regression_demo/run_demo.py
echo $?   # expect 1 — RegressionService detected intentional quality drop
```

This creates an isolated project, baseline vs degraded run, policy evaluation, traces, and prints dashboard URLs. No paid LLM required. Details: [examples/regression_demo/README.md](examples/regression_demo/README.md).

### Docker commands

```bash
docker compose up --build       # foreground
docker compose up -d --build    # detached
docker compose down             # stop (keeps DB volume)
docker compose logs -f
docker compose build --no-cache
```

`docker compose down -v` **destroys** the Postgres volume — only use intentionally.

## Local development (without Docker)

### 1. PostgreSQL

Create a database/user matching `apps/api/.env.example`, or use Compose **only for Postgres**:

```bash
docker compose up -d db
```

### 2. API

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # edit DATABASE_URL + EVALSURE_JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Dashboard

```bash
cd apps/web
cp .env.example .env.local  # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

### 4. SDK / CLI

```bash
# from repo root, with API venv or a dedicated env
pip install -e "packages/sdk[dev]" -e "packages/cli[dev]"
```

## Environment variables

**Never commit real secrets.** Prefer placeholders in `.env.example` files.

### Required (API / Compose)

| Variable | Purpose |
|----------|---------|
| `EVALSURE_JWT_SECRET` | JWT signing secret (≥ 16 chars). Alias: `JWT_SECRET` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Compose database bootstrap |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://…`) |
| `DATABASE_URL_SYNC` | Alembic sync URL (`postgresql://…`) |

Compose sets `DATABASE_URL*` to the `db` hostname automatically.

### Auth & CORS

| Variable | Default | Purpose |
|----------|---------|---------|
| `EVALSURE_JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `EVALSURE_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Access token lifetime |
| `EVALSURE_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated browser origins |

### Web

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Browser → API (e.g. `http://localhost:8000`) |
| `EVALSURE_API_INTERNAL_URL` | Server-side Next → API in Compose (`http://api:8000`) |
| `EVALSURE_ACCESS_TOKEN` | Optional server-only JWT fallback for CI (never `NEXT_PUBLIC_`) |

### SDK / CLI

| Variable | Purpose |
|----------|---------|
| `EVALSURE_API_URL` | API base URL |
| `EVALSURE_API_KEY` | Project API key (`evs_…`) |
| `EVALSURE_ACCESS_TOKEN` | JWT (needed to create/list projects) |

### LLM judge (optional)

Only required when a run includes the `llm_judge` metric:

| Variable | Purpose |
|----------|---------|
| `EVALSURE_JUDGE_API_KEY` | Provider API key (never logged or snapshotted) |
| `EVALSURE_JUDGE_PROVIDER` | Default `openai_compatible` |
| `EVALSURE_JUDGE_MODEL` | Model name |
| `EVALSURE_JUDGE_BASE_URL` | Chat completions base URL |
| `EVALSURE_JUDGE_TIMEOUT_SECONDS` | HTTP timeout |

Files: root `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`.

## Authentication

**Dashboard (humans):** register/login → JWT in httpOnly cookie → protected routes.

**SDK / CLI / CI (machines):** create a project API key in the dashboard (`/projects/[id]/settings/api-keys`). Plaintext is shown **once**; only a hash is stored. Send `X-API-Key: evs_…`.

## SDK usage

```python
from evalsure_sdk import EvalSureClient

# JWT required to create projects; API key is enough for project-scoped work later.
client = EvalSureClient(
    base_url="http://localhost:8000",
    access_token="...",          # from POST /api/v1/auth/login
)

project = client.projects.create(name="support-bot")
dataset = client.datasets.create(project.id, name="faq-v1")
version = client.datasets.create_version(
    dataset.id,
    test_cases=[
        {
            "external_id": "refund-policy",
            "input": {"question": "What is your refund policy?"},
            "expected": {"answer": "Refunds are available within 30 days."},
        },
    ],
)

# After creating an API key in the dashboard, prefer api_key= for automation:
# client = EvalSureClient(base_url="...", api_key="evs_...")

experiment = client.experiments.create(project.id, name="faq-regression")
run = client.runs.create(
    project.id,
    dataset_version_id=version.id,
    experiment_id=experiment.id,
    metrics=["exact_match", "string_similarity"],
)

cases = client.datasets.list_test_cases(version.id)
client.runs.submit_results(
    run.id,
    results=[
        {
            "test_case_id": cases[0].id,
            "actual_output": {"answer": "Refunds are available within 30 days."},
        },
    ],
)

client.experiments.set_baseline(experiment.id, run.id)
# Later runs: client.runs.evaluate_regression(new_run.id)
```

## CLI usage

```bash
export EVALSURE_API_URL=http://localhost:8000
export EVALSURE_ACCESS_TOKEN=...   # JWT
# and/or
export EVALSURE_API_KEY=evs_...

evalsure projects create "support-bot"
evalsure datasets create <PROJECT_ID> --name "faq-v1"
evalsure datasets create-version <DATASET_ID> -f examples/basic/dataset_cases.json
evalsure experiments create <PROJECT_ID> --name "faq-regression"
evalsure runs create <PROJECT_ID> <VERSION_ID> \
  --experiment-id <EXPERIMENT_ID> \
  --metrics exact_match,string_similarity
# After mapping external_id → test_case_id UUIDs (see examples/basic/run_walkthrough.py):
evalsure runs submit-results <RUN_ID> -f /tmp/results_v1.json
evalsure experiments baseline <EXPERIMENT_ID> <RUN_ID>
evalsure runs regression <RUN_ID>
evalsure traces run <RUN_ID>
```

## CI / GitHub Actions

1. Copy [examples/ci/evalsure.yml](examples/ci/evalsure.yml) to repo-root `evalsure.yml` and fill real UUIDs.  
2. Produce `evalsure-results.json` in CI (your app’s evaluation outputs).  
3. Set secrets `EVALSURE_API_URL` and `EVALSURE_API_KEY`.  
4. Workflow [.github/workflows/evalsure.yml](.github/workflows/evalsure.yml) runs `evalsure ci run`.

| Exit code | Meaning |
|-----------|---------|
| **0** | Pass |
| **1** | Regression failure |
| **2** | Usage / configuration error |
| **3** | API / network / authentication error |

## Regression example

**Baseline (v1)** — good answers → `string_similarity ≈ 0.94`  
**Candidate (v2)** — worse paraphrases → `string_similarity ≈ 0.86`  

```
Delta:  -0.08
Policy: max_allowed_drop = 0.05
Result: REGRESSION FAIL
```

The evaluation run status stays **COMPLETED**; `regression_status` becomes **FAIL**. Inspect regressed cases and traces in the dashboard or via CLI.

See [examples/basic/](examples/basic/) for files you can submit.

## API documentation

With the API running:

- Swagger UI: http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  
- OpenAPI JSON: http://localhost:8000/openapi.json  

Prefix for application routes: `/api/v1`.

### Conventions

**Pagination:** `?page=1&page_size=50` (max 200) → `{ "items", "page", "page_size", "total" }`  

**Errors:**

```json
{ "error": { "code": "RUN_NOT_FOUND", "message": "Evaluation run was not found." } }
```

**Request ID:** optional `X-Request-ID` header — echoed on responses and included in logs.

## Development commands

```bash
# Backend
cd apps/api && pytest
cd apps/api && alembic upgrade head
cd apps/api && uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/web && npm test
cd apps/web && npm run lint
cd apps/web && npm run build
cd apps/web && npm run dev

# SDK + CLI
pytest packages/sdk packages/cli

# Full suite (from repo root, with deps installed)
cd apps/api && pytest
pytest packages/sdk packages/cli
cd apps/web && npm test && npm run build
```

No project-wide Python formatter/linter is configured beyond what you run locally; the web app uses `next lint`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Migrations / API won’t start | Postgres up; `DATABASE_URL`; `EVALSURE_JWT_SECRET` set |
| Dashboard empty / unauthorized | Sign in at `/login`; `NEXT_PUBLIC_API_URL` |
| CORS errors | `EVALSURE_CORS_ORIGINS` includes the dashboard origin |
| Judge failures | `EVALSURE_JUDGE_API_KEY` only needed for `llm_judge` |
| Compose web can’t reach API (SSR) | `EVALSURE_API_INTERNAL_URL=http://api:8000` |

## Learn more

- [docs/quickstart.md](docs/quickstart.md) — clone → first regression check  
- [docs/architecture.md](docs/architecture.md) — modules, lifecycle, auth  
- [examples/basic/](examples/basic/) — deterministic dataset + results  
- [examples/regression_demo/](examples/regression_demo/) — end-to-end regression quality gate  
- [examples/ci/](examples/ci/) — CI config & results sample  
