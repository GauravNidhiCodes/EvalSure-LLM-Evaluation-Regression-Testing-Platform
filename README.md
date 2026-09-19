# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Phase 0–3 — auth, datasets, runs, experiments, regression, LLM-as-a-judge
- Phase 4 Milestone 1 — evaluation traces
- Phase 4 Milestone 2 — **Python SDK + CLI**

Not yet: frontend dashboard, GitHub Actions, Redis workers.

## Python SDK

Install (from repo root):

```bash
pip install -e packages/sdk
```

```python
from evalsure_sdk import EvalSureClient

client = EvalSureClient(
    base_url="http://localhost:8000",
    api_key="evs_...",           # X-API-Key — project-scoped ops
    # access_token="...",        # JWT — required for projects.create / projects.list
)

projects = client.projects.list()  # needs access_token
dataset = client.datasets.create(project_id="...", name="customer-support")
version = client.datasets.create_version(
    dataset.id,
    test_cases=[
        {
            "external_id": "case-1",
            "input": {"question": "What is your refund policy?"},
            "expected": {"answer": "Refunds are available within 30 days."},
        }
    ],
)
run = client.runs.create(
    project_id="...",
    dataset_version_id=version.id,
    metrics=["exact_match", "string_similarity", "llm_judge"],
)
client.runs.submit_results(run.id, results=[...])
client.runs.evaluate_regression(run.id)
client.traces.get_run_traces(run.id)
```

Auth notes:

- Most endpoints accept **`X-API-Key`** (project API key)
- **`projects.create` / `projects.list`** require a JWT (`access_token`) — backend limitation
- API keys are never logged, printed, or stored by the SDK

## CLI

```bash
pip install -e packages/sdk -e packages/cli
export EVALSURE_API_URL=http://localhost:8000
export EVALSURE_API_KEY=evs_...
# optional for project create/list:
# export EVALSURE_ACCESS_TOKEN=...

evalsure --help
evalsure projects list          # needs JWT
evalsure datasets list PROJECT_ID
evalsure datasets create-version DATASET_ID --file dataset.json
evalsure runs create PROJECT_ID DATASET_VERSION_ID --metrics exact_match,string_similarity
evalsure runs submit-results RUN_ID --file results.json
evalsure runs get RUN_ID --json
evalsure runs regression RUN_ID
evalsure experiments baseline EXPERIMENT_ID RUN_ID
evalsure traces run RUN_ID
```

Dataset / results JSON follow the API contract (`input` / `actual_output` are objects).

## Evaluation traces

Append-only JSON events (`run_started` → `case_started` → `model_call` → `metric_evaluation` → …).
See `GET /api/v1/runs/{id}/traces`.

## Run the API locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest
```

SDK / CLI tests (mocked HTTP — no live API):

```bash
pip install -e "packages/sdk[dev]" -e "packages/cli[dev]"
pytest packages/sdk packages/cli
```
