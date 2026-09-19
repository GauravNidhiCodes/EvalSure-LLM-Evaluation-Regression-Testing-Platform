from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import AuthContext, require_project_access
from app.core.config import get_settings
from app.core.models import (
    CaseResult,
    CaseResultStatus,
    DatasetVersion,
    EvaluationRun,
    Experiment,
    RegressionStatus,
    RunStatus,
    TestCase,
)
from app.evaluations.schemas import (
    CaseResultOut,
    DatasetVersionSummary,
    EvaluationResultsSubmit,
    EvaluationResultsSubmitOut,
    EvaluationRunCreate,
    EvaluationRunCreated,
    EvaluationRunOut,
)
from app.judge.errors import JudgeEvaluationError
from app.judge.provider import judge_config_for_snapshot
from app.metrics.registry import MetricContext, MetricRegistry, aggregate_metric_scores
from app.regression.service import _regression_info_from_summary
from app.traces.events import TraceEventType
from app.traces.service import TraceService


def _aggregates(total_cases: int, results: list[CaseResult]) -> tuple[int, int, int]:
    completed = sum(1 for r in results if r.status == CaseResultStatus.COMPLETED.value)
    failed = sum(1 for r in results if r.status == CaseResultStatus.FAILED.value)
    pending = total_cases - completed - failed
    return completed, failed, pending


def _score_case_metrics(
    *,
    actual_output: dict | None,
    test_case: TestCase,
    metric_names: list[str],
) -> tuple[dict, str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Score configured metrics.

    Returns:
        scores, judge_error, model_call payloads, metric_evaluation payloads

    Failure handling: a failed llm_judge evaluation fails the CaseResult (with error_message)
    but does not fail the overall EvaluationRun — the run still becomes COMPLETED when all
    cases have results.
    """
    if not metric_names or actual_output is None:
        return {}, None, [], []
    scores: dict = {}
    judge_error: str | None = None
    metric_events: list[dict[str, Any]] = []
    context = MetricContext(input=test_case.input)
    settings = get_settings()
    for name in metric_names:
        try:
            partial = MetricRegistry.score_case(
                actual_output,
                test_case.expected,
                [name],
                context=context,
            )
            scores.update(partial)
            entry = partial[name]
            event_data: dict[str, Any] = {
                "metric": name,
                "score": entry.get("score"),
                "passed": entry.get("passed"),
            }
            if entry.get("reason") is not None:
                event_data["reason"] = entry["reason"]
            if name == "llm_judge":
                if context.model_calls:
                    last_call = context.model_calls[-1]
                    event_data["provider"] = last_call.get("provider")
                    if last_call.get("model") is not None:
                        event_data["model"] = last_call.get("model")
                else:
                    event_data["provider"] = (
                        settings.judge_provider or "openai_compatible"
                    ).strip().lower()
                    event_data["model"] = settings.judge_model
            metric_events.append(event_data)
        except JudgeEvaluationError as exc:
            judge_error = f"llm_judge: {exc}"
            break
    return scores, judge_error, list(context.model_calls), metric_events


def _run_out(
    run: EvaluationRun,
    *,
    total_cases: int,
    results: list[CaseResult] | None = None,
    baseline_run_id: UUID | None = None,
) -> EvaluationRunOut:
    results = results if results is not None else list(run.case_results or [])
    completed, failed, pending = _aggregates(total_cases, results)
    version = None
    if run.dataset_version is not None:
        version = DatasetVersionSummary.model_validate(run.dataset_version)

    if baseline_run_id is None and run.experiment is not None:
        baseline_run_id = run.experiment.baseline_run_id

    regression_status = RegressionStatus(
        getattr(run, "regression_status", None) or RegressionStatus.NOT_EVALUATED.value
    )
    regression = _regression_info_from_summary(
        getattr(run, "regression_summary", None),
        regression_status.value,
        baseline_run_id,
    )

    return EvaluationRunOut(
        id=run.id,
        run_id=run.id,
        project_id=run.project_id,
        experiment_id=run.experiment_id,
        is_baseline=baseline_run_id is not None and run.id == baseline_run_id,
        dataset_version_id=run.dataset_version_id,
        dataset_version=version,
        status=RunStatus(run.status),
        config_snapshot=dict(run.config_snapshot or {}),
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        total_cases=total_cases,
        completed_cases=completed,
        failed_cases=failed,
        pending_cases=pending,
        regression_status=regression_status,
        baseline_run_id=baseline_run_id,
        regression=regression,
        metric_aggregates=aggregate_metric_scores([dict(r.metric_scores or {}) for r in results]),
    )


async def _count_test_cases(db: AsyncSession, dataset_version_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(TestCase).where(TestCase.dataset_version_id == dataset_version_id)
    )
    return int(result.scalar_one())


def _build_config_snapshot(body: EvaluationRunCreate) -> dict:
    """Freeze reproducibility metadata at run creation. Never mutate afterwards.

    Secrets (API keys) are never included in the snapshot.
    """
    snapshot = dict(body.config_snapshot)
    # Strip any accidentally supplied secrets from client payload.
    snapshot.pop("api_key", None)
    snapshot.pop("judge_api_key", None)
    if isinstance(snapshot.get("judge"), dict):
        judge = dict(snapshot["judge"])
        judge.pop("api_key", None)
        judge.pop("judge_api_key", None)
        snapshot["judge"] = judge

    snapshot["dataset_version_id"] = str(body.dataset_version_id)
    if body.experiment_id is not None:
        snapshot["experiment_id"] = str(body.experiment_id)
    if body.metrics:
        snapshot["metrics"] = list(body.metrics)
    elif "metrics" not in snapshot:
        snapshot["metrics"] = []

    metrics = list(snapshot.get("metrics") or [])
    if "llm_judge" in metrics:
        # Preserve non-secret judge settings for reproducibility.
        snapshot["judge"] = judge_config_for_snapshot()
    return snapshot


async def create_run(
    db: AsyncSession,
    project_id: UUID,
    auth: AuthContext,
    body: EvaluationRunCreate,
) -> EvaluationRunCreated:
    await require_project_access(project_id, auth, db)

    result = await db.execute(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset))
        .where(DatasetVersion.id == body.dataset_version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
    if version.dataset.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset version does not belong to this project",
        )

    experiment_id: UUID | None = None
    if body.experiment_id is not None:
        exp_result = await db.execute(select(Experiment).where(Experiment.id == body.experiment_id))
        experiment = exp_result.scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
        if experiment.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment does not belong to this project",
            )
        experiment_id = experiment.id

    case_count = await _count_test_cases(db, version.id)
    if case_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset version has no test cases",
        )

    run = EvaluationRun(
        project_id=project_id,
        experiment_id=experiment_id,
        dataset_version_id=version.id,
        status=RunStatus.PENDING.value,
        config_snapshot=_build_config_snapshot(body),
    )
    db.add(run)
    await db.flush()
    return EvaluationRunCreated(
        id=run.id,
        run_id=run.id,
        status=RunStatus.PENDING,
        experiment_id=run.experiment_id,
    )


async def get_run(
    db: AsyncSession,
    run_id: UUID,
    auth: AuthContext,
) -> EvaluationRunOut:
    result = await db.execute(
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.dataset_version),
            selectinload(EvaluationRun.case_results),
            selectinload(EvaluationRun.experiment),
        )
        .where(EvaluationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    await require_project_access(run.project_id, auth, db)
    total = await _count_test_cases(db, run.dataset_version_id)
    return _run_out(run, total_cases=total)


async def _record_case_traces(
    db: AsyncSession,
    *,
    run: EvaluationRun,
    case_result: CaseResult,
    test_case_id: UUID,
    model_calls: list[dict[str, Any]],
    metric_events: list[dict[str, Any]],
    case_status: str,
    error_message: str | None,
    latency_ms: float | None,
) -> None:
    await TraceService.record_event(
        db,
        run_id=run.id,
        case_result_id=case_result.id,
        event_type=TraceEventType.CASE_STARTED,
        data={"test_case_id": str(test_case_id)},
    )
    for call in model_calls:
        await TraceService.record_event(
            db,
            run_id=run.id,
            case_result_id=case_result.id,
            event_type=TraceEventType.MODEL_CALL,
            data={**call, "test_case_id": str(test_case_id)},
        )
    for metric_data in metric_events:
        await TraceService.record_event(
            db,
            run_id=run.id,
            case_result_id=case_result.id,
            event_type=TraceEventType.METRIC_EVALUATION,
            data={**metric_data, "test_case_id": str(test_case_id)},
        )
    if case_status == CaseResultStatus.FAILED.value:
        await TraceService.record_error_event(
            db,
            run_id=run.id,
            case_result_id=case_result.id,
            event_type=TraceEventType.CASE_FAILED,
            message=error_message,
            error_type="CaseEvaluationError",
            extra={
                "test_case_id": str(test_case_id),
                **({"latency_ms": latency_ms} if latency_ms is not None else {}),
            },
        )
    else:
        completed_data: dict[str, Any] = {"test_case_id": str(test_case_id)}
        if latency_ms is not None:
            completed_data["latency_ms"] = latency_ms
        await TraceService.record_event(
            db,
            run_id=run.id,
            case_result_id=case_result.id,
            event_type=TraceEventType.CASE_COMPLETED,
            data=completed_data,
        )


async def submit_results(
    db: AsyncSession,
    run_id: UUID,
    auth: AuthContext,
    body: EvaluationResultsSubmit,
) -> EvaluationResultsSubmitOut:
    result = await db.execute(
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.case_results),
            selectinload(EvaluationRun.dataset_version),
            selectinload(EvaluationRun.experiment),
        )
        .where(EvaluationRun.id == run_id)
        .with_for_update()
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    await require_project_access(run.project_id, auth, db)

    if run.status in {RunStatus.COMPLETED.value, RunStatus.FAILED.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is {run.status} and cannot accept new results",
        )
    if run.status not in {RunStatus.PENDING.value, RunStatus.RUNNING.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invalid run status: {run.status}")

    cases_result = await db.execute(
        select(TestCase).where(TestCase.dataset_version_id == run.dataset_version_id)
    )
    cases_by_id = {case.id: case for case in cases_result.scalars().all()}
    existing = {cr.test_case_id: cr for cr in run.case_results}

    submitted_ids = [item.test_case_id for item in body.results]
    unknown = [tid for tid in submitted_ids if tid not in cases_by_id]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or foreign test_case_id values: {', '.join(str(t) for t in unknown)}",
        )

    duplicates = [tid for tid in submitted_ids if tid in existing]
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Results already submitted for test_case_id: {', '.join(str(t) for t in duplicates)}",
        )

    just_started = False
    if run.status == RunStatus.PENDING.value:
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        just_started = True

    metric_names = [
        name
        for name in list((run.config_snapshot or {}).get("metrics") or [])
        if MetricRegistry.has(name)
    ]

    try:
        if just_started:
            await TraceService.record_event(
                db,
                run_id=run.id,
                event_type=TraceEventType.RUN_STARTED,
                data={
                    "dataset_version_id": str(run.dataset_version_id),
                    "metrics": metric_names,
                },
            )

        for item in body.results:
            test_case = cases_by_id[item.test_case_id]
            metric_scores: dict = {}
            model_calls: list[dict[str, Any]] = []
            metric_events: list[dict[str, Any]] = []
            error_message = item.error_message
            case_started_at = perf_counter()

            if item.error_message:
                case_status = CaseResultStatus.FAILED.value
            else:
                metric_scores, judge_error, model_calls, metric_events = _score_case_metrics(
                    actual_output=item.actual_output,
                    test_case=test_case,
                    metric_names=metric_names,
                )
                if judge_error:
                    # Judge failures mark the case failed; run can still COMPLETE overall.
                    case_status = CaseResultStatus.FAILED.value
                    error_message = judge_error
                else:
                    case_status = CaseResultStatus.COMPLETED.value

            latency_ms = (perf_counter() - case_started_at) * 1000.0
            case_result = CaseResult(
                run_id=run.id,
                test_case_id=item.test_case_id,
                actual_output=item.actual_output,
                status=case_status,
                metric_scores=metric_scores,
                error_message=error_message,
            )
            db.add(case_result)
            await db.flush()

            await _record_case_traces(
                db,
                run=run,
                case_result=case_result,
                test_case_id=item.test_case_id,
                model_calls=model_calls,
                metric_events=metric_events,
                case_status=case_status,
                error_message=error_message,
                latency_ms=latency_ms,
            )

        await db.flush()

        refreshed = await db.execute(select(CaseResult).where(CaseResult.run_id == run.id))
        all_results = list(refreshed.scalars().all())
        total = len(cases_by_id)
        _completed, _failed, pending = _aggregates(total, all_results)

        if pending == 0:
            run.status = RunStatus.COMPLETED.value
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = None
            await TraceService.record_event(
                db,
                run_id=run.id,
                event_type=TraceEventType.RUN_COMPLETED,
                data={
                    "total_cases": total,
                    "completed_cases": _completed,
                    "failed_cases": _failed,
                },
            )

        await db.flush()
        await db.refresh(run, attribute_names=["dataset_version", "experiment"])
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        run.status = RunStatus.FAILED.value
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        await TraceService.record_error_event(
            db,
            run_id=run.id,
            event_type=TraceEventType.RUN_FAILED,
            message=str(exc),
            error_type=type(exc).__name__,
        )
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist results; run marked FAILED",
        ) from exc

    out = _run_out(run, total_cases=total, results=all_results)
    return EvaluationResultsSubmitOut(run=out, accepted=len(body.results))


async def list_case_results(
    db: AsyncSession,
    run_id: UUID,
    auth: AuthContext,
) -> list[CaseResultOut]:
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    await require_project_access(run.project_id, auth, db)

    rows = await db.execute(
        select(CaseResult)
        .options(selectinload(CaseResult.test_case))
        .where(CaseResult.run_id == run_id)
        .order_by(CaseResult.created_at.asc())
    )
    out: list[CaseResultOut] = []
    for cr in rows.scalars().all():
        out.append(
            CaseResultOut(
                id=cr.id,
                run_id=cr.run_id,
                test_case_id=cr.test_case_id,
                external_id=cr.test_case.external_id if cr.test_case else None,
                actual_output=cr.actual_output,
                status=CaseResultStatus(cr.status),
                metric_scores=cr.metric_scores or {},
                is_regression=bool(getattr(cr, "is_regression", False)),
                error_message=cr.error_message,
                created_at=cr.created_at,
            )
        )
    return out
