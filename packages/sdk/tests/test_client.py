"""SDK unit tests — mocked HTTP only (no real network)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
import respx

from evalsure_sdk import EvalSureClient
from evalsure_sdk.exceptions import (
    EvalSureAuthenticationError,
    EvalSureNotFoundError,
    EvalSureTimeoutError,
    EvalSureValidationError,
)

BASE = "http://test.local:8000"
API = f"{BASE}/api/v1"
NOW = datetime.now(timezone.utc).isoformat()


def _client(**kwargs) -> EvalSureClient:
    defaults = {"base_url": BASE, "api_key": "evs_test_secret_key_do_not_leak", "timeout": 5.0}
    defaults.update(kwargs)
    return EvalSureClient(**defaults)


@respx.mock
def test_auth_header_uses_x_api_key() -> None:
    project_id = str(uuid4())
    route = respx.get(f"{API}/projects/{project_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": project_id,
                "name": "Demo",
                "description": None,
                "owner_id": str(uuid4()),
                "created_at": NOW,
            },
        )
    )
    client = _client()
    client.projects.get(project_id)
    assert route.called
    assert route.calls[0].request.headers["X-API-Key"] == "evs_test_secret_key_do_not_leak"
    assert "Authorization" not in route.calls[0].request.headers or not route.calls[
        0
    ].request.headers.get("Authorization", "").endswith("evs_test_secret_key_do_not_leak")


@respx.mock
def test_projects_list_requires_jwt() -> None:
    client = _client(api_key="evs_x")
    with pytest.raises(EvalSureAuthenticationError, match="JWT"):
        client.projects.list()

    respx.get(f"{API}/projects").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "name": "A",
                    "description": None,
                    "owner_id": str(uuid4()),
                    "created_at": NOW,
                }
            ],
        )
    )
    jwt_client = _client(api_key=None, access_token="jwt-token")
    projects = jwt_client.projects.list()
    assert len(projects) == 1
    assert respx.calls.last.request.headers["Authorization"] == "Bearer jwt-token"


@respx.mock
def test_dataset_operations() -> None:
    project_id = str(uuid4())
    dataset_id = str(uuid4())
    version_id = str(uuid4())

    respx.post(f"{API}/projects/{project_id}/datasets").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": dataset_id,
                "project_id": project_id,
                "name": "customer-support",
                "description": None,
                "metadata": {},
                "created_at": NOW,
            },
        )
    )
    respx.post(f"{API}/datasets/{dataset_id}/versions").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": version_id,
                "dataset_id": dataset_id,
                "version": 1,
                "content_hash": "abc",
                "created_at": NOW,
                "test_case_count": 1,
            },
        )
    )
    respx.get(f"{API}/datasets/{dataset_id}/versions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": version_id,
                    "dataset_id": dataset_id,
                    "version": 1,
                    "content_hash": "abc",
                    "created_at": NOW,
                    "test_case_count": 1,
                }
            ],
        )
    )
    respx.get(f"{API}/dataset-versions/{version_id}/test-cases").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "external_id": "case-1",
                    "input": {"q": "refund?"},
                    "expected": {"a": "30 days"},
                    "metadata": {},
                    "tags": [],
                }
            ],
        )
    )

    client = _client()
    ds = client.datasets.create(project_id, name="customer-support")
    assert ds.name == "customer-support"
    ver = client.datasets.create_version(
        dataset_id,
        test_cases=[
            {
                "external_id": "case-1",
                "input": {"q": "What is your refund policy?"},
                "expected": {"a": "Refunds are available within 30 days."},
            }
        ],
    )
    assert ver.version == 1
    assert len(client.datasets.list_versions(dataset_id)) == 1
    assert client.datasets.list_test_cases(version_id)[0].external_id == "case-1"


@respx.mock
def test_run_create_submit_regression() -> None:
    project_id = str(uuid4())
    run_id = str(uuid4())
    version_id = str(uuid4())
    case_id = str(uuid4())

    respx.post(f"{API}/projects/{project_id}/runs").mock(
        return_value=httpx.Response(
            201,
            json={"id": run_id, "run_id": run_id, "status": "PENDING", "experiment_id": None},
        )
    )
    respx.post(f"{API}/runs/{run_id}/results").mock(
        return_value=httpx.Response(
            200,
            json={
                "accepted": 1,
                "run": {
                    "id": run_id,
                    "run_id": run_id,
                    "project_id": project_id,
                    "experiment_id": None,
                    "is_baseline": False,
                    "dataset_version_id": version_id,
                    "dataset_version": None,
                    "status": "COMPLETED",
                    "config_snapshot": {"metrics": ["exact_match"]},
                    "error_message": None,
                    "started_at": NOW,
                    "finished_at": NOW,
                    "created_at": NOW,
                    "total_cases": 1,
                    "completed_cases": 1,
                    "failed_cases": 0,
                    "pending_cases": 0,
                    "regression_status": "NOT_EVALUATED",
                    "baseline_run_id": None,
                    "regression": None,
                    "metric_aggregates": {},
                },
            },
        )
    )
    respx.post(f"{API}/runs/{run_id}/evaluate-regression").mock(
        return_value=httpx.Response(
            200,
            json={
                "run_id": run_id,
                "evaluation_status": "COMPLETED",
                "regression": {
                    "status": "NOT_EVALUATED",
                    "baseline_run_id": None,
                    "regressed_case_count": 0,
                    "aggregate": {},
                    "regressed_cases": [],
                    "violations": [],
                    "incomparable_cases": [],
                    "notes": ["No baseline"],
                },
            },
        )
    )

    client = _client()
    created = client.runs.create(
        project_id,
        dataset_version_id=version_id,
        metrics=["exact_match", "string_similarity", "llm_judge"],
    )
    assert created.status == "PENDING"
    submitted = client.runs.submit_results(
        run_id,
        results=[{"test_case_id": case_id, "actual_output": {"answer": "ok"}}],
    )
    assert submitted.accepted == 1
    assert submitted.run.status == "COMPLETED"
    reg = client.runs.evaluate_regression(run_id)
    assert reg.regression.status == "NOT_EVALUATED"


@respx.mock
def test_experiments_baseline_and_policies() -> None:
    project_id = str(uuid4())
    exp_id = str(uuid4())
    run_id = str(uuid4())
    policy_id = str(uuid4())

    respx.post(f"{API}/projects/{project_id}/experiments").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": exp_id,
                "project_id": project_id,
                "name": "RAG",
                "description": None,
                "baseline_run_id": None,
                "created_at": NOW,
            },
        )
    )
    respx.post(f"{API}/experiments/{exp_id}/baseline/{run_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": exp_id,
                "project_id": project_id,
                "name": "RAG",
                "description": None,
                "baseline_run_id": run_id,
                "created_at": NOW,
            },
        )
    )
    respx.post(f"{API}/experiments/{exp_id}/regression-policies").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": policy_id,
                "experiment_id": exp_id,
                "metric_name": "string_similarity",
                "max_allowed_drop": 0.05,
                "min_aggregate_score": 0.8,
                "max_regressed_cases": 2,
                "created_at": NOW,
            },
        )
    )
    respx.get(f"{API}/experiments/{exp_id}/regression-policies").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": policy_id,
                    "experiment_id": exp_id,
                    "metric_name": "string_similarity",
                    "max_allowed_drop": 0.05,
                    "min_aggregate_score": 0.8,
                    "max_regressed_cases": 2,
                    "created_at": NOW,
                }
            ],
        )
    )

    client = _client()
    exp = client.experiments.create(project_id, name="RAG")
    assert exp.name == "RAG"
    updated = client.experiments.set_baseline(exp_id, run_id)
    assert str(updated.baseline_run_id) == run_id
    policy = client.experiments.upsert_regression_policy(
        exp_id,
        metric_name="string_similarity",
        max_allowed_drop=0.05,
        min_aggregate_score=0.8,
        max_regressed_cases=2,
    )
    assert policy.metric_name == "string_similarity"
    assert len(client.experiments.list_regression_policies(exp_id)) == 1


@respx.mock
def test_trace_retrieval() -> None:
    run_id = str(uuid4())
    case_id = str(uuid4())
    event_id = str(uuid4())
    respx.get(f"{API}/runs/{run_id}/traces").mock(
        return_value=httpx.Response(
            200,
            json={
                "run_id": run_id,
                "events": [
                    {
                        "id": event_id,
                        "run_id": run_id,
                        "case_result_id": None,
                        "event_type": "run_started",
                        "timestamp": NOW,
                        "data": {},
                        "created_at": NOW,
                    }
                ],
            },
        )
    )
    respx.get(f"{API}/runs/{run_id}/cases/{case_id}/traces").mock(
        return_value=httpx.Response(
            200,
            json={"run_id": run_id, "case_result_id": case_id, "events": []},
        )
    )
    client = _client()
    traces = client.traces.get_run_traces(run_id)
    assert traces.events[0].event_type == "run_started"
    assert client.traces.get_case_traces(run_id, case_id).case_result_id


@respx.mock
def test_http_error_mapping() -> None:
    client = _client()
    missing_run = str(uuid4())
    respx.get(f"{API}/runs/{missing_run}").mock(
        return_value=httpx.Response(404, json={"detail": "Evaluation run not found"})
    )
    with pytest.raises(EvalSureNotFoundError) as nf:
        client.runs.get(missing_run)
    assert nf.value.status_code == 404
    assert "evs_test_secret_key_do_not_leak" not in str(nf.value)

    project_id = str(uuid4())
    respx.post(f"{API}/projects/{project_id}/runs").mock(
        return_value=httpx.Response(422, json={"detail": [{"msg": "Invalid metric"}]})
    )
    with pytest.raises(EvalSureValidationError):
        client.runs.create(project_id, dataset_version_id=str(uuid4()), metrics=["nope"])

    project_id2 = str(uuid4())
    respx.get(f"{API}/projects/{project_id2}").mock(
        return_value=httpx.Response(401, json={"detail": "Invalid API key"})
    )
    with pytest.raises(EvalSureAuthenticationError):
        client.projects.get(project_id2)


@respx.mock
def test_timeout_and_connection() -> None:
    client = _client(timeout=0.01)
    respx.get(url__regex=r".*/projects/.*").mock(side_effect=httpx.TimeoutException("timeout"))
    with pytest.raises(EvalSureTimeoutError, match="timed out"):
        client.projects.get(str(uuid4()))

    respx.get(url__regex=r".*/projects/.*").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(EvalSureTimeoutError, match="connect"):
        client.projects.get(str(uuid4()))


@respx.mock
def test_api_key_redacted_from_error_detail() -> None:
    secret = "evs_super_secret_should_not_appear"
    client = _client(api_key=secret)
    respx.get(url__regex=r".*/runs/.*").mock(
        return_value=httpx.Response(400, json={"detail": f"bad key {secret}"})
    )
    with pytest.raises(EvalSureValidationError) as exc:
        client.runs.get(str(uuid4()))
    assert secret not in str(exc.value)
    assert "***" in str(exc.value)


def test_client_repr_hides_key() -> None:
    client = _client()
    text = repr(client)
    assert "evs_test_secret_key_do_not_leak" not in text
    assert "api_key" in text
