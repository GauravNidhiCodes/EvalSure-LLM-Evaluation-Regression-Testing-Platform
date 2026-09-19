from datetime import datetime, timezone
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, generate_api_key, require_project_access
from app.core.errors import ErrorCode, app_http_error
from app.core.models import ApiKey, Project, User
from app.core.pagination import Page, PageParams, paginate
from app.projects.schemas import ApiKeyCreate, ApiKeyCreated, ProjectCreate, ProjectOut


async def create_project(db: AsyncSession, user: User, body: ProjectCreate) -> Project:
    project = Project(name=body.name, description=body.description, owner_id=user.id)
    db.add(project)
    await db.flush()
    return project


async def list_projects(db: AsyncSession, user: User, params: PageParams) -> Page[ProjectOut]:
    total = int(
        (
            await db.execute(select(func.count()).select_from(Project).where(Project.owner_id == user.id))
        ).scalar_one()
    )
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    items = [ProjectOut.model_validate(p) for p in result.scalars().all()]
    return paginate(items, total, params)


async def get_project(db: AsyncSession, project_id: UUID, auth: AuthContext) -> Project:
    return await require_project_access(project_id, auth, db)


async def create_api_key(
    db: AsyncSession,
    project_id: UUID,
    user: User,
    body: ApiKeyCreate,
) -> ApiKeyCreated:
    auth = AuthContext(user=user)
    project = await require_project_access(project_id, auth, db)
    raw, prefix, key_hash = generate_api_key()
    record = ApiKey(
        project_id=project.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
    )
    db.add(record)
    await db.flush()
    return ApiKeyCreated(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        api_key=raw,
        created_at=record.created_at,
    )


async def list_api_keys(
    db: AsyncSession,
    project_id: UUID,
    user: User,
    params: PageParams,
) -> Page:
    from app.projects.schemas import ApiKeyOut

    auth = AuthContext(user=user)
    await require_project_access(project_id, auth, db)
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(ApiKey).where(ApiKey.project_id == project_id)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.project_id == project_id)
        .order_by(ApiKey.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    items = [ApiKeyOut.model_validate(k) for k in result.scalars().all()]
    return paginate(items, total, params)


async def revoke_api_key(db: AsyncSession, project_id: UUID, key_id: UUID, user: User) -> None:
    auth = AuthContext(user=user)
    await require_project_access(project_id, auth, db)
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise app_http_error(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.API_KEY_NOT_FOUND,
            "API key not found",
        )
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
