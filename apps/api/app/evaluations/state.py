"""Evaluation run status transition rules."""

from __future__ import annotations

from app.core.errors import ErrorCode, app_http_error
from app.core.models import RunStatus
from fastapi import status

# Allowed transitions: from -> frozenset(to)
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    RunStatus.PENDING.value: frozenset({RunStatus.RUNNING.value, RunStatus.FAILED.value}),
    RunStatus.RUNNING.value: frozenset({RunStatus.COMPLETED.value, RunStatus.FAILED.value}),
    RunStatus.COMPLETED.value: frozenset(),
    RunStatus.FAILED.value: frozenset(),
}


def assert_transition(current: str, new: str) -> None:
    """Raise INVALID_RUN_STATE if the transition is not allowed."""
    if current == new:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise app_http_error(
            status.HTTP_409_CONFLICT,
            ErrorCode.INVALID_RUN_STATE,
            f"Invalid run status transition: {current} → {new}",
        )


def ensure_accepts_results(current: str) -> None:
    if current in {RunStatus.COMPLETED.value, RunStatus.FAILED.value}:
        raise app_http_error(
            status.HTTP_409_CONFLICT,
            ErrorCode.INVALID_RUN_STATE,
            f"Run is {current} and cannot accept new results",
        )
    if current not in {RunStatus.PENDING.value, RunStatus.RUNNING.value}:
        raise app_http_error(
            status.HTTP_409_CONFLICT,
            ErrorCode.INVALID_RUN_STATE,
            f"Invalid run status: {current}",
        )
