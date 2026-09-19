"""Controlled evaluation trace event types."""

from __future__ import annotations

import enum


class TraceEventType(str, enum.Enum):
    """Meaningful evaluation lifecycle events (extensible)."""

    RUN_STARTED = "run_started"
    CASE_STARTED = "case_started"
    MODEL_CALL = "model_call"
    METRIC_EVALUATION = "metric_evaluation"
    CASE_COMPLETED = "case_completed"
    CASE_FAILED = "case_failed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
