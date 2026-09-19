from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, generate_api_key, require_project_access
from app.core.models import ApiKey, Project, User
from app.projects.schemas import ApiKeyCreate, ApiKeyCreated, ProjectCreate


async def create_project(db: AsyncSession, user: User, body: ProjectCreate) -> Project:
    project = Project(name=body.name, description=body.description, owner_id=user.id)
    db.add(project)
    await db.flush()
    return project


async def list_projects(db: AsyncSession, user: User) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


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


async def list_api_keys(db: AsyncSession, project_id: UUID, user: User) -> list[ApiKey]:
    auth = AuthContext(user=user)
    await require_project_access(project_id, auth, db)
    result = await db.execute(
        select(ApiKey).where(ApiKey.project_id == project_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, project_id: UUID, key_id: UUID, user: User) -> None:
    auth = AuthContext(user=user)
    await require_project_access(project_id, auth, db)
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    record.revoked_at = datetime.now(timezone.utc)
