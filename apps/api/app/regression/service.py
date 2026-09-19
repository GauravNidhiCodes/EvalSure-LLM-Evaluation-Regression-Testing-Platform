from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import AuthContext, require_project_access
from app.core.models import (
    CaseResult,
    EvaluationRun,
    Experiment,
    RegressionPolicy,
    RegressionStatus,
    RunStatus,
)
from app.judge.errors import JudgeEvaluationError
from app.metrics.registry import MetricContext, MetricRegistry
from app.regression.engine import RegressionService
from app.regression.schemas import (
    EvaluateRegressionOut,
    RegressionInfo,
    RegressionPolicyCreate,
    RegressionPolicyOut,
)


def _policy_out(policy: RegressionPolicy) -> RegressionPolicyOut:
    return RegressionPolicyOut.model_validate(policy)


def _regression_info_from_summary(
    summary: dict | None,
    regression_status: str,
    experiment_baseline_id: UUID | None = None,
) -> RegressionInfo:
    if not summary:
        return RegressionInfo(
            status=RegressionStatus(regression_status),
            baseline_run_id=experiment_baseline_id,
        )
    aggregate = summary.get("aggregate") or {}
    violations = [
        {"metric": name, **data}
        for name, data in aggregate.items()
        if isinstance(data, dict) and data.get("violated")
    ]
    baseline_raw = summary.get("baseline_run_id")
    baseline_id = UUID(baseline_raw) if baseline_raw else experiment_baseline_id
    return RegressionInfo(
        status=RegressionStatus(summary.get("status", regression_status)),
        baseline_run_id=baseline_id,
        regressed_case_count=int(summary.get("regressed_case_count") or 0),
        aggregate=aggregate,
        regressed_cases=list(summary.get("regressed_cases") or []),
        violations=violations,
        incomparable_cases=list(summary.get("incomparable_cases") or []),
        notes=list(summary.get("notes") or []),
    )


async def _get_experiment(db: AsyncSession, experiment_id: UUID, auth: AuthContext) -> Experiment:
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    await require_project_access(experiment.project_id, auth, db)
    return experiment


async def upsert_policy(
    db: AsyncSession,
    experiment_id: UUID,
    auth: AuthContext,
    body: RegressionPolicyCreate,
) -> RegressionPolicyOut:
    experiment = await _get_experiment(db, experiment_id, auth)
    existing = await db.execute(
        select(RegressionPolicy).where(
            RegressionPolicy.experiment_id == experiment.id,
            RegressionPolicy.metric_name == body.metric_name,
        )
    )
    policy = existing.scalar_one_or_none()
    if policy is None:
        policy = RegressionPolicy(
            experiment_id=experiment.id,
            metric_name=body.metric_name,
            max_allowed_drop=body.max_allowed_drop,
            min_aggregate_score=body.min_aggregate_score,
            max_regressed_cases=body.max_regressed_cases,
        )
        db.add(policy)
    else:
        policy.max_allowed_drop = body.max_allowed_drop
        policy.min_aggregate_score = body.min_aggregate_score
        policy.max_regressed_cases = body.max_regressed_cases
    await db.flush()
    return _policy_out(policy)


async def list_policies(
    db: AsyncSession,
    experiment_id: UUID,
    auth: AuthContext,
) -> list[RegressionPolicyOut]:
    await _get_experiment(db, experiment_id, auth)
    result = await db.execute(
        select(RegressionPolicy)
        .where(RegressionPolicy.experiment_id == experiment_id)
        .order_by(RegressionPolicy.metric_name.asc())
    )
    return [_policy_out(p) for p in result.scalars().all()]


async def delete_policy(
    db: AsyncSession,
    policy_id: UUID,
    auth: AuthContext,
) -> None:
    result = await db.execute(
        select(RegressionPolicy)
        .options(selectinload(RegressionPolicy.experiment))
        .where(RegressionPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regression policy not found")
    await require_project_access(policy.experiment.project_id, auth, db)
    await db.delete(policy)
    await db.flush()


def _ensure_scores_for_results(
    results: list[CaseResult],
    metric_names: list[str],
    *,
    persist: bool,
) -> dict[UUID, dict[str, dict]]:
    """Compute metric scores from actual vs expected. Optionally persist on CaseResult.

    Already-persisted scores (including llm_judge reasons) are reused — no duplicate
    provider calls. Judge failures leave the metric unset for that case.
    """
    by_case: dict[UUID, dict[str, dict]] = {}
    for cr in results:
        expected = cr.test_case.expected if cr.test_case else None
        input_data = cr.test_case.input if cr.test_case else None
        existing = dict(cr.metric_scores or {})
        needed = [m for m in metric_names if m not in existing]
        if needed:
            try:
                computed = MetricRegistry.score_case(
                    cr.actual_output,
                    expected,
                    needed,
                    context=MetricContext(input=input_data),
                )
                existing.update(computed)
                if persist:
                    cr.metric_scores = existing
            except JudgeEvaluationError:
                # Leave missing scores; regression treats them as incomparable.
                if persist:
                    cr.metric_scores = existing
        by_case[cr.test_case_id] = existing
    return by_case


async def evaluate_run_regression(
    db: AsyncSession,
    run_id: UUID,
    auth: AuthContext,
) -> EvaluateRegressionOut:
    result = await db.execute(
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.experiment).selectinload(Experiment.regression_policies),
            selectinload(EvaluationRun.case_results).selectinload(CaseResult.test_case),
        )
        .where(EvaluationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    await require_project_access(run.project_id, auth, db)

    if run.status != RunStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run must be COMPLETED to evaluate regression (status={run.status})",
        )

    experiment = run.experiment
    if experiment is None:
        run.regression_status = RegressionStatus.NOT_EVALUATED.value
        run.regression_summary = {
            "status": RegressionStatus.NOT_EVALUATED.value,
            "baseline_run_id": None,
            "regressed_case_count": 0,
            "aggregate": {},
            "regressed_cases": [],
            "notes": ["Run is not linked to an experiment"],
        }
        # Clear current-run regression flags
        for cr in run.case_results:
            cr.is_regression = False
        await db.flush()
        return EvaluateRegressionOut(
            run_id=run.id,
            evaluation_status=run.status,
            regression=_regression_info_from_summary(run.regression_summary, run.regression_status),
        )

    policies = list(experiment.regression_policies or [])
    baseline_run: EvaluationRun | None = None
    baseline_results: list[CaseResult] = []

    if experiment.baseline_run_id:
        baseline_result = await db.execute(
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.case_results).selectinload(CaseResult.test_case))
            .where(EvaluationRun.id == experiment.baseline_run_id)
        )
        baseline_run = baseline_result.scalar_one_or_none()
        if baseline_run:
            baseline_results = list(baseline_run.case_results)

    if baseline_run is None or not policies:
        note = (
            "No baseline configured for experiment"
            if baseline_run is None
            else "No regression policies configured"
        )
        run.regression_status = RegressionStatus.NOT_EVALUATED.value
        run.regression_summary = {
            "status": RegressionStatus.NOT_EVALUATED.value,
            "baseline_run_id": str(baseline_run.id) if baseline_run else None,
            "regressed_case_count": 0,
            "aggregate": {},
            "regressed_cases": [],
            "notes": [note],
        }
        for cr in run.case_results:
            cr.is_regression = False
        await db.flush()
        return EvaluateRegressionOut(
            run_id=run.id,
            evaluation_status=run.status,
            regression=_regression_info_from_summary(
                run.regression_summary, run.regression_status, experiment.baseline_run_id
            ),
        )

    metric_names = [p.metric_name for p in policies if MetricRegistry.has(p.metric_name)]
    # Persist scores only on the current run; baseline scores are computed in memory.
    current_scores = _ensure_scores_for_results(
        list(run.case_results), metric_names, persist=True
    )
    baseline_scores = _ensure_scores_for_results(
        baseline_results, metric_names, persist=False
    )

    engine = RegressionService()
    outcome = engine.evaluate(
        current_run=run,
        baseline_run=baseline_run,
        current_results=list(run.case_results),
        baseline_results=baseline_results,
        policies=policies,
        current_scores_by_case=current_scores,
        baseline_scores_by_case=baseline_scores,
    )

    regressed_ids = {UUID(c.test_case_id) for c in outcome.regressed_cases}
    for cr in run.case_results:
        cr.is_regression = cr.test_case_id in regressed_ids

    run.regression_status = outcome.status.value
    run.regression_summary = outcome.to_summary()
    await db.flush()

    # EvaluationRun.status stays COMPLETED even when regression FAILS.
    return EvaluateRegressionOut(
        run_id=run.id,
        evaluation_status=run.status,
        regression=_regression_info_from_summary(
            run.regression_summary, run.regression_status, experiment.baseline_run_id
        ),
    )
