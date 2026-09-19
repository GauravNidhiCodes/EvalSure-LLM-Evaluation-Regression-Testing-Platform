# EVALSURE Quickstart

Go from an empty clone to a completed evaluation run with baseline regression — using only **deterministic** metrics (`exact_match`, `string_similarity`). No paid LLM provider required.

## 0. Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18 (dashboard only)
- PostgreSQL 16 **or** Docker

## 1. Start the stack

### Option A — Docker Compose

```bash
git clone <repo-url>
cd EvalSure
cp .env.example .env
# Set EVALSURE_JWT_SECRET to a long random string
docker compose up --build
```

Wait until `api` and `web` are healthy. Open:

- Dashboard: http://localhost:3000  
- API docs: http://localhost:8000/docs  

### Option B — Local processes

```bash
# Terminal 1 — Postgres (example via Compose)
docker compose up -d db

# Terminal 2 — API
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # DATABASE_URL → localhost, set EVALSURE_JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Dashboard (optional)
cd apps/web
cp .env.example .env.local
npm install && npm run dev
```

## 2. Create an account (JWT)

Register via the dashboard (`/register`) **or** the API:

```bash
curl -s http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"password123"}'
```

Save `access_token` from the response:

```bash
export EVALSURE_API_URL=http://localhost:8000
export EVALSURE_ACCESS_TOKEN='<access_token>'
```

## 3. Install SDK / CLI

```bash
# from repo root
pip install -e packages/sdk -e packages/cli
```

## 4. Recommended: run the basic walkthrough

```bash
python examples/basic/run_walkthrough.py
```

This script (using the SDK):

1. Creates a project + dataset + version from `dataset_cases.json`  
2. Creates an experiment + regression policy  
3. Submits **v1** results (good) → sets baseline  
4. Submits **v2** results (worse) → evaluates regression → prints PASS/FAIL  

It prints every ID it creates so you can explore them in the dashboard.

## 5. Manual CLI path (same flow)

```bash
# Project
evalsure projects create "support-bot"

# Dataset + version (replace PROJECT_ID)
evalsure datasets create PROJECT_ID --name "faq"
evalsure datasets create-version DATASET_ID -f examples/basic/dataset_cases.json

# Experiment
evalsure experiments create PROJECT_ID --name "faq-regression"

# Create run (replace IDs)
evalsure runs create PROJECT_ID VERSION_ID \
  --experiment-id EXPERIMENT_ID \
  --metrics exact_match,string_similarity

# Build results JSON: map external_id → test_case_id from:
evalsure datasets create-version ...   # already done
# or list cases via SDK / OpenAPI: GET /dataset-versions/{id}/test-cases

# Submit v1 (good), set baseline, then submit v2 (worse) on a NEW run
evalsure runs submit-results RUN_ID -f /path/to/results_with_uuids.json
evalsure experiments baseline EXPERIMENT_ID RUN_ID
evalsure runs regression RUN_ID
```

> Tip: prefer `examples/basic/run_walkthrough.py` so you do not hand-edit UUIDs.

## 6. Create a project API key (for CI / automation)

1. Open the dashboard → Project → **API keys**  
2. Create a key → copy plaintext **once**  
3. Export:

```bash
export EVALSURE_API_KEY='evs_...'
# JWT is no longer required for project-scoped operations
```

## 7. Inspect in the dashboard

| Page | What to look for |
|------|------------------|
| `/projects/...` | Dataset / experiment / runs links |
| `/runs/[runId]` | Metrics, regression status, case results |
| `/runs/[runId]/compare` | Baseline vs current deltas |
| `/runs/[runId]/traces` | Event timeline |

## 8. OpenAPI

Browse interactive docs while the API is running:

http://localhost:8000/docs

## 9. Tests

```bash
cd apps/api && pytest
pytest packages/sdk packages/cli
cd apps/web && npm test && npm run build
```

## Next steps

- Point CI at your EVALSURE deployment — see [examples/ci/](../examples/ci/)  
- Read [architecture.md](architecture.md) for module boundaries  
- Add `llm_judge` only after setting `EVALSURE_JUDGE_API_KEY`  
