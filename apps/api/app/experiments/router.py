from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context
from app.core.database import get_db
from app.core.pagination import Page, page_params
from app.evaluations.schemas import EvaluationRunOut
from app.experiments import service as experiments_service
from app.experiments.schemas import ExperimentCreate, ExperimentOut

router = APIRouter(tags=["experiments"])


@router.post(
    "/projects/{project_id}/experiments",
    response_model=ExperimentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    project_id: UUID,
    body: ExperimentCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ExperimentOut:
    return await experiments_service.create_experiment(db, project_id, auth, body)


@router.get("/projects/{project_id}/experiments", response_model=Page[ExperimentOut])
async def list_experiments(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[ExperimentOut]:
    return await experiments_service.list_experiments(db, project_id, auth, params)


@router.get("/experiments/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(
    experiment_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ExperimentOut:
    return await experiments_service.get_experiment(db, experiment_id, auth)


@router.get("/experiments/{experiment_id}/runs", response_model=Page[EvaluationRunOut])
async def list_experiment_runs(
    experiment_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    params=Depends(page_params),
) -> Page[EvaluationRunOut]:
    return await experiments_service.list_experiment_runs(db, experiment_id, auth, params)


@router.post(
    "/experiments/{experiment_id}/baseline/{run_id}",
    response_model=ExperimentOut,
)
async def set_experiment_baseline(
    experiment_id: UUID,
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ExperimentOut:
    return await experiments_service.set_baseline(db, experiment_id, run_id, auth)
