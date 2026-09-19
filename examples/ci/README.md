# CI examples

Template files for the GitHub Actions quality gate.

| File | Purpose |
|------|---------|
| `evalsure.yml` | Repo-level CI config (project / experiment / dataset version IDs + metrics) |
| `evalsure-results.json` | Sample results payload shape for `evalsure ci run` |

## Usage

1. Copy `evalsure.yml` to the **repository root** as `evalsure.yml` and replace placeholder UUIDs with real IDs from your EVALSURE project.  
2. In CI, generate `evalsure-results.json` with real `test_case_id` values (same shape as this sample).  
3. Set GitHub secrets `EVALSURE_API_URL` and `EVALSURE_API_KEY`.  
4. The workflow `.github/workflows/evalsure.yml` runs `evalsure ci run`.

**Never** put API keys in `evalsure.yml`.

See also [examples/basic/](../basic/) for a local deterministic walkthrough before wiring CI.
