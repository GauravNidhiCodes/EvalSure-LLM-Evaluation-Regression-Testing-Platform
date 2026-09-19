from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context, get_current_user
from app.core.database import get_db
from app.core.models import User
from app.core.pagination import Page, page_params
from app.projects import service as projects_service
from app.projects.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    ProjectCreate,
    ProjectOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await projects_service.create_project(db, user, body)
    return ProjectOut.model_validate(project)


@router.get("", response_model=Page[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[ProjectOut]:
    return await projects_service.list_projects(db, user, params)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await projects_service.get_project(db, project_id, auth)
    return ProjectOut.model_validate(project)


@router.post(
    "/{project_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    project_id: UUID,
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    return await projects_service.create_api_key(db, project_id, user, body)


@router.get("/{project_id}/api-keys", response_model=Page[ApiKeyOut])
async def list_api_keys(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[ApiKeyOut]:
    return await projects_service.list_api_keys(db, project_id, user, params)


@router.delete("/{project_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    project_id: UUID,
    key_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await projects_service.revoke_api_key(db, project_id, key_id, user)
