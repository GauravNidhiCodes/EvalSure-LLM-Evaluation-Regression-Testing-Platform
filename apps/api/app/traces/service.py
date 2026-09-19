"""TraceService — append-only evaluation observability events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import AuthContext, require_project_access
from app.core.errors import ErrorCode, app_http_error
from app.core.models import CaseResult, EvaluationRun, TraceEvent
from app.core.pagination import PageParams
from app.traces.events import TraceEventType
from app.traces.sanitize import sanitize_error_message, sanitize_trace_data
from app.traces.schemas import CaseTracesOut, RunTracesOut, TraceEventOut


def _event_out(event: TraceEvent) -> TraceEventOut:
    return TraceEventOut.model_validate(event)


class TraceService:
    """Create and retrieve append-only TraceEvent rows. Independently testable."""

    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        run_id: UUID,
        event_type: TraceEventType | str,
        data: dict[str, Any] | None = None,
        case_result_id: UUID | None = None,
        timestamp: datetime | None = None,
    ) -> TraceEvent:
        if isinstance(event_type, TraceEventType):
            type_value = event_type.value
        else:
            type_value = str(event_type)

        if case_result_id is not None:
            result = await db.execute(select(CaseResult).where(CaseResult.id == case_result_id))
            case = result.scalar_one_or_none()
            if case is None:
                raise app_http_error(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorCode.BAD_REQUEST,
                    "case_result_id does not exist",
                )
            if case.run_id != run_id:
                raise app_http_error(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorCode.BAD_REQUEST,
                    "case_result_id does not belong to this run",
                )

        payload = sanitize_trace_data(data)
        payload.setdefault("run_id", str(run_id))
        if case_result_id is not None:
            payload.setdefault("case_result_id", str(case_result_id))

        event = TraceEvent(
            run_id=run_id,
            case_result_id=case_result_id,
            event_type=type_value,
            timestamp=timestamp or datetime.now(timezone.utc),
            data=payload,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def record_error_event(
        db: AsyncSession,
        *,
        run_id: UUID,
        event_type: TraceEventType,
        message: str | None,
        error_type: str | None = None,
        case_result_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TraceEvent:
        data = sanitize_error_message(message, error_type=error_type)
        if extra:
            data.update(sanitize_trace_data(extra))
        return await TraceService.record_event(
            db,
            run_id=run_id,
            event_type=event_type,
            data=data,
            case_result_id=case_result_id,
        )

    @staticmethod
    async def get_run_events(
        db: AsyncSession,
        run_id: UUID,
        auth: AuthContext,
        params: PageParams,
    ) -> RunTracesOut:
        run = await TraceService._require_run_access(db, run_id, auth)
        total = int(
            (
                await db.execute(
                    select(func.count()).select_from(TraceEvent).where(TraceEvent.run_id == run.id)
                )
            ).scalar_one()
        )
        result = await db.execute(
            select(TraceEvent)
            .where(TraceEvent.run_id == run.id)
            .order_by(TraceEvent.timestamp.asc(), TraceEvent.created_at.asc())
            .offset(params.offset)
            .limit(params.limit)
        )
        events = [_event_out(e) for e in result.scalars().all()]
        return RunTracesOut(
            run_id=run.id,
            events=events,
            page=params.page,
            page_size=params.page_size,
            total=total,
        )

    @staticmethod
    async def get_case_events(
        db: AsyncSession,
        run_id: UUID,
        case_result_id: UUID,
        auth: AuthContext,
    ) -> CaseTracesOut:
        run = await TraceService._require_run_access(db, run_id, auth)
        result = await db.execute(
            select(CaseResult).where(CaseResult.id == case_result_id, CaseResult.run_id == run.id)
        )
        case = result.scalar_one_or_none()
        if case is None:
            raise app_http_error(
                status.HTTP_404_NOT_FOUND,
                ErrorCode.CASE_RESULT_NOT_FOUND,
                "Case result not found for this run",
            )

        events_result = await db.execute(
            select(TraceEvent)
            .where(
                TraceEvent.run_id == run.id,
                TraceEvent.case_result_id == case.id,
            )
            .order_by(TraceEvent.timestamp.asc(), TraceEvent.created_at.asc())
        )
        events = [_event_out(e) for e in events_result.scalars().all()]
        return CaseTracesOut(run_id=run.id, case_result_id=case.id, events=events)

    @staticmethod
    async def _require_run_access(
        db: AsyncSession,
        run_id: UUID,
        auth: AuthContext,
    ) -> EvaluationRun:
        result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise app_http_error(
                status.HTTP_404_NOT_FOUND,
                ErrorCode.RUN_NOT_FOUND,
                "Evaluation run was not found.",
            )
        await require_project_access(run.project_id, auth, db)
        return run
