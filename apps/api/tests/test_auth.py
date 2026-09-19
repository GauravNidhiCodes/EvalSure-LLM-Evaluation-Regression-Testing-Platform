"""Authentication + API key management tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.security import create_access_token
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    again = await client.post("/api/v1/auth/register", json=payload)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success_and_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )
    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert "password" not in bad.text.lower() or "Invalid credentials" in bad.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_and_expired_token(client: AsyncClient) -> None:
    invalid = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert invalid.status_code == 401

    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "typ": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    expired_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_resp.status_code == 401


@pytest.mark.asyncio
async def test_current_user_dependency(client: AsyncClient) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = register.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"
    assert "password_hash" not in me.json()

    # JWT-only routes (create project) use get_current_user
    project = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Owned"},
    )
    assert project.status_code == 201

    no_auth = await client.post("/api/v1/projects", json={"name": "Nope"})
    assert no_auth.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_project_access_rejected(client: AsyncClient) -> None:
    owner = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    other = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    project = await client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Private"},
    )
    project_id = project.json()["id"]

    denied = await client.get(f"/api/v1/projects/{project_id}", headers=other_headers)
    assert denied.status_code == 403

    denied_keys = await client.get(
        f"/api/v1/projects/{project_id}/api-keys",
        headers=other_headers,
    )
    assert denied_keys.status_code == 403


@pytest.mark.asyncio
async def test_api_key_lifecycle(client: AsyncClient) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "keys@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Key Project"},
    )
    project_id = project.json()["id"]

    created = await client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        headers=headers,
        json={"name": "local-development"},
    )
    assert created.status_code == 201
    payload = created.json()
    raw = payload["api_key"]
    key_id = payload["id"]
    assert raw.startswith("evs_")
    assert "key_hash" not in payload

    listed = await client.get(f"/api/v1/projects/{project_id}/api-keys", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert "api_key" not in item
    assert "key_hash" not in item
    assert item["status"] == "active"
    assert item["name"] == "local-development"

    ok = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert ok.status_code == 200

    revoke = await client.delete(
        f"/api/v1/projects/{project_id}/api-keys/{key_id}",
        headers=headers,
    )
    assert revoke.status_code == 204

    listed_after = await client.get(f"/api/v1/projects/{project_id}/api-keys", headers=headers)
    assert listed_after.json()["items"][0]["status"] == "revoked"
    assert listed_after.json()["items"][0]["revoked_at"] is not None

    rejected = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_unknown_and_malformed_api_key_rejected(client: AsyncClient) -> None:
    unknown = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": "evs_this_key_does_not_exist_anywhere_000"},
    )
    assert unknown.status_code == 401

    malformed = await client.get("/api/v1/auth/me", headers={"X-API-Key": "not-a-key"})
    assert malformed.status_code == 401


def test_access_token_claims_are_minimal() -> None:
    settings = get_settings()
    user_id = uuid4()
    token = create_access_token(user_id)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == str(user_id)
    assert payload["typ"] == "access"
    assert "exp" in payload
    assert "password" not in payload
    assert "api_key" not in payload
