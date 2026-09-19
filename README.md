# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Phase 0 — auth, projects, API keys
- Phase 1 — datasets, evaluation runs + case results
- Phase 2 Milestone 1 — experiments + baseline designation
- Phase 2 Milestone 2 — **regression detection engine**

Not yet: LLM-as-judge, traces, dashboard, CLI/CI, Redis workers.

## Regression in EVALSURE

A **baseline run** is a completed evaluation run designated on an experiment.

A **regression policy** defines how much quality may drop for a metric:

| Field | Meaning |
|-------|---------|
| `metric_name` | e.g. `string_similarity`, `exact_match` |
| `max_allowed_drop` | Max allowed decrease (0–1). Delta = current − baseline. Fail if delta < −max_allowed_drop |
| `min_aggregate_score` | Optional floor for the current aggregate score |
| `max_regressed_cases` | Optional cap on case-level regressions for that metric |

Statuses:

| Status | Meaning |
|--------|---------|
| `NOT_EVALUATED` | No experiment, no baseline, or no policies |
| `PASS` | All policies satisfied |
| `FAIL` | At least one policy violated |

`EvaluationRun.status` stays **`COMPLETED`** even when regression is `FAIL`.

### Example

```
Baseline string_similarity = 0.94
Current  string_similarity = 0.86
Delta = -0.08
Allowed drop = 0.05

Result: REGRESSION DETECTED (FAIL)
Because -0.08 < -0.05
```

Case-level: a case is regressed if it existed in both runs and either the baseline passed while the current failed, or the metric drop exceeds `max_allowed_drop`.

Incomparable cases (missing on one side, or missing scores) are listed and skipped — they do not crash evaluation.

## Quick API flow

```bash
# Policy
curl -X POST "http://localhost:8000/api/v1/experiments/$EXP_ID/regression-policies" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"metric_name":"string_similarity","max_allowed_drop":0.05,"min_aggregate_score":0.80,"max_regressed_cases":2}'

# After baseline is set and a new COMPLETED run exists:
curl -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/evaluate-regression" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/runs/$RUN_ID" -H "Authorization: Bearer $TOKEN"
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

## New / updated endpoints

| Method | Path |
|--------|------|
| GET | `/api/v1/metrics` |
| POST/GET | `/api/v1/experiments/{id}/regression-policies` |
| DELETE | `/api/v1/regression-policies/{id}` |
| POST | `/api/v1/runs/{id}/evaluate-regression` |
| GET | `/api/v1/runs/{id}` — includes `regression_status` + `regression` |
