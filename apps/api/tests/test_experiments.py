from uuid import uuid4

import pytest
from httpx import AsyncClient

SAMPLE_CASES = [
    {
        "external_id": "exp-a",
        "input": {"question": "Q1"},
        "expected": {"answer": "A1"},
        "metadata": {},
        "tags": [],
    },
    {
        "external_id": "exp-b",
        "input": {"question": "Q2"},
        "expected": {"answer": "A2"},
        "metadata": {},
        "tags": [],
    },
]


async def _project_with_version(client: AsyncClient) -> dict:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": f"exp-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Exp Project"})
    project_id = project.json()["id"]

    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "DS"},
    )
    version = await client.post(
        f"/api/v1/datasets/{dataset.json()['id']}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    cases = await client.get(
        f"/api/v1/dataset-versions/{version.json()['id']}/test-cases",
        headers=headers,
    )
    return {
        "headers": headers,
        "project_id": project_id,
        "version_id": version.json()["id"],
        "case_ids": [c["id"] for c in cases.json()["items"]],
    }


async def _complete_run(client: AsyncClient, headers: dict, project_id: str, version_id: str, case_ids: list, experiment_id: str | None = None) -> str:
    payload: dict = {
        "dataset_version_id": version_id,
        "metrics": ["exact_match", "string_similarity"],
        "config_snapshot": {"model": "example-model"},
    }
    if experiment_id:
        payload["experiment_id"] = experiment_id
    created = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    submit = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=headers,
        json={
            "results": [
                {"test_case_id": case_ids[0], "actual_output": {"answer": "A1"}},
                {"test_case_id": case_ids[1], "actual_output": {"answer": "A2"}},
            ]
        },
    )
    assert submit.status_code == 200
    assert submit.json()["run"]["status"] == "COMPLETED"
    return run_id


@pytest.mark.asyncio
async def test_experiment_create_list_get(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "Customer Support RAG", "description": "Retrieval quality"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Customer Support RAG"
    assert body["baseline_run_id"] is None

    listed = await client.get(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
    )
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json()["items"])

    fetched = await client.get(f"/api/v1/experiments/{body['id']}", headers=ctx["headers"])
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_create_run_without_experiment_still_works(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"]},
    )
    assert created.status_code == 201
    assert created.json()["experiment_id"] is None
    detail = await client.get(f"/api/v1/runs/{created.json()['id']}", headers=ctx["headers"])
    assert detail.json()["experiment_id"] is None
    assert detail.json()["is_baseline"] is False


@pytest.mark.asyncio
async def test_create_run_with_experiment(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    exp = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "RAG"},
    )
    exp_id = exp.json()["id"]
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "experiment_id": exp_id,
            "dataset_version_id": ctx["version_id"],
            "metrics": ["exact_match", "string_similarity"],
            "config_snapshot": {"temperature": 0.2},
        },
    )
    assert created.status_code == 201
    assert created.json()["experiment_id"] == exp_id

    detail = await client.get(f"/api/v1/runs/{created.json()['id']}", headers=ctx["headers"])
    snap = detail.json()["config_snapshot"]
    assert snap["experiment_id"] == exp_id
    assert snap["dataset_version_id"] == ctx["version_id"]
    assert snap["metrics"] == ["exact_match", "string_similarity"]
    assert snap["temperature"] == 0.2
    assert detail.json()["is_baseline"] is False

    runs = await client.get(f"/api/v1/experiments/{exp_id}/runs", headers=ctx["headers"])
    assert runs.status_code == 200
    assert len(runs.json()["items"]) == 1
    assert runs.json()["items"][0]["experiment_id"] == exp_id


@pytest.mark.asyncio
async def test_run_with_foreign_experiment_fails(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)

    other = await client.post(
        "/api/v1/auth/register",
        json={"email": f"other-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    other_project = await client.post(
        "/api/v1/projects", headers=other_headers, json={"name": "Other"}
    )
    foreign_exp = await client.post(
        f"/api/v1/projects/{other_project.json()['id']}/experiments",
        headers=other_headers,
        json={"name": "Foreign"},
    )

    response = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "experiment_id": foreign_exp.json()["id"],
            "dataset_version_id": ctx["version_id"],
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_baseline_assignment_and_replacement(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    exp = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "Customer Support RAG"},
    )
    exp_id = exp.json()["id"]

    run12 = await _complete_run(
        client, ctx["headers"], ctx["project_id"], ctx["version_id"], ctx["case_ids"], exp_id
    )
    run18 = await _complete_run(
        client, ctx["headers"], ctx["project_id"], ctx["version_id"], ctx["case_ids"], exp_id
    )

    set_base = await client.post(
        f"/api/v1/experiments/{exp_id}/baseline/{run12}",
        headers=ctx["headers"],
    )
    assert set_base.status_code == 200
    assert set_base.json()["baseline_run_id"] == run12

    r12 = await client.get(f"/api/v1/runs/{run12}", headers=ctx["headers"])
    r18 = await client.get(f"/api/v1/runs/{run18}", headers=ctx["headers"])
    assert r12.json()["is_baseline"] is True
    assert r18.json()["is_baseline"] is False
    # Historical run data untouched
    assert r12.json()["status"] == "COMPLETED"
    assert r12.json()["config_snapshot"]["metrics"] == ["exact_match", "string_similarity"]

    # Replace baseline
    replace = await client.post(
        f"/api/v1/experiments/{exp_id}/baseline/{run18}",
        headers=ctx["headers"],
    )
    assert replace.json()["baseline_run_id"] == run18

    r12b = await client.get(f"/api/v1/runs/{run12}", headers=ctx["headers"])
    r18b = await client.get(f"/api/v1/runs/{run18}", headers=ctx["headers"])
    assert r12b.json()["is_baseline"] is False
    assert r18b.json()["is_baseline"] is True
    # Old baseline run still exists intact
    assert r12b.json()["status"] == "COMPLETED"
    assert r12b.json()["id"] == run12

    # Idempotent re-assign
    again = await client.post(
        f"/api/v1/experiments/{exp_id}/baseline/{run18}",
        headers=ctx["headers"],
    )
    assert again.status_code == 200
    assert again.json()["baseline_run_id"] == run18


@pytest.mark.asyncio
async def test_baseline_rejects_incomplete_run(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    exp = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "RAG"},
    )
    exp_id = exp.json()["id"]
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"experiment_id": exp_id, "dataset_version_id": ctx["version_id"]},
    )
    run_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/experiments/{exp_id}/baseline/{run_id}",
        headers=ctx["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_baseline_rejects_run_from_other_experiment(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    exp_a = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "A"},
    )
    exp_b = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "B"},
    )
    run_id = await _complete_run(
        client,
        ctx["headers"],
        ctx["project_id"],
        ctx["version_id"],
        ctx["case_ids"],
        exp_a.json()["id"],
    )
    response = await client.post(
        f"/api/v1/experiments/{exp_b.json()['id']}/baseline/{run_id}",
        headers=ctx["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_config_snapshot_immutable_with_experiment(client: AsyncClient) -> None:
    ctx = await _project_with_version(client)
    exp = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/experiments",
        headers=ctx["headers"],
        json={"name": "RAG"},
    )
    run_id = await _complete_run(
        client,
        ctx["headers"],
        ctx["project_id"],
        ctx["version_id"],
        ctx["case_ids"],
        exp.json()["id"],
    )
    before = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    snap = before.json()["config_snapshot"]
    await client.post(
        f"/api/v1/experiments/{exp.json()['id']}/baseline/{run_id}",
        headers=ctx["headers"],
    )
    after = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    assert after.json()["config_snapshot"] == snap
    assert after.json()["is_baseline"] is True
