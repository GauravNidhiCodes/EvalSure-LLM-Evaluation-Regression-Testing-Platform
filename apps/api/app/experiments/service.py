from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import AuthContext, require_project_access
from app.core.models import EvaluationRun, Experiment, RunStatus, TestCase
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
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
) -> list[ExperimentOut]:
    await require_project_access(project_id, auth, db)
    result = await db.execute(
        select(Experiment)
        .where(Experiment.project_id == project_id)
        .order_by(Experiment.created_at.desc())
    )
    return [_experiment_out(exp) for exp in result.scalars().all()]


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
) -> list[EvaluationRunOut]:
    experiment = await _get_experiment_for_auth(db, experiment_id, auth)
    result = await db.execute(
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.dataset_version),
            selectinload(EvaluationRun.case_results),
            selectinload(EvaluationRun.experiment),
        )
        .where(EvaluationRun.experiment_id == experiment.id)
        .order_by(EvaluationRun.created_at.desc())
    )
    runs = list(result.scalars().all())
    out: list[EvaluationRunOut] = []
    for run in runs:
        count = await db.execute(
            select(func.count())
            .select_from(TestCase)
            .where(TestCase.dataset_version_id == run.dataset_version_id)
        )
        out.append(
            _run_out(
                run,
                total_cases=int(count.scalar_one()),
                baseline_run_id=experiment.baseline_run_id,
            )
        )
    return out


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    if run.experiment_id != experiment.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run does not belong to this experiment",
        )
    if run.status != RunStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only COMPLETED runs can be baselines (run status is {run.status})",
        )

    # Persist baseline on the experiment only — do not mutate the run.
    experiment.baseline_run_id = run.id
    await db.flush()
    return _experiment_out(experiment)
