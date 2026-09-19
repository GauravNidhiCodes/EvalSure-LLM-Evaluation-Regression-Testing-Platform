from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context
from app.core.database import get_db
from app.core.pagination import Page, page_params
from app.datasets import service as datasets_service
from app.datasets.schemas import (
    DatasetCreate,
    DatasetOut,
    DatasetVersionCreate,
    DatasetVersionOut,
    TestCaseOut,
)

router = APIRouter(tags=["datasets"])


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    project_id: UUID,
    body: DatasetCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DatasetOut:
    return await datasets_service.create_dataset(db, project_id, auth, body)


@router.get("/projects/{project_id}/datasets", response_model=Page[DatasetOut])
async def list_datasets(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[DatasetOut]:
    return await datasets_service.list_datasets(db, project_id, auth, params)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
async def get_dataset(
    dataset_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DatasetOut:
    return await datasets_service.get_dataset(db, dataset_id, auth)


@router.post(
    "/datasets/{dataset_id}/versions",
    response_model=DatasetVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version(
    dataset_id: UUID,
    body: DatasetVersionCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DatasetVersionOut:
    return await datasets_service.create_version(db, dataset_id, auth, body)


@router.get("/datasets/{dataset_id}/versions", response_model=Page[DatasetVersionOut])
async def list_dataset_versions(
    dataset_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[DatasetVersionOut]:
    return await datasets_service.list_versions(db, dataset_id, auth, params)


@router.get("/dataset-versions/{version_id}", response_model=DatasetVersionOut)
async def get_dataset_version(
    version_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DatasetVersionOut:
    return await datasets_service.get_version(db, version_id, auth)


@router.get(
    "/dataset-versions/{version_id}/test-cases",
    response_model=Page[TestCaseOut],
)
async def list_version_test_cases(
    version_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[TestCaseOut]:
    return await datasets_service.list_test_cases(db, version_id, auth, params)
