"""llm_judge metric — scores actual vs expected via an LLM judge provider."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.judge.errors import JudgeEvaluationError
from app.judge.parsing import parse_judge_response
from app.judge.prompt import build_judge_prompt
from app.judge.provider import JudgeCompletion, get_judge_provider
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
        settings = get_settings()
        started = time.perf_counter()
        try:
            completion = provider.complete(prompt)
        except JudgeEvaluationError as exc:
            if context is not None:
                context.model_calls.append(
                    {
                        "provider": getattr(provider, "name", "unknown"),
                        "model": getattr(provider, "model", None) or settings.judge_model,
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "error": str(exc),
                    }
                )
            raise
        except Exception as exc:  # noqa: BLE001
            if context is not None:
                context.model_calls.append(
                    {
                        "provider": getattr(provider, "name", "unknown"),
                        "model": getattr(provider, "model", None) or settings.judge_model,
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "error": str(exc),
                    }
                )
            raise JudgeEvaluationError(f"Judge provider failed: {exc}") from exc

        if not isinstance(completion, JudgeCompletion):
            # Defensive: older-style string responses
            completion = JudgeCompletion(
                content=str(completion),
                provider=getattr(provider, "name", "unknown"),
                model=getattr(provider, "model", None),
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        if context is not None:
            context.model_calls.append(completion.to_model_call_data())

        score, reason = parse_judge_response(completion.content)
        return MetricScore(
            name=self.name,
            score=score,
            passed=score >= self.pass_threshold,
            reason=reason,
        )
