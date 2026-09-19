# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Phase 0–4 — auth, datasets, runs, experiments, regression, LLM-as-a-judge, traces, SDK/CLI
- Phase 2 Milestone 3 — **GitHub Actions CI integration**

Not yet: frontend dashboard, Redis workers.

## GitHub Actions CI

EVALSURE can act as a **CI quality gate** for LLM apps:

```
push / pull_request
  → your tests produce evalsure-results.json
  → evalsure ci run
  → submit results + regression vs experiment baseline
  → exit 0 (PASS) or 1 (FAIL) → GitHub Actions job status
```

CI **never** overwrites the experiment baseline.

### 1. Set up EVALSURE

1. Create a project, dataset version, and experiment
2. Designate a **baseline** run on the experiment
3. Configure regression policies

### 2. Add GitHub secrets

Repository → Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|--------|
| `EVALSURE_API_URL` | API base URL (e.g. `https://api.example.com`) |
| `EVALSURE_API_KEY` | Project API key (`evs_...`) |

Never commit API keys.

### 3. Add `evalsure.yml` (no secrets)

```yaml
project_id: "..."
experiment_id: "..."
dataset_version_id: "..."

metrics:
  - exact_match
  - string_similarity
```

See `examples/ci/evalsure.yml`.

### 4. Produce `evalsure-results.json`

Your app/tests generate outputs. Example:

```json
{
  "results": [
    {
      "test_case_id": "...",
      "actual_output": { "answer": "..." }
    }
  ]
}
```

See `examples/ci/evalsure-results.json`. Strings are accepted and wrapped as `{"text": "..."}`.

### 5. Workflow

`.github/workflows/evalsure.yml` runs on `pull_request` and `push` to `main`:

```bash
evalsure ci run --config evalsure.yml --results evalsure-results.json
```

The job fails when regression status is **FAIL**.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Regression **PASS** (or `NOT_EVALUATED` — no policy failure) |
| `1` | Regression **FAIL** |
| `2` | Config / YAML / results file error |
| `3` | API / network / authentication error |

### CLI

```bash
export EVALSURE_API_URL=...
export EVALSURE_API_KEY=...
evalsure ci run --config evalsure.yml --results evalsure-results.json
```

## Python SDK

```bash
pip install -e packages/sdk
```

```python
from evalsure_sdk import EvalSureClient

client = EvalSureClient(base_url="http://localhost:8000", api_key="evs_...")
```

## CLI

```bash
pip install -e packages/sdk -e packages/cli
evalsure --help
evalsure ci run --config evalsure.yml --results evalsure-results.json
```

## Run the API locally

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
pytest
```

```bash
pip install -e "packages/sdk[dev]" -e "packages/cli[dev]"
pytest packages/sdk packages/cli
```
