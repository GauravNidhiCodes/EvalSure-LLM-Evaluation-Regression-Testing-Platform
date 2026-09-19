# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- **Phase 0** — auth, projects, API keys
- **Phase 1 Milestone 1** — datasets, immutable versions, test cases
- **Phase 1 Milestone 2** — evaluation runs + client-submitted case results
- **Phase 2 Milestone 1** — experiments + baseline designation

Not yet: scoring execution, regression comparison, traces, dashboard, CLI/CI.

## Concepts

| Concept | Meaning |
|---------|---------|
| **Experiment** | Named workflow that groups related evaluation runs (e.g. “Customer Support RAG”) |
| **Evaluation Run** | One execution against a dataset version, with frozen `config_snapshot` and submitted outputs |
| **Baseline Run** | The completed run an experiment points to for *future* comparisons |

Example:

```
Experiment: Customer Support RAG
  Baseline: Run #12
  New evaluation: Run #18

Future milestone:
  Compare Run #18 against Run #12
  Detect regressions
```

Baseline assignment only stores `baseline_run_id` on the experiment. Historical runs are never rewritten. Regression comparison is **not** implemented in this milestone.

## Repository layout

```
EvalSure/
  apps/api/app/
    auth/ projects/ datasets/ evaluations/ experiments/ core/
```

## Run locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Experiments + baseline (quick example)

```bash
# Create experiment
EXP=$(curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/experiments" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Customer Support RAG","description":"Retrieval quality"}')
EXP_ID=$(echo "$EXP" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create a run linked to the experiment (metrics stored in config_snapshot for reproducibility)
RUN=$(curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/runs" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"experiment_id\":\"$EXP_ID\",\"dataset_version_id\":\"$VERSION_ID\",\"metrics\":[\"exact_match\",\"string_similarity\"]}")
RUN_ID=$(echo "$RUN" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# After the run is COMPLETED, designate it as baseline
curl -s -X POST "http://localhost:8000/api/v1/experiments/$EXP_ID/baseline/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Creating a run **without** `experiment_id` remains supported.

## API surface (additions)

| Method | Path | Description |
|--------|------|-------------|
| POST/GET | `/api/v1/projects/{id}/experiments` | Create / list experiments |
| GET | `/api/v1/experiments/{id}` | Experiment detail (`baseline_run_id`) |
| GET | `/api/v1/experiments/{id}/runs` | Runs in experiment |
| POST | `/api/v1/experiments/{id}/baseline/{run_id}` | Set completed run as baseline |
| POST | `/api/v1/projects/{id}/runs` | Optional `experiment_id`, `metrics` |

## Tests

```bash
cd apps/api && source .venv/bin/activate && pytest
```
