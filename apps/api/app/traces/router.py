from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, get_auth_context
from app.core.database import get_db
from app.traces.schemas import CaseTracesOut, RunTracesOut
from app.traces.service import TraceService

router = APIRouter(tags=["traces"])


@router.get("/runs/{run_id}/traces", response_model=RunTracesOut)
async def get_run_traces(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> RunTracesOut:
    return await TraceService.get_run_events(db, run_id, auth)


@router.get(
    "/runs/{run_id}/cases/{case_result_id}/traces",
    response_model=CaseTracesOut,
)
async def get_case_traces(
    run_id: UUID,
    case_result_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CaseTracesOut:
    return await TraceService.get_case_events(db, run_id, case_result_id, auth)
