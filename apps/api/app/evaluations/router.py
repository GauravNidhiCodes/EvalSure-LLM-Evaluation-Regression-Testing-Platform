from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context
from app.core.database import get_db
from app.evaluations import service as evaluations_service
from app.evaluations.schemas import (
    CaseResultOut,
    EvaluationResultsSubmit,
    EvaluationResultsSubmitOut,
    EvaluationRunCreate,
    EvaluationRunCreated,
    EvaluationRunOut,
)

router = APIRouter(tags=["evaluations"])


@router.post(
    "/projects/{project_id}/runs",
    response_model=EvaluationRunCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_run(
    project_id: UUID,
    body: EvaluationRunCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRunCreated:
    return await evaluations_service.create_run(db, project_id, auth, body)


@router.get("/runs/{run_id}", response_model=EvaluationRunOut)
async def get_evaluation_run(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRunOut:
    return await evaluations_service.get_run(db, run_id, auth)


@router.post("/runs/{run_id}/results", response_model=EvaluationResultsSubmitOut)
async def submit_evaluation_results(
    run_id: UUID,
    body: EvaluationResultsSubmit,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResultsSubmitOut:
    return await evaluations_service.submit_results(db, run_id, auth, body)


@router.get("/runs/{run_id}/results", response_model=list[CaseResultOut])
async def list_evaluation_results(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[CaseResultOut]:
    return await evaluations_service.list_case_results(db, run_id, auth)
