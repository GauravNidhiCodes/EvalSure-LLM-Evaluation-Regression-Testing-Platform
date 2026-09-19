# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- **Phase 0** — auth, projects, API keys
- **Phase 1 Milestone 1** — datasets, immutable versions, test cases
- **Phase 1 Milestone 2** — evaluation runs + client-submitted case results

Not yet: scoring/metrics, regression, experiments, traces, dashboard, CLI/CI.

## Repository layout

```
EvalSure/
  README.md
  apps/
    api/
      app/
        auth/
        projects/
        datasets/
        evaluations/     # Milestone 2: runs + case results
        core/
      alembic/
      tests/
```

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ running locally

```bash
psql -h 127.0.0.1 -d postgres -c "CREATE ROLE evalsure LOGIN PASSWORD 'evalsure';"
psql -h 127.0.0.1 -d postgres -c "CREATE DATABASE evalsure OWNER evalsure;"
psql -h 127.0.0.1 -d evalsure -c "GRANT ALL ON SCHEMA public TO evalsure; ALTER SCHEMA public OWNER TO evalsure;"
```

## Run the API locally

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Complete flow (dataset → run → results)

```bash
TOKEN=...
PROJECT_ID=...

# 1–2) Dataset + immutable version
DATASET_ID=$(curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/datasets" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"DBMS QA"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

VERSION=$(curl -s -X POST "http://localhost:8000/api/v1/datasets/$DATASET_ID/versions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "test_cases": [
      {
        "external_id": "dbms-001",
        "input": {"question": "What is normalization?"},
        "expected": {"answer": "Normalization is..."},
        "metadata": {"category": "DBMS"},
        "tags": ["dbms"]
      }
    ]
  }')
VERSION_ID=$(echo "$VERSION" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
CASE_ID=$(curl -s "http://localhost:8000/api/v1/dataset-versions/$VERSION_ID/test-cases" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3) Create evaluation run (config snapshot is frozen)
RUN=$(curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/runs" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{
    \"dataset_version_id\": \"$VERSION_ID\",
    \"config_snapshot\": {
      \"model\": \"example-model\",
      \"prompt_version\": \"v3\",
      \"temperature\": 0.2,
      \"retrieval\": {\"top_k\": 5}
    }
  }")
RUN_ID=$(echo "$RUN" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4–5) Submit model outputs (run becomes COMPLETED when every case has a result)
curl -s -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/results" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{
    \"results\": [
      {
        \"test_case_id\": \"$CASE_ID\",
        \"actual_output\": {\"answer\": \"Normalization is...\"}
      }
    ]
  }"

# 6) Retrieve run + results
curl -s "http://localhost:8000/api/v1/runs/$RUN_ID" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/v1/runs/$RUN_ID/results" -H "Authorization: Bearer $TOKEN"
```

**Lifecycle:** `PENDING` → `RUNNING` (first valid results batch) → `COMPLETED` (all cases have results). Completed runs are immutable. Scoring/metrics are not applied in this milestone.

## API surface

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST/GET | `/api/v1/auth/*`, `/projects*` | Phase 0 |
| POST/GET | `/api/v1/projects/{id}/datasets` … | Milestone 1 datasets |
| POST | `/api/v1/projects/{id}/runs` | Create evaluation run |
| GET | `/api/v1/runs/{id}` | Run detail + aggregates |
| POST | `/api/v1/runs/{id}/results` | Submit case outputs |
| GET | `/api/v1/runs/{id}/results` | List case results |

## Tests

```bash
cd apps/api && source .venv/bin/activate && pytest
```

## Configuration

See `.env.example`. Never commit real secrets.
