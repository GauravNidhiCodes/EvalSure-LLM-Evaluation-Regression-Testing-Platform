from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context
from app.core.database import get_db
from app.metrics.registry import MetricRegistry
from app.regression import service as regression_service
from app.regression.schemas import (
    EvaluateRegressionOut,
    RegressionPolicyCreate,
    RegressionPolicyOut,
)

router = APIRouter(tags=["regression"])


@router.get("/metrics", response_model=list[str])
async def list_metrics() -> list[str]:
    return MetricRegistry.list_metrics()


@router.post(
    "/experiments/{experiment_id}/regression-policies",
    response_model=RegressionPolicyOut,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_regression_policy(
    experiment_id: UUID,
    body: RegressionPolicyCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> RegressionPolicyOut:
    return await regression_service.upsert_policy(db, experiment_id, auth, body)


@router.get(
    "/experiments/{experiment_id}/regression-policies",
    response_model=list[RegressionPolicyOut],
)
async def list_regression_policies(
    experiment_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[RegressionPolicyOut]:
    return await regression_service.list_policies(db, experiment_id, auth)


@router.delete("/regression-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regression_policy(
    policy_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    await regression_service.delete_policy(db, policy_id, auth)


@router.post("/runs/{run_id}/evaluate-regression", response_model=EvaluateRegressionOut)
async def evaluate_regression(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> EvaluateRegressionOut:
    return await regression_service.evaluate_run_regression(db, run_id, auth)
