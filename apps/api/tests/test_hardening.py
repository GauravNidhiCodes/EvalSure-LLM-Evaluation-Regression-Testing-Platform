"""Production hardening tests — errors, pagination, state machine, request IDs."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.evaluations.state import ALLOWED_TRANSITIONS, assert_transition
from app.core.models import RunStatus
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_error_format_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/runs/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "message" in body["error"]
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_custom_request_id_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "req-hardening-1"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-hardening-1"


@pytest.mark.asyncio
async def test_pagination_projects(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "page@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await client.post("/api/v1/projects", headers=headers, json={"name": "P1"})
    await client.post("/api/v1/projects", headers=headers, json={"name": "P2"})

    page = await client.get("/api/v1/projects?page=1&page_size=1", headers=headers)
    assert page.status_code == 200
    body = page.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] == 2
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_invalid_run_state_transition_helper() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_transition(RunStatus.COMPLETED.value, RunStatus.RUNNING.value)
    assert exc.value.status_code == 409
    assert RunStatus.COMPLETED.value in ALLOWED_TRANSITIONS
    assert not ALLOWED_TRANSITIONS[RunStatus.COMPLETED.value]


@pytest.mark.asyncio
async def test_duplicate_result_submission_rejected(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupres@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Dup"})
    project_id = project.json()["id"]
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "D"},
    )
    version = await client.post(
        f"/api/v1/datasets/{dataset.json()['id']}/versions",
        headers=headers,
        json={
            "test_cases": [
                {"external_id": "c1", "input": {"q": "1"}, "expected": {"a": "1"}},
            ]
        },
    )
    run = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers=headers,
        json={"dataset_version_id": version.json()["id"], "metrics": ["exact_match"]},
    )
    cases = await client.get(
        f"/api/v1/dataset-versions/{version.json()['id']}/test-cases",
        headers=headers,
    )
    case_id = cases.json()["items"][0]["id"]
    payload = {
        "results": [
            {"test_case_id": case_id, "actual_output": {"a": "1"}},
            {"test_case_id": case_id, "actual_output": {"a": "1"}},
        ]
    }
    dup = await client.post(
        f"/api/v1/runs/{run.json()['id']}/results",
        headers=headers,
        json=payload,
    )
    assert dup.status_code == 422
    assert dup.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_completed_run_immutable(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "immut@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Imm"})
    project_id = project.json()["id"]
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "D"},
    )
    version = await client.post(
        f"/api/v1/datasets/{dataset.json()['id']}/versions",
        headers=headers,
        json={
            "test_cases": [
                {"external_id": "c1", "input": {"q": "1"}, "expected": {"a": "1"}},
            ]
        },
    )
    run = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers=headers,
        json={"dataset_version_id": version.json()["id"], "metrics": ["exact_match"]},
    )
    cases = await client.get(
        f"/api/v1/dataset-versions/{version.json()['id']}/test-cases",
        headers=headers,
    )
    case_id = cases.json()["items"][0]["id"]
    first = await client.post(
        f"/api/v1/runs/{run.json()['id']}/results",
        headers=headers,
        json={"results": [{"test_case_id": case_id, "actual_output": {"a": "1"}}]},
    )
    assert first.status_code == 200
    assert first.json()["run"]["status"] == "COMPLETED"

    again = await client.post(
        f"/api/v1/runs/{run.json()['id']}/results",
        headers=headers,
        json={"results": [{"test_case_id": case_id, "actual_output": {"a": "1"}}]},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_RUN_STATE"


@pytest.mark.asyncio
async def test_expired_token_error_shape(client: AsyncClient) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "typ": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
