# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Phase 0 — auth, projects, API keys
- Phase 1 — datasets, evaluation runs + case results
- Phase 2 — experiments, baselines, regression detection
- Phase 3 Milestone 1 — **LLM-as-a-Judge metric** (`llm_judge`)

Not yet: traces, dashboard, CLI/CI, Redis workers.

## LLM-as-a-Judge

Deterministic metrics (`exact_match`, `string_similarity`) miss semantic equivalence.
Example: *"Paris is the capital of France."* vs *"France's capital city is Paris."* —
string match fails, but meaning is aligned.

**`llm_judge`** asks a configured LLM to score actual output against expected output
and returns a normalized score in **[0.0, 1.0]** plus a short reason.

### Environment

```bash
EVALSURE_JUDGE_PROVIDER=openai_compatible   # default
EVALSURE_JUDGE_MODEL=gpt-4o-mini
EVALSURE_JUDGE_API_KEY=                     # required for real calls; never commit
EVALSURE_JUDGE_BASE_URL=https://api.openai.com/v1
EVALSURE_JUDGE_TIMEOUT_SECONDS=60
```

- API keys come only from environment / `.env`
- Keys are **never** stored in `config_snapshot`, DB rows, logs, or API responses
- The test suite uses a **mocked** judge provider — **no real LLM calls** in CI

### Run configuration

```json
{
  "metrics": ["exact_match", "string_similarity", "llm_judge"],
  "config_snapshot": { "model": "my-app-v2" }
}
```

Frozen snapshot (secrets excluded):

```json
{
  "metrics": ["llm_judge"],
  "judge": {
    "provider": "openai_compatible",
    "model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1"
  }
}
```

### Case result example

```json
{
  "llm_judge": {
    "score": 0.91,
    "passed": true,
    "reason": "The response is factually aligned with the reference..."
  }
}
```

Run-level aggregates average **scores only** (reasons stay on each CaseResult):

```json
{
  "llm_judge": {
    "average": 0.87,
    "minimum": 0.61,
    "maximum": 0.98,
    "count": 10
  }
}
```

### Failure handling

If the judge call/parse fails (missing key, timeout, HTTP error, invalid JSON, score outside 0..1):

- that **CaseResult** is marked **FAILED** with an `error_message`
- no silent/fallback score is written for `llm_judge`
- the **EvaluationRun** can still become **COMPLETED** once all cases have results

### Regression

`llm_judge` is a normal numeric metric for regression policies — compare baseline vs current averages with `max_allowed_drop` / `min_aggregate_score`.

## Regression in EVALSURE

A **baseline run** is a completed evaluation run designated on an experiment.

A **regression policy** defines how much quality may drop for a metric:

| Field | Meaning |
|-------|---------|
| `metric_name` | e.g. `string_similarity`, `exact_match`, `llm_judge` |
| `max_allowed_drop` | Max allowed decrease (0–1). Delta = current − baseline. Fail if delta < −max_allowed_drop |
| `min_aggregate_score` | Optional floor for the current aggregate score |
| `max_regressed_cases` | Optional cap on case-level regressions for that metric |

Statuses: `NOT_EVALUATED` | `PASS` | `FAIL` — separate from `EvaluationRun.status`.

## Quick API flow

```bash
# Create run with llm_judge
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/runs" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"dataset_version_id":"'$VERSION_ID'","metrics":["llm_judge"]}'

# Submit outputs (scores computed server-side via judge provider)
curl -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/results" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"results":[{"test_case_id":"...","actual_output":{"answer":"..."}}]}'
```

## Run locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest
```
