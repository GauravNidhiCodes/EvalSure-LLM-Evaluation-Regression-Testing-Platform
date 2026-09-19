"""llm_judge metric — scores actual vs expected via an LLM judge provider."""

from __future__ import annotations

from typing import Any

from app.judge.errors import JudgeEvaluationError
from app.judge.parsing import parse_judge_response
from app.judge.prompt import build_judge_prompt
from app.judge.provider import get_judge_provider
from app.metrics.registry import Metric, MetricContext, MetricScore


class LLMJudgeMetric(Metric):
    name = "llm_judge"

    def __init__(self, pass_threshold: float = 0.7) -> None:
        self.pass_threshold = pass_threshold

    def score(
        self,
        actual: dict[str, Any] | None,
        expected: dict[str, Any] | None,
        context: MetricContext | None = None,
    ) -> MetricScore:
        input_data = context.input if context is not None else None
        prompt = build_judge_prompt(input_data=input_data, expected=expected, actual=actual)
        provider = get_judge_provider()
        try:
            raw = provider.complete(prompt)
        except JudgeEvaluationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise JudgeEvaluationError(f"Judge provider failed: {exc}") from exc

        score, reason = parse_judge_response(raw)
        return MetricScore(
            name=self.name,
            score=score,
            passed=score >= self.pass_threshold,
            reason=reason,
        )
