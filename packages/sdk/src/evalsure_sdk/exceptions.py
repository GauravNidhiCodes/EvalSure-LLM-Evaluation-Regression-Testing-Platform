"""SDK exception hierarchy — never include API keys in messages."""

from __future__ import annotations

from typing import Any


def _redact(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted


class EvalSureError(Exception):
    """Base SDK error."""


class EvalSureAPIError(EvalSureError):
    """Non-success HTTP response from the EVALSURE API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"HTTP {self.status_code}: {self.args[0]}"
        return str(self.args[0])


class EvalSureAuthenticationError(EvalSureAPIError):
    """401 / invalid credentials."""


class EvalSureValidationError(EvalSureAPIError):
    """400 / 422 validation errors."""


class EvalSureNotFoundError(EvalSureAPIError):
    """404 not found."""


class EvalSureTimeoutError(EvalSureError):
    """HTTP timeout or connection failure."""
