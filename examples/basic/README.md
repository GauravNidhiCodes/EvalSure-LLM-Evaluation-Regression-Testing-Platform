# Basic EVALSURE example (deterministic)

This folder demonstrates a tiny FAQ evaluation **without** calling an external LLM.

| File | Purpose |
|------|---------|
| `dataset_cases.json` | Three test cases (`external_id` + input + expected) |
| `results_v1.json` | Good model outputs (baseline) |
| `results_v2.json` | Worse outputs (should fail regression) |
| `run_walkthrough.py` | End-to-end SDK script |

## Story

1. **v1** answers match the expected strings closely → high `string_similarity`.  
2. Pin v1 as the experiment **baseline**.  
3. **v2** answers are vague / wrong → similarity drops more than `max_allowed_drop=0.05`.  
4. Regression evaluation returns **FAIL**.

## Run it

```bash
# API must be running; register or login for a JWT:
export EVALSURE_API_URL=http://localhost:8000
export EVALSURE_ACCESS_TOKEN='...'

pip install -e packages/sdk
python examples/basic/run_walkthrough.py
```

Then open the printed compare URL in the dashboard.

## Why not paste UUIDs into results files?

Case result submission requires `test_case_id` UUIDs from the API. The walkthrough maps `external_id` → UUID after the dataset version is created. That mirrors how real CI should build `evalsure-results.json`.
