from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import AuthContext, require_project_access
from app.core.errors import ErrorCode, app_http_error
from app.core.models import EvaluationRun, Experiment, RunStatus, TestCase
from app.core.pagination import Page, PageParams, paginate
from app.evaluations.schemas import EvaluationRunOut
from app.evaluations.service import _run_out
from app.experiments.schemas import ExperimentCreate, ExperimentOut


def _experiment_out(experiment: Experiment) -> ExperimentOut:
    return ExperimentOut(
        id=experiment.id,
        project_id=experiment.project_id,
        name=experiment.name,
        description=experiment.description,
        baseline_run_id=experiment.baseline_run_id,
        created_at=experiment.created_at,
    )


async def _get_experiment_for_auth(
    db: AsyncSession,
    experiment_id: UUID,
    auth: AuthContext,
) -> Experiment:
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise app_http_error(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.EXPERIMENT_NOT_FOUND,
            "Experiment not found",
        )
    await require_project_access(experiment.project_id, auth, db)
    return experiment


async def create_experiment(
    db: AsyncSession,
    project_id: UUID,
    auth: AuthContext,
    body: ExperimentCreate,
) -> ExperimentOut:
    await require_project_access(project_id, auth, db)
    experiment = Experiment(
        project_id=project_id,
        name=body.name,
        description=body.description,
    )
    db.add(experiment)
    await db.flush()
    return _experiment_out(experiment)


async def list_experiments(
    db: AsyncSession,
    project_id: UUID,
    auth: AuthContext,
    params: PageParams,
) -> Page[ExperimentOut]:
    await require_project_access(project_id, auth, db)
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(Experiment)
        .where(Experiment.project_id == project_id)
        .order_by(Experiment.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    return paginate([_experiment_out(exp) for exp in result.scalars().all()], total, params)


async def get_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    auth: AuthContext,
) -> ExperimentOut:
    experiment = await _get_experiment_for_auth(db, experiment_id, auth)
    return _experiment_out(experiment)


async def list_experiment_runs(
    db: AsyncSession,
    experiment_id: UUID,
    auth: AuthContext,
    params: PageParams,
) -> Page[EvaluationRunOut]:
    experiment = await _get_experiment_for_auth(db, experiment_id, auth)
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(EvaluationRun)
                .where(EvaluationRun.experiment_id == experiment.id)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.dataset_version),
            selectinload(EvaluationRun.case_results),
            selectinload(EvaluationRun.experiment),
        )
        .where(EvaluationRun.experiment_id == experiment.id)
        .order_by(EvaluationRun.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    runs = list(result.scalars().all())
    version_ids = {run.dataset_version_id for run in runs}
    counts: dict[UUID, int] = {}
    if version_ids:
        count_rows = await db.execute(
            select(TestCase.dataset_version_id, func.count())
            .where(TestCase.dataset_version_id.in_(version_ids))
            .group_by(TestCase.dataset_version_id)
        )
        counts = {vid: int(n) for vid, n in count_rows.all()}

    items = [
        _run_out(
            run,
            total_cases=counts.get(run.dataset_version_id, 0),
            baseline_run_id=experiment.baseline_run_id,
        )
        for run in runs
    ]
    return paginate(items, total, params)


async def set_baseline(
    db: AsyncSession,
    experiment_id: UUID,
    run_id: UUID,
    auth: AuthContext,
) -> ExperimentOut:
    experiment = await _get_experiment_for_auth(db, experiment_id, auth)

    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise app_http_error(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.RUN_NOT_FOUND,
            "Evaluation run was not found.",
        )
    if run.experiment_id != experiment.id:
        raise app_http_error(
            status.HTTP_400_BAD_REQUEST,
            ErrorCode.BAD_REQUEST,
            "Run does not belong to this experiment",
        )
    if run.status != RunStatus.COMPLETED.value:
        raise app_http_error(
            status.HTTP_400_BAD_REQUEST,
            ErrorCode.INVALID_RUN_STATE,
            f"Only COMPLETED runs can be baselines (run status is {run.status})",
        )

    # Idempotent: re-assigning the same baseline is a no-op success.
    experiment.baseline_run_id = run.id
    await db.flush()
    return _experiment_out(experiment)
