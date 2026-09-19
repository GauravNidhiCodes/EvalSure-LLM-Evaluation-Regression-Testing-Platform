import pytest
from httpx import AsyncClient

from app.datasets.hashing import content_hash_for_cases


SAMPLE_CASES = [
    {
        "external_id": "dbms-001",
        "input": {"question": "What is normalization?"},
        "expected": {"answer": "Normalization is..."},
        "metadata": {"category": "DBMS", "difficulty": "easy"},
        "tags": ["dbms", "normalization"],
    },
    {
        "external_id": "dbms-002",
        "input": {"question": "What is a primary key?"},
        "expected": {"answer": "A unique identifier..."},
        "metadata": {"category": "DBMS"},
        "tags": ["dbms"],
    },
]


async def _auth_project(client: AsyncClient) -> tuple[str, str]:
    email = "datasets@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    if register.status_code == 409:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        token = login.json()["access_token"]
    else:
        assert register.status_code == 201
        token = register.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Dataset Project"},
    )
    assert project.status_code == 201
    return headers["Authorization"], project.json()["id"]


@pytest.mark.asyncio
async def test_dataset_create_and_list(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}

    created = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "DBMS QA", "description": "Core DBMS questions", "metadata": {"owner": "qa"}},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "DBMS QA"
    assert body["metadata"] == {"owner": "qa"}
    dataset_id = body["id"]

    listed = await client.get(f"/api/v1/projects/{project_id}/datasets", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == dataset_id for item in listed.json()["items"])

    fetched = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == dataset_id


@pytest.mark.asyncio
async def test_version_creation_and_test_case_retrieval(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}

    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "DBMS"},
    )
    dataset_id = dataset.json()["id"]

    version = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    assert version.status_code == 201
    payload = version.json()
    assert payload["version"] == 1
    assert payload["test_case_count"] == 2
    assert len(payload["content_hash"]) == 64
    version_id = payload["id"]

    versions = await client.get(f"/api/v1/datasets/{dataset_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert versions.json()["items"][0]["id"] == version_id

    detail = await client.get(f"/api/v1/dataset-versions/{version_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["content_hash"] == payload["content_hash"]

    cases = await client.get(f"/api/v1/dataset-versions/{version_id}/test-cases", headers=headers)
    assert cases.status_code == 200
    ids = [c["external_id"] for c in cases.json()["items"]]
    assert ids == ["dbms-001", "dbms-002"]


@pytest.mark.asyncio
async def test_reject_empty_dataset_version(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Empty"},
    )
    dataset_id = dataset.json()["id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reject_duplicate_external_id(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Dupes"},
    )
    dataset_id = dataset.json()["id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={
            "test_cases": [
                {
                    "external_id": "same",
                    "input": {"q": "1"},
                    "expected": {"a": "1"},
                },
                {
                    "external_id": "same",
                    "input": {"q": "2"},
                    "expected": {"a": "2"},
                },
            ]
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reject_malformed_test_case(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Bad"},
    )
    dataset_id = dataset.json()["id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": [{"external_id": "x", "input": {}}]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dataset_versions_are_immutable(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Immutable"},
    )
    dataset_id = dataset.json()["id"]
    version = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES[:1]},
    )
    version_id = version.json()["id"]
    original_hash = version.json()["content_hash"]

    for method in ("put", "patch"):
        response = await getattr(client, method)(
            f"/api/v1/dataset-versions/{version_id}",
            headers=headers,
            json={"test_cases": SAMPLE_CASES},
        )
        assert response.status_code in {405, 404, 422}

    delete_response = await client.delete(
        f"/api/v1/dataset-versions/{version_id}",
        headers=headers,
    )
    assert delete_response.status_code in {405, 404}

    # Creating another version increments; original unchanged
    v2 = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    assert v2.status_code == 201
    assert v2.json()["version"] == 2

    original = await client.get(f"/api/v1/dataset-versions/{version_id}", headers=headers)
    assert original.json()["content_hash"] == original_hash
    assert original.json()["version"] == 1
    assert original.json()["test_case_count"] == 1


@pytest.mark.asyncio
async def test_deterministic_content_hashing(client: AsyncClient) -> None:
    auth, project_id = await _auth_project(client)
    headers = {"Authorization": auth}
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "Hash"},
    )
    dataset_id = dataset.json()["id"]

    # Same content, different case order → same hash
    reordered = list(reversed(SAMPLE_CASES))
    expected = content_hash_for_cases(SAMPLE_CASES)
    assert content_hash_for_cases(reordered) == expected

    v1 = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    v2 = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=headers,
        json={"test_cases": reordered},
    )
    assert v1.status_code == 201 and v2.status_code == 201
    assert v1.json()["content_hash"] == v2.json()["content_hash"] == expected
    assert v1.json()["version"] == 1
    assert v2.json()["version"] == 2


def test_content_hash_unit() -> None:
    a = content_hash_for_cases(SAMPLE_CASES)
    b = content_hash_for_cases(list(reversed(SAMPLE_CASES)))
    assert a == b
    assert len(a) == 64
