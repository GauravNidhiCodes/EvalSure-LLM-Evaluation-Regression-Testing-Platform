"""Structured logging helpers — never log secrets."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(x-api-key\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(bearer\s+)(\S+)"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(jwt[_-]?secret\s*[:=]\s*)(\S+)"),
    re.compile(r"evs_[A-Za-z0-9_-]{16,}"),
]


def get_request_id() -> str | None:
    return request_id_ctx.get()


def set_request_id(value: str | None):
    return request_id_ctx.set(value)


def reset_request_id(token) -> None:
    request_id_ctx.reset(token)


def redact_secrets(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            out = pattern.sub(r"\1[REDACTED]", out)
        else:
            out = pattern.sub("[REDACTED_API_KEY]", out)
    return out


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        return True


def configure_logging(*, debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    if not any(isinstance(f, RequestIdFilter) for h in root.handlers for f in h.filters):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s"
            )
        )
        handler.addFilter(RequestIdFilter())
        root.handlers.clear()
        root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").addFilter(RequestIdFilter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        key_l = key.lower()
        if any(s in key_l for s in ("password", "secret", "api_key", "token", "authorization")):
            continue
        parts.append(f"{key}={value}")
    logger.info(" ".join(parts))
