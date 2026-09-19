"""Stable API error codes and exceptions."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

# Prefer Starlette's non-deprecated alias when available.
_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", None)


class ErrorCode:
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    DATASET_NOT_FOUND = "DATASET_NOT_FOUND"
    DATASET_VERSION_NOT_FOUND = "DATASET_VERSION_NOT_FOUND"
    EXPERIMENT_NOT_FOUND = "EXPERIMENT_NOT_FOUND"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    CASE_RESULT_NOT_FOUND = "CASE_RESULT_NOT_FOUND"
    API_KEY_NOT_FOUND = "API_KEY_NOT_FOUND"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    INVALID_METRIC = "INVALID_METRIC"
    INVALID_RUN_STATE = "INVALID_RUN_STATE"
    DUPLICATE_RESULT = "DUPLICATE_RESULT"
    REGRESSION_NOT_EVALUATED = "REGRESSION_NOT_EVALUATED"
    CONFLICT = "CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"


class AppError(Exception):
    """Application error with stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)

    def as_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return body


def app_http_error(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Raise-compatible HTTPException carrying structured detail for the error handler."""
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return HTTPException(status_code=status_code, detail=payload)


_STATUS_DEFAULT_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.INTERNAL_ERROR,
}
if _UNPROCESSABLE is not None:
    _STATUS_DEFAULT_CODES[_UNPROCESSABLE] = ErrorCode.VALIDATION_ERROR


def normalize_http_detail(detail: Any, status_code: int) -> tuple[str, str, dict[str, Any] | None]:
    """Return (code, message, details) from FastAPI HTTPException.detail."""
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        details = detail.get("details") if isinstance(detail.get("details"), dict) else None
        return str(detail["code"]), str(detail["message"]), details
    if isinstance(detail, str):
        code = _STATUS_DEFAULT_CODES.get(status_code, ErrorCode.BAD_REQUEST)
        lowered = detail.lower()
        if "project" in lowered and "not found" in lowered:
            code = ErrorCode.PROJECT_NOT_FOUND
        elif "dataset version" in lowered and "not found" in lowered:
            code = ErrorCode.DATASET_VERSION_NOT_FOUND
        elif "dataset" in lowered and "not found" in lowered:
            code = ErrorCode.DATASET_NOT_FOUND
        elif "experiment" in lowered and "not found" in lowered:
            code = ErrorCode.EXPERIMENT_NOT_FOUND
        elif "evaluation run" in lowered and "not found" in lowered:
            code = ErrorCode.RUN_NOT_FOUND
        elif "run" in lowered and "not found" in lowered:
            code = ErrorCode.RUN_NOT_FOUND
        elif "api key" in lowered and "not found" in lowered:
            code = ErrorCode.API_KEY_NOT_FOUND
        elif "policy" in lowered and "not found" in lowered:
            code = ErrorCode.POLICY_NOT_FOUND
        elif "case result" in lowered and "not found" in lowered:
            code = ErrorCode.CASE_RESULT_NOT_FOUND
        elif "invalid run" in lowered or "cannot accept" in lowered or "must be completed" in lowered:
            code = ErrorCode.INVALID_RUN_STATE
        elif "already submitted" in lowered or "duplicate" in lowered:
            code = ErrorCode.DUPLICATE_RESULT
        elif "forbidden" in lowered or "mismatch" in lowered:
            code = ErrorCode.FORBIDDEN
        elif "not authenticated" in lowered or "invalid token" in lowered or "invalid api key" in lowered:
            code = ErrorCode.UNAUTHORIZED
        elif "invalid metric" in lowered:
            code = ErrorCode.INVALID_METRIC
        return code, detail, None
    return _STATUS_DEFAULT_CODES.get(status_code, ErrorCode.BAD_REQUEST), str(detail), None
