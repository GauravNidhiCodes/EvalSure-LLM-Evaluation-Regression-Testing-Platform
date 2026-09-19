"""Resource namespaces for EvalSureClient."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from evalsure_sdk._http import HttpTransport
from evalsure_sdk.models import (
    CaseResult,
    CaseTraces,
    Dataset,
    DatasetVersion,
    EvaluateRegressionResult,
    EvaluationResultsSubmitResult,
    EvaluationRun,
    EvaluationRunCreated,
    Experiment,
    Project,
    RegressionPolicy,
    RunTraces,
    TestCase,
)


def _id(value: UUID | str) -> str:
    return str(value)


def _page_items(data: Any) -> list[Any]:
    """Normalize paginated `{items: [...]}` or legacy list responses."""
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
        return list(items) if isinstance(items, list) else []
    if isinstance(data, list):
        return data
    return []


class ProjectsAPI:
    def __init__(self, transport: HttpTransport) -> None:
        self._http = transport

    def list(self) -> list[Project]:
        """List projects owned by the authenticated user (requires JWT)."""
        data = self._http.request("GET", "/projects?page_size=200", require_jwt=True)
        return [Project.model_validate(item) for item in _page_items(data)]

    def create(self, *, name: str, description: str | None = None) -> Project:
        """Create a project (requires JWT)."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        data = self._http.request("POST", "/projects", json=body, require_jwt=True)
        return Project.model_validate(data)

    def get(self, project_id: UUID | str) -> Project:
        data = self._http.request("GET", f"/projects/{_id(project_id)}")
        return Project.model_validate(data)


class DatasetsAPI:
    def __init__(self, transport: HttpTransport) -> None:
        self._http = transport

    def create(
        self,
        project_id: UUID | str,
        *,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        body: dict[str, Any] = {"name": name, "metadata": metadata or {}}
        if description is not None:
            body["description"] = description
        data = self._http.request("POST", f"/projects/{_id(project_id)}/datasets", json=body)
        return Dataset.model_validate(data)

    def list(self, project_id: UUID | str) -> list[Dataset]:
        data = self._http.request("GET", f"/projects/{_id(project_id)}/datasets?page_size=200")
        return [Dataset.model_validate(item) for item in _page_items(data)]

    def get(self, dataset_id: UUID | str) -> Dataset:
        data = self._http.request("GET", f"/datasets/{_id(dataset_id)}")
        return Dataset.model_validate(data)

    def create_version(
        self,
        dataset_id: UUID | str,
        *,
        test_cases: list[dict[str, Any]],
    ) -> DatasetVersion:
        """Create an immutable dataset version.

        Each test case must follow the API contract:
        ``external_id``, ``input`` (object), optional ``expected`` (object),
        ``metadata``, ``tags``.
        """
        data = self._http.request(
            "POST",
            f"/datasets/{_id(dataset_id)}/versions",
            json={"test_cases": test_cases},
        )
        return DatasetVersion.model_validate(data)

    def list_versions(self, dataset_id: UUID | str) -> list[DatasetVersion]:
        data = self._http.request("GET", f"/datasets/{_id(dataset_id)}/versions?page_size=200")
        return [DatasetVersion.model_validate(item) for item in _page_items(data)]

    def get_version(self, version_id: UUID | str) -> DatasetVersion:
        data = self._http.request("GET", f"/dataset-versions/{_id(version_id)}")
        return DatasetVersion.model_validate(data)

    def list_test_cases(self, version_id: UUID | str) -> list[TestCase]:
        data = self._http.request(
            "GET",
            f"/dataset-versions/{_id(version_id)}/test-cases?page_size=200",
        )
        return [TestCase.model_validate(item) for item in _page_items(data)]


class RunsAPI:
    def __init__(self, transport: HttpTransport) -> None:
        self._http = transport

    def create(
        self,
        project_id: UUID | str,
        *,
        dataset_version_id: UUID | str,
        experiment_id: UUID | str | None = None,
        metrics: list[str] | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> EvaluationRunCreated:
        body: dict[str, Any] = {
            "dataset_version_id": _id(dataset_version_id),
            "metrics": metrics or [],
            "config_snapshot": config_snapshot or {},
        }
        if experiment_id is not None:
            body["experiment_id"] = _id(experiment_id)
        data = self._http.request("POST", f"/projects/{_id(project_id)}/runs", json=body)
        return EvaluationRunCreated.model_validate(data)

    def get(self, run_id: UUID | str) -> EvaluationRun:
        data = self._http.request("GET", f"/runs/{_id(run_id)}")
        return EvaluationRun.model_validate(data)

    def submit_results(
        self,
        run_id: UUID | str,
        *,
        results: list[dict[str, Any]],
    ) -> EvaluationResultsSubmitResult:
        data = self._http.request(
            "POST",
            f"/runs/{_id(run_id)}/results",
            json={"results": results},
        )
        return EvaluationResultsSubmitResult.model_validate(data)

    def list_results(self, run_id: UUID | str) -> list[CaseResult]:
        data = self._http.request("GET", f"/runs/{_id(run_id)}/results?page_size=200")
        return [CaseResult.model_validate(item) for item in _page_items(data)]

    def evaluate_regression(self, run_id: UUID | str) -> EvaluateRegressionResult:
        data = self._http.request("POST", f"/runs/{_id(run_id)}/evaluate-regression")
        return EvaluateRegressionResult.model_validate(data)


class ExperimentsAPI:
    def __init__(self, transport: HttpTransport) -> None:
        self._http = transport

    def create(
        self,
        project_id: UUID | str,
        *,
        name: str,
        description: str | None = None,
    ) -> Experiment:
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        data = self._http.request("POST", f"/projects/{_id(project_id)}/experiments", json=body)
        return Experiment.model_validate(data)

    def list(self, project_id: UUID | str) -> list[Experiment]:
        data = self._http.request("GET", f"/projects/{_id(project_id)}/experiments?page_size=200")
        return [Experiment.model_validate(item) for item in _page_items(data)]

    def get(self, experiment_id: UUID | str) -> Experiment:
        data = self._http.request("GET", f"/experiments/{_id(experiment_id)}")
        return Experiment.model_validate(data)

    def list_runs(self, experiment_id: UUID | str) -> list[EvaluationRun]:
        data = self._http.request("GET", f"/experiments/{_id(experiment_id)}/runs?page_size=200")
        return [EvaluationRun.model_validate(item) for item in _page_items(data)]

    def set_baseline(self, experiment_id: UUID | str, run_id: UUID | str) -> Experiment:
        data = self._http.request(
            "POST",
            f"/experiments/{_id(experiment_id)}/baseline/{_id(run_id)}",
        )
        return Experiment.model_validate(data)

    def list_regression_policies(self, experiment_id: UUID | str) -> list[RegressionPolicy]:
        data = self._http.request(
            "GET",
            f"/experiments/{_id(experiment_id)}/regression-policies",
        )
        return [RegressionPolicy.model_validate(item) for item in data]

    def upsert_regression_policy(
        self,
        experiment_id: UUID | str,
        *,
        metric_name: str,
        max_allowed_drop: float,
        min_aggregate_score: float | None = None,
        max_regressed_cases: int | None = None,
    ) -> RegressionPolicy:
        body: dict[str, Any] = {
            "metric_name": metric_name,
            "max_allowed_drop": max_allowed_drop,
        }
        if min_aggregate_score is not None:
            body["min_aggregate_score"] = min_aggregate_score
        if max_regressed_cases is not None:
            body["max_regressed_cases"] = max_regressed_cases
        data = self._http.request(
            "POST",
            f"/experiments/{_id(experiment_id)}/regression-policies",
            json=body,
        )
        return RegressionPolicy.model_validate(data)


class TracesAPI:
    def __init__(self, transport: HttpTransport) -> None:
        self._http = transport

    def get_run_traces(self, run_id: UUID | str) -> RunTraces:
        data = self._http.request("GET", f"/runs/{_id(run_id)}/traces")
        return RunTraces.model_validate(data)

    def get_case_traces(self, run_id: UUID | str, case_result_id: UUID | str) -> CaseTraces:
        data = self._http.request(
            "GET",
            f"/runs/{_id(run_id)}/cases/{_id(case_result_id)}/traces",
        )
        return CaseTraces.model_validate(data)
