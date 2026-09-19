import pytest
from httpx import AsyncClient

from app.auth.security import generate_api_key, hash_api_key


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "EVALSURE"


@pytest.mark.asyncio
async def test_register_login_and_create_project(client: AsyncClient) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "dev@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "dev@example.com"

    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Demo", "description": "Phase 0"},
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    key = await client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        headers=headers,
        json={"name": "ci"},
    )
    assert key.status_code == 201
    payload = key.json()
    assert payload["api_key"].startswith("evs_")
    assert "key_hash" not in payload

    listed = await client.get(f"/api/v1/projects/{project_id}/api-keys", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["key_prefix"] == payload["key_prefix"]
    assert "api_key" not in listed.json()["items"][0]

    # Authenticate with API key
    me_via_key = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": payload["api_key"]},
    )
    assert me_via_key.status_code == 200
    assert me_via_key.json()["email"] == "dev@example.com"


def test_api_key_is_hashed_not_raw() -> None:
    raw, prefix, key_hash = generate_api_key()
    assert raw.startswith("evs_")
    assert prefix == raw[:12]
    assert key_hash == hash_api_key(raw)
    assert raw not in key_hash
    assert len(key_hash) == 64
