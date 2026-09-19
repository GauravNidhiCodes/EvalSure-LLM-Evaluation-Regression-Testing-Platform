"""Regression detection — compare a completed run against an experiment baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.models import CaseResult, CaseResultStatus, EvaluationRun, RegressionPolicy, RegressionStatus
from app.metrics.registry import MetricRegistry


@dataclass
class RegressedCase:
    test_case_id: str
    metric: str
    baseline_score: float
    current_score: float
    delta: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "metric": self.metric,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "delta": self.delta,
            "reason": self.reason,
        }


@dataclass
class AggregateMetricResult:
    baseline: float | None
    current: float | None
    delta: float | None
    threshold: float
    min_aggregate_score: float | None
    violated: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "current": self.current,
            "delta": self.delta,
            "threshold": self.threshold,
            "min_aggregate_score": self.min_aggregate_score,
            "violated": self.violated,
            "reasons": self.reasons,
        }


@dataclass
class RegressionResult:
    status: RegressionStatus
    baseline_run_id: UUID | None
    aggregate: dict[str, AggregateMetricResult] = field(default_factory=dict)
    regressed_cases: list[RegressedCase] = field(default_factory=list)
    incomparable_cases: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def regressed_case_count(self) -> int:
        return len({c.test_case_id for c in self.regressed_cases})

    def to_summary(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "baseline_run_id": str(self.baseline_run_id) if self.baseline_run_id else None,
            "regressed_case_count": self.regressed_case_count,
            "aggregate": {name: agg.to_dict() for name, agg in self.aggregate.items()},
            "regressed_cases": [c.to_dict() for c in self.regressed_cases],
            "incomparable_cases": self.incomparable_cases,
            "notes": self.notes,
        }


def _score_value(metric_scores: dict[str, Any] | None, metric: str) -> float | None:
    if not metric_scores or metric not in metric_scores:
        return None
    entry = metric_scores[metric]
    if isinstance(entry, dict):
        if "score" in entry:
            return float(entry["score"])
        return None
    try:
        return float(entry)
    except (TypeError, ValueError):
        return None


def _case_passed(case: CaseResult) -> bool:
    return case.status == CaseResultStatus.COMPLETED.value


def _average(scores: list[float]) -> float | None:
    if not scores:
        return None
    return sum(scores) / len(scores)


class RegressionService:
    """Pure comparison engine — no DB access. Independently testable."""

    def evaluate(
        self,
        *,
        current_run: EvaluationRun,
        baseline_run: EvaluationRun | None,
        current_results: list[CaseResult],
        baseline_results: list[CaseResult],
        policies: list[RegressionPolicy],
        current_scores_by_case: dict[UUID, dict[str, dict[str, Any]]],
        baseline_scores_by_case: dict[UUID, dict[str, dict[str, Any]]],
    ) -> RegressionResult:
        if baseline_run is None:
            return RegressionResult(
                status=RegressionStatus.NOT_EVALUATED,
                baseline_run_id=None,
                notes=["No baseline configured for experiment"],
            )
        if not policies:
            return RegressionResult(
                status=RegressionStatus.NOT_EVALUATED,
                baseline_run_id=baseline_run.id,
                notes=["No regression policies configured"],
            )

        notes: list[str] = []
        if current_run.id == baseline_run.id:
            notes.append("Current run is the baseline; deltas are expected to be zero")

        if current_run.dataset_version_id != baseline_run.dataset_version_id:
            notes.append(
                "Baseline and current runs use different dataset versions; "
                "case comparison uses intersecting test_case_id values only"
            )

        baseline_by_case = {cr.test_case_id: cr for cr in baseline_results}
        current_by_case = {cr.test_case_id: cr for cr in current_results}

        aggregate: dict[str, AggregateMetricResult] = {}
        regressed_cases: list[RegressedCase] = []
        incomparable: list[dict[str, Any]] = []
        any_violation = False
        regressed_ids: set[str] = set()

        for policy in policies:
            metric = policy.metric_name
            if not MetricRegistry.has(metric):
                notes.append(f"Policy references unavailable metric '{metric}'; skipped")
                continue

            baseline_scores = [
                s
                for cid, scores in baseline_scores_by_case.items()
                if (s := _score_value(scores, metric)) is not None
            ]
            current_scores = [
                s
                for cid, scores in current_scores_by_case.items()
                if (s := _score_value(scores, metric)) is not None
            ]
            baseline_avg = _average(baseline_scores)
            current_avg = _average(current_scores)

            reasons: list[str] = []
            violated = False
            delta: float | None = None
            if baseline_avg is not None and current_avg is not None:
                delta = current_avg - baseline_avg
                if delta < -policy.max_allowed_drop:
                    violated = True
                    reasons.append(
                        f"aggregate drop {delta:.4f} exceeds max_allowed_drop "
                        f"{policy.max_allowed_drop}"
                    )
            elif baseline_avg is None or current_avg is None:
                notes.append(f"Metric '{metric}' missing aggregate scores on baseline or current")

            if (
                policy.min_aggregate_score is not None
                and current_avg is not None
                and current_avg < policy.min_aggregate_score
            ):
                violated = True
                reasons.append(
                    f"current average {current_avg:.4f} below min_aggregate_score "
                    f"{policy.min_aggregate_score}"
                )

            metric_case_regressions = 0
            shared_ids = set(baseline_by_case) & set(current_by_case)
            only_baseline = set(baseline_by_case) - set(current_by_case)
            only_current = set(current_by_case) - set(baseline_by_case)
            for tid in only_baseline:
                incomparable.append(
                    {"test_case_id": str(tid), "reason": "missing_in_current", "metric": metric}
                )
            for tid in only_current:
                incomparable.append(
                    {"test_case_id": str(tid), "reason": "missing_in_baseline", "metric": metric}
                )

            for tid in shared_ids:
                b_case = baseline_by_case[tid]
                c_case = current_by_case[tid]
                b_score = _score_value(baseline_scores_by_case.get(tid), metric)
                c_score = _score_value(current_scores_by_case.get(tid), metric)
                if b_score is None or c_score is None:
                    incomparable.append(
                        {
                            "test_case_id": str(tid),
                            "reason": "missing_metric_score",
                            "metric": metric,
                        }
                    )
                    continue

                case_delta = c_score - b_score
                reasons_case: list[str] = []

                if _case_passed(b_case) and c_case.status == CaseResultStatus.FAILED.value:
                    reasons_case.append("baseline_passed_current_failed")

                if case_delta < -policy.max_allowed_drop:
                    reasons_case.append("metric_drop_exceeded_threshold")

                if reasons_case:
                    metric_case_regressions += 1
                    regressed_ids.add(str(tid))
                    regressed_cases.append(
                        RegressedCase(
                            test_case_id=str(tid),
                            metric=metric,
                            baseline_score=b_score,
                            current_score=c_score,
                            delta=case_delta,
                            reason=";".join(reasons_case),
                        )
                    )

            if (
                policy.max_regressed_cases is not None
                and metric_case_regressions > policy.max_regressed_cases
            ):
                violated = True
                reasons.append(
                    f"regressed cases for {metric}: {metric_case_regressions} > "
                    f"max_regressed_cases {policy.max_regressed_cases}"
                )

            aggregate[metric] = AggregateMetricResult(
                baseline=baseline_avg,
                current=current_avg,
                delta=delta,
                threshold=policy.max_allowed_drop,
                min_aggregate_score=policy.min_aggregate_score,
                violated=violated,
                reasons=reasons,
            )
            if violated:
                any_violation = True

        status = RegressionStatus.FAIL if any_violation else RegressionStatus.PASS
        return RegressionResult(
            status=status,
            baseline_run_id=baseline_run.id,
            aggregate=aggregate,
            regressed_cases=regressed_cases,
            incomparable_cases=incomparable,
            notes=notes,
        )
