"""Pluggable metric registry for scoring case outputs."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass
class MetricContext:
    """Optional per-case context for metrics that need more than expected/actual."""

    input: dict[str, Any] | None = None


@dataclass
class MetricScore:
    name: str
    score: float
    passed: bool
    reason: str | None = None


class Metric(ABC):
    name: str

    @abstractmethod
    def score(
        self,
        actual: dict[str, Any] | None,
        expected: dict[str, Any] | None,
        context: MetricContext | None = None,
    ) -> MetricScore:
        raise NotImplementedError


def _extract_text(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return ""
    for key in ("output", "text", "answer", "content", "response"):
        if key in payload and payload[key] is not None:
            return str(payload[key]).strip()
    if len(payload) == 1:
        return str(next(iter(payload.values()))).strip()
    return str(payload).strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


class ExactMatchMetric(Metric):
    name = "exact_match"

    def score(
        self,
        actual: dict[str, Any] | None,
        expected: dict[str, Any] | None,
        context: MetricContext | None = None,
    ) -> MetricScore:
        a = _normalize(_extract_text(actual))
        e = _normalize(_extract_text(expected))
        ok = bool(e) and a == e
        return MetricScore(name=self.name, score=1.0 if ok else 0.0, passed=ok)


class StringSimilarityMetric(Metric):
    name = "string_similarity"

    def __init__(self, pass_threshold: float = 0.8):
        self.pass_threshold = pass_threshold

    def score(
        self,
        actual: dict[str, Any] | None,
        expected: dict[str, Any] | None,
        context: MetricContext | None = None,
    ) -> MetricScore:
        a = _normalize(_extract_text(actual))
        e = _normalize(_extract_text(expected))
        if not e:
            return MetricScore(name=self.name, score=0.0, passed=False)
        ratio = SequenceMatcher(None, a, e).ratio()
        return MetricScore(name=self.name, score=ratio, passed=ratio >= self.pass_threshold)


# Alias used in earlier docs / create-run examples
class SimilarityAlias(StringSimilarityMetric):
    name = "similarity"


_REGISTRY: dict[str, type[Metric]] = {
    ExactMatchMetric.name: ExactMatchMetric,
    StringSimilarityMetric.name: StringSimilarityMetric,
    SimilarityAlias.name: SimilarityAlias,
}


def _register_builtin_judge() -> None:
    # Lazy import avoids circular dependency at module load for non-judge paths.
    from app.judge.metric import LLMJudgeMetric

    _REGISTRY[LLMJudgeMetric.name] = LLMJudgeMetric


_register_builtin_judge()


def metric_score_value(metric_scores: dict[str, Any] | None, metric: str) -> float | None:
    """Extract a numeric score from a CaseResult.metric_scores entry."""
    if not metric_scores or metric not in metric_scores:
        return None
    entry = metric_scores[metric]
    if isinstance(entry, dict):
        if "score" not in entry:
            return None
        try:
            value = float(entry["score"])
        except (TypeError, ValueError):
            return None
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    try:
        value = float(entry)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def aggregate_metric_scores(results_scores: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Build run-level aggregates from CaseResult.metric_scores (reasons are not averaged)."""
    buckets: dict[str, list[float]] = {}
    for scores in results_scores:
        for name in scores:
            value = metric_score_value(scores, name)
            if value is not None:
                buckets.setdefault(name, []).append(value)
    return {
        name: {
            "average": sum(vals) / len(vals),
            "minimum": min(vals),
            "maximum": max(vals),
            "count": float(len(vals)),
        }
        for name, vals in sorted(buckets.items())
    }


class MetricRegistry:
    @staticmethod
    def list_metrics() -> list[str]:
        return sorted(_REGISTRY.keys())

    @staticmethod
    def has(name: str) -> bool:
        return name in _REGISTRY

    @staticmethod
    def get(name: str) -> Metric:
        if name not in _REGISTRY:
            raise KeyError(f"Unknown metric: {name}")
        return _REGISTRY[name]()

    @classmethod
    def score_case(
        cls,
        actual: dict[str, Any] | None,
        expected: dict[str, Any] | None,
        metric_names: list[str],
        context: MetricContext | None = None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name in metric_names:
            result = cls.get(name).score(actual, expected, context)
            entry: dict[str, Any] = {"score": result.score, "passed": result.passed}
            if result.reason is not None:
                entry["reason"] = result.reason
            out[name] = entry
        return out
