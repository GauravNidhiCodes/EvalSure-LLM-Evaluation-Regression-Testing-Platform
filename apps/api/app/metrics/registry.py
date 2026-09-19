"""Pluggable metric registry for scoring case outputs (no LLM-as-judge)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass
class MetricScore:
    name: str
    score: float
    passed: bool


class Metric(ABC):
    name: str

    @abstractmethod
    def score(self, actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> MetricScore:
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

    def score(self, actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> MetricScore:
        a = _normalize(_extract_text(actual))
        e = _normalize(_extract_text(expected))
        ok = bool(e) and a == e
        return MetricScore(name=self.name, score=1.0 if ok else 0.0, passed=ok)


class StringSimilarityMetric(Metric):
    name = "string_similarity"

    def __init__(self, pass_threshold: float = 0.8):
        self.pass_threshold = pass_threshold

    def score(self, actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> MetricScore:
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
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name in metric_names:
            result = cls.get(name).score(actual, expected)
            out[name] = {"score": result.score, "passed": result.passed}
        return out
