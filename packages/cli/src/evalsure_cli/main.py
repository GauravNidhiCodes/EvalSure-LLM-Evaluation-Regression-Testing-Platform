"""EVALSURE Typer CLI — talks to the REST API via evalsure-sdk only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer

from evalsure_cli.config import load_config
from evalsure_cli.output import (
    exit_api_error,
    model_dump,
    print_json,
    print_kv,
    print_table,
)
from evalsure_sdk.exceptions import EvalSureError

app = typer.Typer(
    name="evalsure",
    help="EVALSURE CLI — evaluation & regression testing via the REST API.",
    no_args_is_help=True,
    add_completion=False,
)

projects_app = typer.Typer(help="Project commands", no_args_is_help=True)
datasets_app = typer.Typer(help="Dataset commands", no_args_is_help=True)
runs_app = typer.Typer(help="Evaluation run commands", no_args_is_help=True)
experiments_app = typer.Typer(help="Experiment commands", no_args_is_help=True)
traces_app = typer.Typer(help="Trace commands", no_args_is_help=True)

app.add_typer(projects_app, name="projects")
app.add_typer(datasets_app, name="datasets")
app.add_typer(runs_app, name="runs")
app.add_typer(experiments_app, name="experiments")
app.add_typer(traces_app, name="traces")


@app.callback()
def _global_opts(
    ctx: typer.Context,
    api_url: Optional[str] = typer.Option(
        None, "--api-url", envvar="EVALSURE_API_URL", help="EVALSURE API base URL"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", envvar="EVALSURE_API_KEY", help="Project API key (never printed)"
    ),
    access_token: Optional[str] = typer.Option(
        None,
        "--access-token",
        envvar="EVALSURE_ACCESS_TOKEN",
        help="JWT for project create/list (never printed)",
    ),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="HTTP timeout seconds"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["api_key"] = api_key
    ctx.obj["access_token"] = access_token
    ctx.obj["timeout"] = timeout


def _client(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
    timeout: Optional[float] = None,
):
    return load_config(
        api_url=api_url,
        api_key=api_key,
        access_token=access_token,
        timeout=timeout,
    ).client()


def _from_ctx(ctx: typer.Context):
    return _client(
        api_url=ctx.obj.get("api_url"),
        api_key=ctx.obj.get("api_key"),
        access_token=ctx.obj.get("access_token"),
        timeout=ctx.obj.get("timeout"),
    )


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(1) from None
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: invalid JSON in {path}: {exc}", err=True)
        raise typer.Exit(1) from None


# ----- projects -----


@projects_app.command("list")
def projects_list(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
) -> None:
    """List projects (requires EVALSURE_ACCESS_TOKEN / JWT)."""
    try:
        items = _from_ctx(ctx).projects.list()
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(items))
        return
    print_table(
        "Projects",
        ["id", "name", "description"],
        [[p.id, p.name, p.description or ""] for p in items],
    )


@projects_app.command("create")
def projects_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Project name"),
    description: Optional[str] = typer.Option(None, "--description"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Create a project (requires JWT)."""
    try:
        project = _from_ctx(ctx).projects.create(name=name, description=description)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(project))
        return
    print_kv("Project created", {"id": project.id, "name": project.name})


@projects_app.command("get")
def projects_get(
    ctx: typer.Context,
    project_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        project = _from_ctx(ctx).projects.get(project_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(project))
        return
    print_kv(
        "Project",
        {"id": project.id, "name": project.name, "description": project.description},
    )


# ----- datasets -----


@datasets_app.command("list")
def datasets_list(
    ctx: typer.Context,
    project_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        items = _from_ctx(ctx).datasets.list(project_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(items))
        return
    print_table(
        "Datasets",
        ["id", "name", "description"],
        [[d.id, d.name, d.description or ""] for d in items],
    )


@datasets_app.command("get")
def datasets_get(
    ctx: typer.Context,
    dataset_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        dataset = _from_ctx(ctx).datasets.get(dataset_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(dataset))
        return
    print_kv(
        "Dataset",
        {
            "id": dataset.id,
            "project_id": dataset.project_id,
            "name": dataset.name,
        },
    )


@datasets_app.command("create")
def datasets_create(
    ctx: typer.Context,
    project_id: str,
    name: str = typer.Option(..., "--name"),
    description: Optional[str] = typer.Option(None, "--description"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        dataset = _from_ctx(ctx).datasets.create(
            project_id, name=name, description=description
        )
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(dataset))
        return
    print_kv("Dataset created", {"id": dataset.id, "name": dataset.name})


@datasets_app.command("versions")
def datasets_versions(
    ctx: typer.Context,
    dataset_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        items = _from_ctx(ctx).datasets.list_versions(dataset_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(items))
        return
    print_table(
        "Dataset versions",
        ["id", "version", "content_hash", "test_case_count"],
        [[v.id, v.version, v.content_hash, v.test_case_count] for v in items],
    )


@datasets_app.command("create-version")
def datasets_create_version(
    ctx: typer.Context,
    dataset_id: str,
    file: Path = typer.Option(..., "--file", "-f", exists=True, readable=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Import a dataset version from a JSON file.

    File formats accepted:
      - ``{"test_cases": [...]}``
      - a bare JSON array of test cases
    """
    payload = _load_json_file(file)
    if isinstance(payload, dict) and "test_cases" in payload:
        test_cases = payload["test_cases"]
    elif isinstance(payload, list):
        test_cases = payload
    else:
        typer.echo(
            "Error: JSON must be a list of test cases or an object with test_cases",
            err=True,
        )
        raise typer.Exit(1)
    if not isinstance(test_cases, list) or not test_cases:
        typer.echo("Error: test_cases must be a non-empty list", err=True)
        raise typer.Exit(1)
    try:
        version = _from_ctx(ctx).datasets.create_version(dataset_id, test_cases=test_cases)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(version))
        return
    print_kv(
        "Dataset version created",
        {
            "id": version.id,
            "version": version.version,
            "content_hash": version.content_hash,
            "test_case_count": version.test_case_count,
        },
    )


# ----- runs -----


@runs_app.command("create")
def runs_create(
    ctx: typer.Context,
    project_id: str,
    dataset_version_id: str,
    experiment_id: Optional[str] = typer.Option(None, "--experiment-id"),
    metrics: Optional[str] = typer.Option(
        None, "--metrics", help="Comma-separated metric names"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    metric_list = [m.strip() for m in (metrics or "").split(",") if m.strip()]
    try:
        run = _from_ctx(ctx).runs.create(
            project_id,
            dataset_version_id=dataset_version_id,
            experiment_id=experiment_id,
            metrics=metric_list,
        )
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(run))
        return
    print_kv("Run created", {"id": run.id, "status": run.status, "experiment_id": run.experiment_id})


@runs_app.command("get")
def runs_get(
    ctx: typer.Context,
    run_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        run = _from_ctx(ctx).runs.get(run_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(run))
        return
    print_kv(
        "Evaluation run",
        {
            "id": run.id,
            "status": run.status,
            "regression_status": run.regression_status,
            "completed_cases": run.completed_cases,
            "failed_cases": run.failed_cases,
            "pending_cases": run.pending_cases,
            "total_cases": run.total_cases,
        },
    )


@runs_app.command("results")
def runs_results(
    ctx: typer.Context,
    run_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        items = _from_ctx(ctx).runs.list_results(run_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(items))
        return
    print_table(
        "Case results",
        ["id", "external_id", "status", "is_regression"],
        [[r.id, r.external_id or "", r.status, r.is_regression] for r in items],
    )


@runs_app.command("submit-results")
def runs_submit_results(
    ctx: typer.Context,
    run_id: str,
    file: Path = typer.Option(..., "--file", "-f", exists=True, readable=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Submit evaluation outputs from a JSON file.

    File formats accepted:
      - ``{"results": [...]}``
      - a bare JSON array of result objects
    """
    payload = _load_json_file(file)
    if isinstance(payload, dict) and "results" in payload:
        results = payload["results"]
    elif isinstance(payload, list):
        results = payload
    else:
        typer.echo(
            "Error: JSON must be a list of results or an object with results",
            err=True,
        )
        raise typer.Exit(1)
    if not isinstance(results, list) or not results:
        typer.echo("Error: results must be a non-empty list", err=True)
        raise typer.Exit(1)
    try:
        out = _from_ctx(ctx).runs.submit_results(run_id, results=results)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(out))
        return
    print_kv(
        "Results submitted",
        {
            "accepted": out.accepted,
            "run_status": out.run.status,
            "completed_cases": out.run.completed_cases,
            "failed_cases": out.run.failed_cases,
        },
    )


@runs_app.command("regression")
def runs_regression(
    ctx: typer.Context,
    run_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = _from_ctx(ctx).runs.evaluate_regression(run_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(result))
        return
    print_kv(
        "Regression evaluation",
        {
            "run_id": result.run_id,
            "evaluation_status": result.evaluation_status,
            "regression_status": result.regression.status,
            "regressed_case_count": result.regression.regressed_case_count,
        },
    )


# ----- experiments -----


@experiments_app.command("list")
def experiments_list(
    ctx: typer.Context,
    project_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        items = _from_ctx(ctx).experiments.list(project_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(items))
        return
    print_table(
        "Experiments",
        ["id", "name", "baseline_run_id"],
        [[e.id, e.name, e.baseline_run_id or ""] for e in items],
    )


@experiments_app.command("get")
def experiments_get(
    ctx: typer.Context,
    experiment_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        exp = _from_ctx(ctx).experiments.get(experiment_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(exp))
        return
    print_kv(
        "Experiment",
        {
            "id": exp.id,
            "name": exp.name,
            "baseline_run_id": exp.baseline_run_id,
        },
    )


@experiments_app.command("create")
def experiments_create(
    ctx: typer.Context,
    project_id: str,
    name: str = typer.Option(..., "--name"),
    description: Optional[str] = typer.Option(None, "--description"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        exp = _from_ctx(ctx).experiments.create(project_id, name=name, description=description)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(exp))
        return
    print_kv("Experiment created", {"id": exp.id, "name": exp.name})


@experiments_app.command("baseline")
def experiments_baseline(
    ctx: typer.Context,
    experiment_id: str,
    run_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        exp = _from_ctx(ctx).experiments.set_baseline(experiment_id, run_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(exp))
        return
    print_kv(
        "Baseline set",
        {"experiment_id": exp.id, "baseline_run_id": exp.baseline_run_id},
    )


# ----- traces -----


@traces_app.command("run")
def traces_run(
    ctx: typer.Context,
    run_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        traces = _from_ctx(ctx).traces.get_run_traces(run_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(traces))
        return
    print_table(
        f"Run traces ({run_id})",
        ["event_type", "timestamp", "case_result_id"],
        [[e.event_type, e.timestamp, e.case_result_id or ""] for e in traces.events],
    )


@traces_app.command("case")
def traces_case(
    ctx: typer.Context,
    run_id: str,
    case_result_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        traces = _from_ctx(ctx).traces.get_case_traces(run_id, case_result_id)
    except EvalSureError as exc:
        exit_api_error(exc)
    if as_json:
        print_json(model_dump(traces))
        return
    print_table(
        f"Case traces ({case_result_id})",
        ["event_type", "timestamp"],
        [[e.event_type, e.timestamp] for e in traces.events],
    )


if __name__ == "__main__":
    app()
