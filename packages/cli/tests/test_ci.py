"""CI command and config/result parsing tests — no live network or GitHub."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import yaml
from typer.testing import CliRunner

from evalsure_cli.ci import collect_github_metadata, run_ci
from evalsure_cli.ci_config import CiConfigError, load_ci_config
from evalsure_cli.ci_results import CiResultsError, load_results_file
from evalsure_cli.exit_codes import (
    EXIT_API,
    EXIT_CONFIG,
    EXIT_PASS,
    EXIT_REGRESSION_FAIL,
)
from evalsure_cli.main import app
from evalsure_sdk.exceptions import EvalSureAuthenticationError, EvalSureTimeoutError
from evalsure_sdk.models import (
    EvaluateRegressionResult,
    EvaluationResultsSubmitResult,
    EvaluationRun,
    EvaluationRunCreated,
    RegressionInfo,
)

runner = CliRunner()
NOW = datetime.now(timezone.utc)
ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "evalsure.yml"


def _write_config(path: Path, **overrides) -> Path:
    data = {
        "project_id": str(uuid4()),
        "experiment_id": str(uuid4()),
        "dataset_version_id": str(uuid4()),
        "metrics": ["exact_match", "string_similarity"],
    }
    data.update(overrides)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _write_results(path: Path, results: list | dict | None = None) -> Path:
    import json

    if results is None:
        results = {
            "results": [
                {
                    "test_case_id": str(uuid4()),
                    "actual_output": {"answer": "ok"},
                }
            ]
        }
    path.write_text(json.dumps(results), encoding="utf-8")
    return path


def _run_models(*, regression_status: str = "PASS") -> tuple:
    run_id = uuid4()
    created = EvaluationRunCreated(
        id=run_id, run_id=run_id, status="PENDING", experiment_id=uuid4()
    )
    run = EvaluationRun(
        id=run_id,
        run_id=run_id,
        project_id=uuid4(),
        experiment_id=created.experiment_id,
        dataset_version_id=uuid4(),
        status="COMPLETED",
        config_snapshot={},
        created_at=NOW,
        total_cases=1,
        completed_cases=1,
        failed_cases=0,
        pending_cases=0,
        baseline_run_id=uuid4(),
        regression_status=regression_status,
        metric_aggregates={
            "exact_match": {"average": 0.92, "minimum": 0.92, "maximum": 0.92, "count": 1},
            "string_similarity": {
                "average": 0.95,
                "minimum": 0.95,
                "maximum": 0.95,
                "count": 1,
            },
        },
    )
    submitted = EvaluationResultsSubmitResult(run=run, accepted=1)
    regression = EvaluateRegressionResult(
        run_id=run_id,
        evaluation_status="COMPLETED",
        regression=RegressionInfo(
            status=regression_status,
            baseline_run_id=run.baseline_run_id,
            regressed_case_count=3 if regression_status == "FAIL" else 0,
            violations=(
                [
                    {
                        "metric": "string_similarity",
                        "violated": True,
                        "reasons": ["aggregate drop exceeds max_allowed_drop"],
                    }
                ]
                if regression_status == "FAIL"
                else []
            ),
        ),
    )
    return created, submitted, run, regression


# ----- config -----


def test_load_valid_config(tmp_path: Path) -> None:
    path = _write_config(tmp_path / "evalsure.yml")
    cfg = load_ci_config(path)
    assert cfg.project_id
    assert cfg.metrics == ["exact_match", "string_similarity"]


def test_missing_config_fields(tmp_path: Path) -> None:
    path = tmp_path / "evalsure.yml"
    path.write_text("project_id: abc\n", encoding="utf-8")
    with pytest.raises(CiConfigError, match="Missing required"):
        load_ci_config(path)


def test_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "evalsure.yml"
    path.write_text("project_id: [\n  - broken\n", encoding="utf-8")
    with pytest.raises(CiConfigError, match="Invalid YAML"):
        load_ci_config(path)


def test_config_rejects_api_key(tmp_path: Path) -> None:
    path = tmp_path / "evalsure.yml"
    path.write_text(
        "project_id: a\nexperiment_id: b\ndataset_version_id: c\napi_key: secret\n",
        encoding="utf-8",
    )
    with pytest.raises(CiConfigError, match="secrets"):
        load_ci_config(path)


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(CiConfigError, match="not found"):
        load_ci_config(tmp_path / "missing.yml")


# ----- results -----


def test_load_results_and_normalize_string(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    tid = str(uuid4())
    _write_results(
        path,
        {"results": [{"test_case_id": tid, "actual_output": "plain text"}]},
    )
    results = load_results_file(path)
    assert results[0]["actual_output"] == {"text": "plain text"}


def test_missing_results_file(tmp_path: Path) -> None:
    with pytest.raises(CiResultsError, match="not found"):
        load_results_file(tmp_path / "nope.json")


def test_invalid_results_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(CiResultsError, match="Invalid JSON"):
        load_results_file(path)


# ----- run_ci exit codes -----


def test_ci_pass_exit_0(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    created, submitted, run, regression = _run_models(regression_status="PASS")
    client = MagicMock()
    client.runs.create.return_value = created
    client.runs.submit_results.return_value = submitted
    client.runs.evaluate_regression.return_value = regression
    client.runs.get.return_value = run
    # Ensure set_baseline is never called
    client.experiments.set_baseline = MagicMock()

    outcome = run_ci(client, config_path=config, results_path=results)
    assert outcome.exit_code == EXIT_PASS
    client.experiments.set_baseline.assert_not_called()
    assert client.runs.create.called
    assert client.runs.submit_results.called
    assert client.runs.evaluate_regression.called


def test_ci_regression_fail_exit_1(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    created, submitted, run, regression = _run_models(regression_status="FAIL")
    client = MagicMock()
    client.runs.create.return_value = created
    client.runs.submit_results.return_value = submitted
    client.runs.evaluate_regression.return_value = regression
    client.runs.get.return_value = run

    outcome = run_ci(client, config_path=config, results_path=results)
    assert outcome.exit_code == EXIT_REGRESSION_FAIL
    assert outcome.regression_status == "FAIL"


def test_ci_config_error_exit_2(tmp_path: Path) -> None:
    client = MagicMock()
    outcome = run_ci(
        client,
        config_path=tmp_path / "missing.yml",
        results_path=tmp_path / "also-missing.json",
    )
    assert outcome.exit_code == EXIT_CONFIG
    client.runs.create.assert_not_called()


def test_ci_api_error_exit_3(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    client = MagicMock()
    client.runs.create.side_effect = EvalSureAuthenticationError(
        "Invalid API key", status_code=401
    )
    outcome = run_ci(client, config_path=config, results_path=results)
    assert outcome.exit_code == EXIT_API


def test_ci_timeout_exit_3(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    client = MagicMock()
    client.runs.create.side_effect = EvalSureTimeoutError("timed out")
    outcome = run_ci(client, config_path=config, results_path=results)
    assert outcome.exit_code == EXIT_API


def test_cli_ci_run_exit_codes(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    created, submitted, run, regression = _run_models(regression_status="PASS")
    mock_client = MagicMock()
    mock_client.runs.create.return_value = created
    mock_client.runs.submit_results.return_value = submitted
    mock_client.runs.evaluate_regression.return_value = regression
    mock_client.runs.get.return_value = run

    with patch("evalsure_cli.main._client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--api-key",
                "evs_secret_ci_key",
                "ci",
                "run",
                "--config",
                str(config),
                "--results",
                str(results),
            ],
        )
    assert result.exit_code == EXIT_PASS
    assert "EVALSURE Evaluation" in result.stdout
    assert "PASS" in result.stdout
    assert "evs_secret_ci_key" not in result.stdout


def test_cli_ci_run_fail_exit_1(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "evalsure.yml")
    results = _write_results(tmp_path / "results.json")
    created, submitted, run, regression = _run_models(regression_status="FAIL")
    mock_client = MagicMock()
    mock_client.runs.create.return_value = created
    mock_client.runs.submit_results.return_value = submitted
    mock_client.runs.evaluate_regression.return_value = regression
    mock_client.runs.get.return_value = run

    with patch("evalsure_cli.main._client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["ci", "run", "--config", str(config), "--results", str(results)],
        )
    assert result.exit_code == EXIT_REGRESSION_FAIL
    assert "FAIL" in result.stdout
    assert "Regressed cases" in result.stdout


def test_github_metadata_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/app")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/42/merge")
    monkeypatch.setenv("GITHUB_RUN_ID", "999")
    meta = collect_github_metadata()
    assert meta["repository"] == "acme/app"
    assert meta["sha"] == "abc123"
    assert meta["pull_request_number"] == "42"
    assert meta["workflow_run_id"] == "999"
    assert "api_key" not in meta


def test_workflow_yaml_valid() -> None:
    assert WORKFLOW.exists()
    raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert raw["name"] == "EVALSURE"
    assert "pull_request" in raw["on"]
    assert "push" in raw["on"]
    job = raw["jobs"]["evalsure"]
    assert job["runs-on"] == "ubuntu-latest"
    steps = job["steps"]
    texts = []
    for step in steps:
        texts.append(step.get("name", ""))
        texts.append(step.get("run", "") or "")
        texts.append(str(step.get("uses", "") or ""))
        texts.append(str(step.get("env", {}) or ""))
    blob = "\n".join(texts)
    assert "actions/setup-python@v5" in blob
    assert "secrets.EVALSURE_API_URL" in blob
    assert "secrets.EVALSURE_API_KEY" in blob
    assert "evalsure ci run" in blob
    assert "evalsure.yml" in blob
    # No hardcoded secrets
    assert "evs_" not in blob
    assert "sk-" not in blob


def test_ci_help() -> None:
    result = runner.invoke(app, ["ci", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
