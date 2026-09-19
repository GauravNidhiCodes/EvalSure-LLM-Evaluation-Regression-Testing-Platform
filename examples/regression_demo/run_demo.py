#!/usr/bin/env python3
"""EVALSURE regression demo — deterministic, no paid LLM required.

Uses the real SDK → API → metric engine → baseline → RegressionService path.

Exit codes (aligned with `evalsure ci run`):
  0  Regression PASS (quality held)
  1  Regression FAIL (quality dropped — expected for this demo's degraded outputs)
  2  Usage / configuration error
  3  API / network / authentication error

  export EVALSURE_API_URL=http://localhost:8000
  # Optional: reuse a JWT; otherwise a throwaway demo user is registered.
  # export EVALSURE_ACCESS_TOKEN=...
  python examples/regression_demo/run_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from evalsure_sdk import EvalSureClient
from evalsure_sdk.exceptions import EvalSureAuthenticationError, EvalSureError, EvalSureTimeoutError

HERE = Path(__file__).resolve().parent
METRIC = "string_similarity"


def _load(name: str) -> dict[str, Any]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _avg(metric_aggregates: dict[str, Any], metric: str) -> float | None:
    entry = metric_aggregates.get(metric)
    if isinstance(entry, dict) and "average" in entry:
        try:
            return float(entry["average"])
        except (TypeError, ValueError):
            return None
    return None


def _results_payload(by_external: dict[str, Any], cases: list) -> list[dict[str, Any]]:
    mapping = {c.external_id: c.id for c in cases}
    out: list[dict[str, Any]] = []
    for external_id, actual in by_external.items():
        if external_id not in mapping:
            raise SystemExit(f"Unknown external_id in results: {external_id}")
        out.append({"test_case_id": str(mapping[external_id]), "actual_output": actual})
    return out


def _ensure_access_token(base_url: str, existing: str | None) -> str:
    if existing:
        return existing
    email = f"regression-demo-{uuid.uuid4().hex[:10]}@example.com"
    password = f"demo-{uuid.uuid4().hex}"
    url = urljoin(base_url.rstrip("/") + "/", "api/v1/auth/register")
    try:
        response = httpx.post(
            url,
            json={"email": email, "password": password},
            timeout=30.0,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            print("Register succeeded but no access_token in response.", file=sys.stderr)
            raise SystemExit(3)
        print(f"(registered ephemeral demo user {email})")
        print(f"(dashboard login password for this run: {password})")
        return str(token)
    except httpx.HTTPError as exc:
        print(f"Could not register demo user at {url}: {exc}", file=sys.stderr)
        print("Start the API, or set EVALSURE_ACCESS_TOKEN manually.", file=sys.stderr)
        raise SystemExit(3) from exc


def _print_header() -> None:
    print("EVALSURE REGRESSION DEMO")
    print("========================")
    print()


def main() -> int:
    base_url = os.environ.get("EVALSURE_API_URL", "http://localhost:8000")
    web_url = os.environ.get("EVALSURE_WEB_URL", "http://localhost:3000").rstrip("/")
    token = _ensure_access_token(base_url, os.environ.get("EVALSURE_ACCESS_TOKEN"))

    dataset_doc = _load("dataset.json")
    policy = _load("policy.json")
    baseline_outs = _load("baseline_outputs.json")["results_by_external_id"]
    regressed_outs = _load("regressed_outputs.json")["results_by_external_id"]
    metric_name = str(policy.get("metric_name", METRIC))
    max_drop = float(policy["max_allowed_drop"])
    min_agg = policy.get("min_aggregate_score")
    max_cases = policy.get("max_regressed_cases")
    run_metrics = list(policy.get("run_metrics") or [metric_name])

    try:
        client = EvalSureClient(base_url=base_url, access_token=token)
        suffix = uuid.uuid4().hex[:8]
        project = client.projects.create(
            name=f"regression-demo-{suffix}",
            description="Isolated EVALSURE regression demo project (safe to delete).",
        )
        dataset = client.datasets.create(
            project.id,
            name=str(dataset_doc.get("name", "support-faq")),
            description=dataset_doc.get("description"),
        )
        version = client.datasets.create_version(
            dataset.id,
            test_cases=dataset_doc["test_cases"],
        )
        experiment = client.experiments.create(
            project.id,
            name=f"support-faq-regression-{suffix}",
            description="Prompt/model quality gate for the support FAQ assistant.",
        )
        client.experiments.upsert_regression_policy(
            experiment.id,
            metric_name=metric_name,
            max_allowed_drop=max_drop,
            min_aggregate_score=float(min_agg) if min_agg is not None else None,
            max_regressed_cases=int(max_cases) if max_cases is not None else None,
        )

        cases = client.datasets.list_test_cases(version.id)
        case_by_id = {str(c.id): c for c in cases}
        expected_by_ext = {
            c.external_id: (c.expected or {}).get("answer", "") for c in cases
        }

        # --- Baseline (healthy) ---
        baseline_run = client.runs.create(
            project.id,
            dataset_version_id=version.id,
            experiment_id=experiment.id,
            metrics=run_metrics,
        )
        baseline_submit = client.runs.submit_results(
            baseline_run.id,
            results=_results_payload(baseline_outs, cases),
        )
        client.experiments.set_baseline(experiment.id, baseline_run.id)
        baseline_results = {
            r.external_id: r for r in client.runs.list_results(baseline_run.id)
        }

        # --- Current (degraded) ---
        current_run = client.runs.create(
            project.id,
            dataset_version_id=version.id,
            experiment_id=experiment.id,
            metrics=run_metrics,
        )
        current_submit = client.runs.submit_results(
            current_run.id,
            results=_results_payload(regressed_outs, cases),
        )
        current_results = {
            r.external_id: r for r in client.runs.list_results(current_run.id)
        }

        regression = client.runs.evaluate_regression(current_run.id)
        reg = regression.regression
        status = reg.status

        # Traces from the real TraceService (no fabrication)
        traces = client.traces.get_run_traces(current_run.id)
        event_types = sorted({e.event_type for e in traces.events})

        baseline_avg = _avg(baseline_submit.run.metric_aggregates, metric_name)
        current_avg = _avg(current_submit.run.metric_aggregates, metric_name)
        agg = (reg.aggregate or {}).get(metric_name) or {}
        delta = agg.get("delta")
        if delta is None and baseline_avg is not None and current_avg is not None:
            delta = current_avg - baseline_avg

        _print_header()
        print(f"Dataset: {dataset.name}")
        print(f"Test cases: {len(cases)}")
        print(f"Project: {project.id}")
        print(f"Experiment: {experiment.id}")
        print()
        print("Baseline Run")
        print("-------------")
        print(f"Run id: {baseline_run.id}")
        print(f"Metric: {metric_name}")
        print(f"Score: {baseline_avg:.4f}" if baseline_avg is not None else "Score: n/a")
        print(f"Eval status: {baseline_submit.run.status}")
        print("Baseline marker: set via experiments.set_baseline")
        print()
        print("Current Run")
        print("------------")
        print(f"Run id: {current_run.id}")
        print(f"Metric: {metric_name}")
        print(f"Score: {current_avg:.4f}" if current_avg is not None else "Score: n/a")
        print(f"Eval status: {current_submit.run.status}")
        print(f"Regression status: {status}")
        print()
        print("Regression")
        print("----------")
        if delta is not None:
            print(f"Baseline → Current: {delta:+.4f}")
        print(f"Allowed drop: {max_drop}")
        if min_agg is not None:
            print(f"Min aggregate score: {min_agg}")
        if max_cases is not None:
            print(f"Max regressed cases: {max_cases}")
        print(f"Regressed cases: {reg.regressed_case_count}")
        if reg.violations:
            print("Violations:")
            for v in reg.violations:
                print(f"  - {v}")
        print()
        if status == "FAIL":
            print("[FAIL] Regression detected by EVALSURE RegressionService")
        elif status == "PASS":
            print("[PASS] No regression against baseline")
        else:
            print(f"[{status}] Regression not fully evaluated")
        print()

        if reg.regressed_cases:
            print("Affected cases")
            print("--------------")
            for item in reg.regressed_cases:
                tid = str(item.get("test_case_id", ""))
                case = case_by_id.get(tid)
                ext = case.external_id if case else tid
                expected = expected_by_ext.get(ext, "")
                b_out = (baseline_results.get(ext).actual_output or {}).get("answer", "") if baseline_results.get(ext) else ""
                c_out = (current_results.get(ext).actual_output or {}).get("answer", "") if current_results.get(ext) else ""
                b_score = item.get("baseline_score")
                c_score = item.get("current_score")
                c_delta = item.get("delta")
                print(f"{ext}")
                print(f"  Expected: {expected}")
                print(f"  Baseline: {b_out}")
                print(f"  Current:  {c_out}")
                if b_score is not None and c_score is not None and c_delta is not None:
                    print(
                        f"  Scores:   baseline={float(b_score):.4f}  "
                        f"current={float(c_score):.4f}  delta={float(c_delta):+.4f}"
                    )
                print(f"  Reason:   {item.get('reason', '')}")
                print()

        print("Traces (current run)")
        print("--------------------")
        print(f"Events: {len(traces.events)}")
        print(f"Types:  {', '.join(event_types) if event_types else '(none)'}")
        print()
        print("Dashboard")
        print("---------")
        print(f"Compare:     {web_url}/runs/{current_run.id}/compare")
        print(f"Current run: {web_url}/runs/{current_run.id}")
        print(f"Traces:      {web_url}/runs/{current_run.id}/traces")
        print(f"Experiment:  {web_url}/experiments/{experiment.id}")
        print()
        print("Tip: edit policy.json (max_allowed_drop / max_regressed_cases) and re-run.")

        if status == "FAIL":
            return 1
        if status == "PASS":
            return 0
        return 2

    except EvalSureAuthenticationError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 3
    except EvalSureTimeoutError as exc:
        print(f"API unreachable / timed out: {exc}", file=sys.stderr)
        return 3
    except EvalSureError as exc:
        print(f"EVALSURE API error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
