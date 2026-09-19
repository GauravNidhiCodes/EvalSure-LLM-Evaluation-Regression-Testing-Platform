# EVALSURE regression demo

## What this demo proves

EVALSURE can detect when a change to an LLM application **reduces output quality** relative to a known-good baseline — using deterministic metrics, without calling a paid model API.

The demo walks the real product path:

```
Dataset → Dataset Version → Evaluation Run → Metrics
        → Baseline → New Run → RegressionPolicy → RegressionService
        → Regressed cases → Terminal summary (+ dashboard / traces)
```

## What “regression” means here

A **regression** is not “the run failed to execute.” Both the baseline and the current run complete successfully (`COMPLETED`). Regression means:

> Against a pinned baseline run, under a `RegressionPolicy`, quality got worse enough to violate the policy (aggregate drop, floor score, or too many degraded cases).

Traditional tests ask: *Did we get the exact expected string?*  
EVALSURE also asks: *Did quality get worse after this change?*

## Demo architecture

| Piece | Role |
|-------|------|
| `dataset.json` | 10 support-FAQ test cases |
| `baseline_outputs.json` | Healthy model outputs (near exact match) |
| `regressed_outputs.json` | Intentionally worse outputs (vague / incomplete) |
| `policy.json` | Real `RegressionPolicy` knobs |
| `run_demo.py` | Orchestrates **SDK → live API** (no fake scores) |

Degraded cases (by design): `refund-policy`, `password-reset`, `shipping-time`, `cancel-subscription`, `track-order`.

## Prerequisites

- Python ≥ 3.11 with `packages/sdk` installed
- EVALSURE API running against a **development** database
- PostgreSQL reachable as configured in `apps/api/.env`

No OpenAI / Anthropic / Gemini key is required.

## How to start EVALSURE

```bash
# From repo root — Postgres must be up
cd apps/api
source .venv/bin/activate   # or: python -m venv .venv && pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Optional dashboard (another terminal):

```bash
cd apps/web
npm install && npm run dev
```

Compose alternative (if Docker is available): `docker compose up --build` from the repo root.

## How to run the demo

```bash
# From repo root
pip install -e packages/sdk
export EVALSURE_API_URL=http://localhost:8000
# Optional: reuse a JWT; otherwise the script registers an ephemeral demo user
# export EVALSURE_ACCESS_TOKEN='...'

python examples/regression_demo/run_demo.py
echo "exit=$?"
```

The script creates an **isolated** project named `regression-demo-<suffix>` so it does not overwrite your other work. You can delete that project later from the dashboard.

## What output to expect

You should see a summary similar to:

```
EVALSURE REGRESSION DEMO
========================

Dataset: support-faq
Test cases: 10

Baseline Run
-------------
Metric: string_similarity
Score: ~1.0
Eval status: COMPLETED

Current Run
------------
Metric: string_similarity
Score: lower than baseline
Regression status: FAIL

Regression
----------
Baseline → Current: negative delta
Allowed drop: 0.05
Regressed cases: ≥ 3

[FAIL] Regression detected by EVALSURE RegressionService
```

Numbers are **computed by the API**, not hardcoded in the script.

### Exit codes

Aligned with `evalsure ci run`:

| Code | Meaning |
|------|---------|
| **0** | Regression `PASS` |
| **1** | Regression `FAIL` (**expected** for the shipped degraded outputs) |
| **2** | Config / unexpected status |
| **3** | Auth / network / API error |

## How baseline works

1. Submit healthy outputs → run reaches `COMPLETED`.  
2. `client.experiments.set_baseline(experiment_id, run_id)` pins that run as the experiment baseline (existing API).  
3. The baseline run itself is not mutated when later runs are scored.

## How regression is detected

1. Policy from `policy.json` is upserted via `experiments.upsert_regression_policy` (`string_similarity`, `max_allowed_drop=0.05`, `min_aggregate_score=0.85`, `max_regressed_cases=2`).  
2. Current run submits degraded outputs; backend scores metrics.  
3. `client.runs.evaluate_regression(run_id)` calls the real **RegressionService** / engine.  
4. Status and `regressed_cases` come from that evaluation.

## How to inspect in the dashboard

After the script prints URLs:

1. Sign in at http://localhost:3000/login.  
   When the script auto-registers, it prints the ephemeral email **and password** — use those to open the dashboard for that demo project.  
   Or set `EVALSURE_ACCESS_TOKEN` from your own account so data lands under your user.  
2. Open **Compare** on the current run — metrics, deltas, regressed cases.  
3. Open **Traces** — lifecycle events from TraceService (`run_started`, case/metric events, `run_completed`, etc.).  
4. Open the **experiment** — baseline pointer, policies, run list.

## Change the threshold and observe behavior

Edit `policy.json`:

- Raise `max_allowed_drop` to `0.50` and/or `max_regressed_cases` to `10` → often **PASS**.  
- Lower `max_allowed_drop` to `0.01` → still **FAIL**, usually with the same degraded cases.

Re-run the script; each run creates a fresh isolated project.

## Core value

Traditional software tests usually ask:

> Did the program produce the expected deterministic result?

LLM applications need another layer:

> Did the quality of the generated output get worse after this change?

EVALSURE addresses this by scoring outputs with metrics and comparing a completed run against a known baseline under an explicit regression policy — exactly what this demo exercises end to end.
