# EVALSURE

LLM evaluation and regression-testing platform.

## Current status

- Phase 0 — auth, projects, API keys
- Phase 1 — datasets, evaluation runs + case results
- Phase 2 — experiments, baselines, regression detection
- Phase 3 — LLM-as-a-Judge metric (`llm_judge`)
- Phase 4 Milestone 1 — **evaluation traces + observability**

Not yet: dashboard, GitHub Actions / CLI, Redis workers.

## Evaluation traces

Traces answer: *"What happened when EVALSURE evaluated this test case?"*

They are **lightweight, append-only JSON events** stored in Postgres — not a full
OpenTelemetry collector or distributed tracing system. Use them for evaluation
debugging and observability.

### Event types

| Event | When |
|-------|------|
| `run_started` | Run leaves PENDING on first result batch |
| `case_started` | Case begins processing |
| `model_call` | LLM/provider call (e.g. `llm_judge`) |
| `metric_evaluation` | A metric score is computed |
| `case_completed` / `case_failed` | Case finishes |
| `run_completed` / `run_failed` | Run finishes |

Typical happy path:

```
run_started
→ case_started
→ model_call          (if llm_judge)
→ metric_evaluation
→ case_completed
→ run_completed
```

### API

```bash
GET /api/v1/runs/{run_id}/traces
GET /api/v1/runs/{run_id}/cases/{case_result_id}/traces
```

Example response:

```json
{
  "run_id": "...",
  "events": [
    {"id": "...", "event_type": "run_started", "timestamp": "...", "data": {}},
    {
      "id": "...",
      "event_type": "model_call",
      "timestamp": "...",
      "data": {
        "provider": "openai_compatible",
        "model": "gpt-4o-mini",
        "latency_ms": 842,
        "input_tokens": 120,
        "output_tokens": 65,
        "total_tokens": 185
      }
    },
    {
      "id": "...",
      "event_type": "metric_evaluation",
      "timestamp": "...",
      "data": {"metric": "string_similarity", "score": 0.91}
    }
  ]
}
```

### Latency & tokens

- `latency_ms` is recorded for real provider calls and case evaluation when measured
- Token fields (`input_tokens`, `output_tokens`, `total_tokens`) are included **only**
  when the provider response exposes usage — never estimated or fabricated

### Security

Traces never store API keys, authorization headers, credentials, or env secrets.
Trace endpoints enforce the same project ownership as other run APIs.
Events are **append-only** — there are no update/delete APIs.

## LLM-as-a-Judge

Deterministic metrics (`exact_match`, `string_similarity`) miss semantic equivalence.
**`llm_judge`** scores actual vs expected via a configured LLM (0.0–1.0 + reason).

```bash
EVALSURE_JUDGE_PROVIDER=openai_compatible
EVALSURE_JUDGE_MODEL=gpt-4o-mini
EVALSURE_JUDGE_API_KEY=
EVALSURE_JUDGE_BASE_URL=https://api.openai.com/v1
```

Keys never appear in `config_snapshot`, traces, or API responses. Tests mock the provider.

## Regression

Baseline run + per-metric policies (`max_allowed_drop`, `min_aggregate_score`,
`max_regressed_cases`). Statuses: `NOT_EVALUATED` | `PASS` | `FAIL` — separate from
`EvaluationRun.status`.

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
