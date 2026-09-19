"""CI orchestration — create run, submit results, evaluate regression.

Never modifies experiment baselines. Never prints API keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evalsure_cli.ci_config import CiConfigError, EvalSureCiConfig, load_ci_config
from evalsure_cli.ci_results import CiResultsError, load_results_file
from evalsure_cli.exit_codes import (
    EXIT_API,
    EXIT_CONFIG,
    EXIT_PASS,
    EXIT_REGRESSION_FAIL,
)
from evalsure_cli.output import console, err_console
from evalsure_sdk import EvalSureClient
from evalsure_sdk.exceptions import (
    EvalSureAPIError,
    EvalSureAuthenticationError,
    EvalSureError,
    EvalSureNotFoundError,
    EvalSureTimeoutError,
    EvalSureValidationError,
)
from evalsure_sdk.models import EvaluateRegressionResult, EvaluationRun


@dataclass
class CiRunOutcome:
    exit_code: int
    run_id: str | None = None
    regression_status: str | None = None
    message: str = ""


def collect_github_metadata() -> dict[str, Any]:
    """Optional GitHub Actions metadata for config_snapshot (no secrets)."""
    meta: dict[str, Any] = {}
    mapping = {
        "repository": "GITHUB_REPOSITORY",
        "ref": "GITHUB_REF",
        "sha": "GITHUB_SHA",
        "workflow": "GITHUB_WORKFLOW",
        "workflow_run_id": "GITHUB_RUN_ID",
        "actor": "GITHUB_ACTOR",
    }
    for key, env_name in mapping.items():
        value = os.environ.get(env_name)
        if value:
            meta[key] = value
    # pull_request number when available (set by workflow)
    pr = os.environ.get("EVALSURE_PR_NUMBER") or os.environ.get("GITHUB_PR_NUMBER")
    if not pr:
        ref = os.environ.get("GITHUB_REF", "")
        # refs/pull/123/merge
        parts = ref.split("/")
        if len(parts) >= 3 and parts[0] == "refs" and parts[1] == "pull":
            pr = parts[2]
    if pr:
        meta["pull_request_number"] = pr
    return meta


def _format_metric_aggregates(aggregates: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for name, stats in sorted(aggregates.items()):
        if isinstance(stats, dict) and "average" in stats:
            rows.append((name, f"{float(stats['average']):.4f}"))
        elif isinstance(stats, (int, float)):
            rows.append((name, f"{float(stats):.4f}"))
        else:
            rows.append((name, str(stats)))
    return rows


def print_ci_summary(
    *,
    run: EvaluationRun,
    regression: EvaluateRegressionResult,
) -> None:
    console.print("")
    console.print("[bold]EVALSURE Evaluation[/bold]")
    console.print("")
    console.print(f"Run:\n    {run.id}")
    baseline = (
        regression.regression.baseline_run_id
        or run.baseline_run_id
        or "(none)"
    )
    console.print(f"\nBaseline:\n    {baseline}")

    console.print("\nMetrics:")
    metric_rows = _format_metric_aggregates(run.metric_aggregates or {})
    if metric_rows:
        width = max(len(name) for name, _ in metric_rows)
        for name, value in metric_rows:
            console.print(f"    {name.ljust(width)}  {value}")
    else:
        console.print("    (no aggregates)")

    status = regression.regression.status
    console.print(f"\nRegression:\n    {status}")

    if status == "FAIL":
        count = regression.regression.regressed_case_count
        console.print(f"\nRegressed cases:\n    {count}")
        violations = regression.regression.violations or []
        if violations:
            console.print("\nViolations:")
            for item in violations[:10]:
                metric = item.get("metric", "?")
                reasons = item.get("reasons") or []
                reason_text = "; ".join(str(r) for r in reasons) if reasons else "policy violated"
                console.print(f"    - {metric}: {reason_text}")
        notes = regression.regression.notes or []
        if notes:
            console.print("\nNotes:")
            for note in notes[:5]:
                console.print(f"    - {note}")
    elif status == "NOT_EVALUATED":
        notes = regression.regression.notes or []
        if notes:
            console.print("\nNotes:")
            for note in notes[:5]:
                console.print(f"    - {note}")
    console.print("")


def run_ci(
    client: EvalSureClient,
    *,
    config_path: Path,
    results_path: Path,
) -> CiRunOutcome:
    """Execute the CI quality-gate flow. Does not modify baselines."""
    try:
        config = load_ci_config(config_path)
        results = load_results_file(results_path)
    except (CiConfigError, CiResultsError) as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        return CiRunOutcome(exit_code=EXIT_CONFIG, message=str(exc))

    snapshot: dict[str, Any] = {
        "source": "evalsure_ci",
        "config": config.to_dict(),
    }
    gh_meta = collect_github_metadata()
    if gh_meta:
        snapshot["github"] = gh_meta

    try:
        created = client.runs.create(
            config.project_id,
            dataset_version_id=config.dataset_version_id,
            experiment_id=config.experiment_id,
            metrics=config.metrics,
            config_snapshot=snapshot,
        )
        submitted = client.runs.submit_results(created.id, results=results)
        run = submitted.run
        # Sync path: submit completes the run when all cases are present.
        if run.status != "COMPLETED":
            run = client.runs.get(created.id)

        regression = client.runs.evaluate_regression(created.id)
        # Refresh aggregates / baseline fields after regression
        run = client.runs.get(created.id)
        print_ci_summary(run=run, regression=regression)

        status = regression.regression.status
        if status == "FAIL":
            return CiRunOutcome(
                exit_code=EXIT_REGRESSION_FAIL,
                run_id=str(created.id),
                regression_status=status,
                message="Regression FAIL",
            )
        return CiRunOutcome(
            exit_code=EXIT_PASS,
            run_id=str(created.id),
            regression_status=status,
            message=f"Regression {status}",
        )
    except (EvalSureAuthenticationError, EvalSureTimeoutError) as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        return CiRunOutcome(exit_code=EXIT_API, message=str(exc))
    except (EvalSureNotFoundError, EvalSureValidationError, EvalSureAPIError) as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        return CiRunOutcome(exit_code=EXIT_API, message=str(exc))
    except EvalSureError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        return CiRunOutcome(exit_code=EXIT_API, message=str(exc))
