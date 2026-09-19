from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import AuthContext, require_project_access
from app.core.models import Dataset, DatasetVersion, TestCase
from app.datasets.hashing import content_hash_for_cases
from app.datasets.schemas import (
    DatasetCreate,
    DatasetOut,
    DatasetVersionCreate,
    DatasetVersionOut,
    TestCaseOut,
)


def _dataset_out(dataset: Dataset) -> DatasetOut:
    return DatasetOut(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        metadata=dataset.metadata_ or {},
        created_at=dataset.created_at,
    )


def _version_out(version: DatasetVersion, test_case_count: int | None = None) -> DatasetVersionOut:
    return DatasetVersionOut(
        id=version.id,
        dataset_id=version.dataset_id,
        version=version.version,
        content_hash=version.content_hash,
        created_at=version.created_at,
        test_case_count=test_case_count,
    )


def _case_out(case: TestCase) -> TestCaseOut:
    return TestCaseOut(
        id=case.id,
        external_id=case.external_id,
        input=case.input,
        expected=case.expected,
        metadata=case.metadata_ or {},
        tags=list(case.tags or []),
    )


async def _get_dataset_for_auth(
    db: AsyncSession,
    dataset_id: UUID,
    auth: AuthContext,
) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    await require_project_access(dataset.project_id, auth, db)
    return dataset


async def create_dataset(
    db: AsyncSession,
    project_id: UUID,
    auth: AuthContext,
    body: DatasetCreate,
) -> DatasetOut:
    await require_project_access(project_id, auth, db)
    dataset = Dataset(
        project_id=project_id,
        name=body.name,
        description=body.description,
        metadata_=body.metadata,
    )
    db.add(dataset)
    await db.flush()
    return _dataset_out(dataset)


async def list_datasets(
    db: AsyncSession,
    project_id: UUID,
    auth: AuthContext,
) -> list[DatasetOut]:
    await require_project_access(project_id, auth, db)
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc())
    )
    return [_dataset_out(d) for d in result.scalars().all()]


async def get_dataset(
    db: AsyncSession,
    dataset_id: UUID,
    auth: AuthContext,
) -> DatasetOut:
    dataset = await _get_dataset_for_auth(db, dataset_id, auth)
    return _dataset_out(dataset)


async def create_version(
    db: AsyncSession,
    dataset_id: UUID,
    auth: AuthContext,
    body: DatasetVersionCreate,
) -> DatasetVersionOut:
    dataset = await _get_dataset_for_auth(db, dataset_id, auth)

    max_ver = await db.execute(
        select(func.coalesce(func.max(DatasetVersion.version), 0)).where(
            DatasetVersion.dataset_id == dataset.id
        )
    )
    next_version = int(max_ver.scalar_one()) + 1

    case_dicts = [
        {
            "external_id": case.external_id,
            "input": case.input,
            "expected": case.expected,
            "metadata": case.metadata,
            "tags": case.tags,
        }
        for case in body.test_cases
    ]
    content_hash = content_hash_for_cases(case_dicts)

    version = DatasetVersion(
        dataset_id=dataset.id,
        version=next_version,
        content_hash=content_hash,
    )
    db.add(version)
    await db.flush()

    for case in body.test_cases:
        db.add(
            TestCase(
                dataset_version_id=version.id,
                external_id=case.external_id,
                input=case.input,
                expected=case.expected,
                metadata_=case.metadata,
                tags=case.tags,
            )
        )
    await db.flush()
    return _version_out(version, test_case_count=len(body.test_cases))


async def list_versions(
    db: AsyncSession,
    dataset_id: UUID,
    auth: AuthContext,
) -> list[DatasetVersionOut]:
    await _get_dataset_for_auth(db, dataset_id, auth)
    result = await db.execute(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
    )
    versions = list(result.scalars().all())
    out: list[DatasetVersionOut] = []
    for version in versions:
        count = await db.execute(
            select(func.count())
            .select_from(TestCase)
            .where(TestCase.dataset_version_id == version.id)
        )
        out.append(_version_out(version, test_case_count=int(count.scalar_one())))
    return out


async def get_version(
    db: AsyncSession,
    version_id: UUID,
    auth: AuthContext,
) -> DatasetVersionOut:
    result = await db.execute(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset), selectinload(DatasetVersion.test_cases))
        .where(DatasetVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
    await require_project_access(version.dataset.project_id, auth, db)
    return _version_out(version, test_case_count=len(version.test_cases))


async def list_test_cases(
    db: AsyncSession,
    version_id: UUID,
    auth: AuthContext,
) -> list[TestCaseOut]:
    result = await db.execute(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset))
        .where(DatasetVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
    await require_project_access(version.dataset.project_id, auth, db)

    cases = await db.execute(
        select(TestCase)
        .where(TestCase.dataset_version_id == version_id)
        .order_by(TestCase.external_id.asc())
    )
    return [_case_out(case) for case in cases.scalars().all()]
