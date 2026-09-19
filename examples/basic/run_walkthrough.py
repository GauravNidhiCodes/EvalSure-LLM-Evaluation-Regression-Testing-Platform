#!/usr/bin/env python3
"""Deterministic EVALSURE walkthrough — no external LLM required.

Requires a running API and EVALSURE_ACCESS_TOKEN (JWT from /auth/register or /auth/login).

  export EVALSURE_API_URL=http://localhost:8000
  export EVALSURE_ACCESS_TOKEN=...
  python examples/basic/run_walkthrough.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from evalsure_sdk import EvalSureClient

HERE = Path(__file__).resolve().parent


def _load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _results_payload(by_external: dict, cases: list) -> list[dict]:
    mapping = {c.external_id: c.id for c in cases}
    out: list[dict] = []
    for external_id, actual in by_external.items():
        if external_id not in mapping:
            raise SystemExit(f"Unknown external_id in results file: {external_id}")
        out.append({"test_case_id": str(mapping[external_id]), "actual_output": actual})
    return out


def main() -> int:
    base_url = os.environ.get("EVALSURE_API_URL", "http://localhost:8000")
    token = os.environ.get("EVALSURE_ACCESS_TOKEN")
    if not token:
        print("Set EVALSURE_ACCESS_TOKEN (JWT from /api/v1/auth/register or /login).", file=sys.stderr)
        return 2

    client = EvalSureClient(base_url=base_url, access_token=token)
    cases_doc = _load("dataset_cases.json")
    v1 = _load("results_v1.json")["results_by_external_id"]
    v2 = _load("results_v2.json")["results_by_external_id"]

    project = client.projects.create(name="basic-example")
    print(f"project_id={project.id}")

    dataset = client.datasets.create(project.id, name="faq-basic")
    print(f"dataset_id={dataset.id}")

    version = client.datasets.create_version(dataset.id, test_cases=cases_doc["test_cases"])
    print(f"dataset_version_id={version.id} version={version.version}")

    experiment = client.experiments.create(project.id, name="faq-regression")
    print(f"experiment_id={experiment.id}")

    client.experiments.upsert_regression_policy(
        experiment.id,
        metric_name="string_similarity",
        max_allowed_drop=0.05,
    )

    cases = client.datasets.list_test_cases(version.id)
    metrics = ["exact_match", "string_similarity"]

    # --- Baseline run (good) ---
    run1 = client.runs.create(
        project.id,
        dataset_version_id=version.id,
        experiment_id=experiment.id,
        metrics=metrics,
    )
    print(f"baseline_run_id={run1.id}")
    out1 = client.runs.submit_results(run1.id, results=_results_payload(v1, cases))
    print(f"baseline_status={out1.run.status} aggregates={out1.run.metric_aggregates}")
    client.experiments.set_baseline(experiment.id, run1.id)

    # --- Candidate run (worse) ---
    run2 = client.runs.create(
        project.id,
        dataset_version_id=version.id,
        experiment_id=experiment.id,
        metrics=metrics,
    )
    print(f"candidate_run_id={run2.id}")
    out2 = client.runs.submit_results(run2.id, results=_results_payload(v2, cases))
    print(f"candidate_status={out2.run.status} aggregates={out2.run.metric_aggregates}")

    regression = client.runs.evaluate_regression(run2.id)
    status = regression.regression.status
    print(f"regression_status={status}")
    print(f"regressed_case_count={regression.regression.regressed_case_count}")
    print("Open dashboard compare:", f"{os.environ.get('EVALSURE_WEB_URL', 'http://localhost:3000')}/runs/{run2.id}/compare")

    if status == "FAIL":
        print("Expected FAIL for this demo — v2 is intentionally worse than baseline.")
        return 0
    print("Unexpected regression status for the demo dataset:", status)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
