from uuid import uuid4

import pytest
from httpx import AsyncClient

SAMPLE_CASES = [
    {
        "external_id": "case-a",
        "input": {"question": "Q1"},
        "expected": {"answer": "A1"},
        "metadata": {},
        "tags": ["a"],
    },
    {
        "external_id": "case-b",
        "input": {"question": "Q2"},
        "expected": {"answer": "A2"},
        "metadata": {},
        "tags": ["b"],
    },
]


async def _setup(client: AsyncClient) -> dict:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": f"runs-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Runs"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Eval set"},
    )
    dataset_id = dataset.json()["id"]

    version = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    assert version.status_code == 201
    version_id = version.json()["id"]

    cases = await client.get(
        f"/api/v1/dataset-versions/{version_id}/test-cases",
        headers=headers,
    )
    assert cases.status_code == 200
    case_ids = {c["external_id"]: c["id"] for c in cases.json()["items"]}

    return {
        "headers": headers,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "version_id": version_id,
        "case_ids": case_ids,
    }


@pytest.mark.asyncio
async def test_create_evaluation_run(client: AsyncClient) -> None:
    ctx = await _setup(client)
    config = {"model": "example-model", "prompt_version": "v3", "temperature": 0.2}
    response = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"], "config_snapshot": config},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["id"] == body["run_id"]

    detail = await client.get(f"/api/v1/runs/{body['id']}", headers=ctx["headers"])
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "PENDING"
    assert data["total_cases"] == 2
    assert data["completed_cases"] == 0
    assert data["pending_cases"] == 2
    assert data["failed_cases"] == 0
    assert data["config_snapshot"]["model"] == "example-model"
    assert data["config_snapshot"]["prompt_version"] == "v3"
    assert data["config_snapshot"]["temperature"] == 0.2
    assert data["config_snapshot"]["dataset_version_id"] == ctx["version_id"]
    assert data["config_snapshot"]["metrics"] == []
    assert data["dataset_version"]["id"] == ctx["version_id"]
    assert data["experiment_id"] is None
    assert data["is_baseline"] is False


@pytest.mark.asyncio
async def test_invalid_dataset_version(client: AsyncClient) -> None:
    ctx = await _setup(client)
    response = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": str(uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_results_and_complete(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "dataset_version_id": ctx["version_id"],
            "config_snapshot": {"model": "m1", "retrieval": {"top_k": 5}},
        },
    )
    run_id = created.json()["id"]
    frozen_model = "m1"

    partial = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {
                    "test_case_id": ctx["case_ids"]["case-a"],
                    "actual_output": {"answer": "A1"},
                }
            ]
        },
    )
    assert partial.status_code == 200
    run = partial.json()["run"]
    assert run["status"] == "RUNNING"
    assert run["completed_cases"] == 1
    assert run["pending_cases"] == 1
    assert run["config_snapshot"]["model"] == frozen_model
    assert run["config_snapshot"]["retrieval"] == {"top_k": 5}
    assert run["config_snapshot"]["dataset_version_id"] == ctx["version_id"]

    remaining = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {
                    "test_case_id": ctx["case_ids"]["case-b"],
                    "actual_output": {"answer": "A2"},
                }
            ]
        },
    )
    assert remaining.status_code == 200
    done = remaining.json()["run"]
    assert done["status"] == "COMPLETED"
    assert done["completed_cases"] == 2
    assert done["pending_cases"] == 0
    assert done["finished_at"] is not None
    assert done["config_snapshot"]["model"] == frozen_model
    assert done["config_snapshot"]["dataset_version_id"] == ctx["version_id"]

    listed = await client.get(f"/api/v1/runs/{run_id}/results", headers=ctx["headers"])
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2


@pytest.mark.asyncio
async def test_incomplete_run_cannot_complete(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "only one"}}
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["run"]["status"] == "RUNNING"
    assert response.json()["run"]["pending_cases"] == 1


@pytest.mark.asyncio
async def test_reject_unknown_test_case(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={"results": [{"test_case_id": str(uuid4()), "actual_output": {"answer": "x"}}]},
    )
    assert response.status_code == 400
    detail = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    assert detail.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_reject_test_case_from_another_dataset(client: AsyncClient) -> None:
    ctx = await _setup(client)
    other_ds = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/datasets",
        headers=ctx["headers"],
        json={"name": "Other"},
    )
    other_ver = await client.post(
        f"/api/v1/datasets/{other_ds.json()['id']}/versions",
        headers=ctx["headers"],
        json={"test_cases": SAMPLE_CASES},
    )
    other_cases = await client.get(
        f"/api/v1/dataset-versions/{other_ver.json()['id']}/test-cases",
        headers=ctx["headers"],
    )
    foreign_id = other_cases.json()["items"][0]["id"]

    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={"results": [{"test_case_id": foreign_id, "actual_output": {"answer": "nope"}}]},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_result_rejection(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    first = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "A1"}}
            ]
        },
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "again"}}
            ]
        },
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_completed_run_immutable(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"], "config_snapshot": {"model": "frozen"}},
    )
    run_id = created.json()["id"]
    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "A1"}},
                {"test_case_id": ctx["case_ids"]["case-b"], "actual_output": {"answer": "A2"}},
            ]
        },
    )
    detail = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    assert detail.json()["status"] == "COMPLETED"
    assert detail.json()["config_snapshot"]["model"] == "frozen"
    assert detail.json()["config_snapshot"]["dataset_version_id"] == ctx["version_id"]

    blocked = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "mutate"}}
            ]
        },
    )
    assert blocked.status_code == 409

    # Config remains frozen
    again = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    assert again.json()["config_snapshot"]["model"] == "frozen"
    assert again.json()["config_snapshot"]["dataset_version_id"] == ctx["version_id"]


@pytest.mark.asyncio
async def test_malformed_results_rejected(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    empty = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={"results": []},
    )
    assert empty.status_code == 422
    bad = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={"results": [{"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {}}]},
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_status_transitions_and_aggregates(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    pending = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    assert pending.json()["status"] == "PENDING"

    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_ids"]["case-a"], "actual_output": {"answer": "ok"}},
                {
                    "test_case_id": ctx["case_ids"]["case-b"],
                    "error_message": "model timeout",
                },
            ]
        },
    )
    done = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    data = done.json()
    assert data["status"] == "COMPLETED"
    assert data["total_cases"] == 2
    assert data["completed_cases"] == 1
    assert data["failed_cases"] == 1
    assert data["pending_cases"] == 0
