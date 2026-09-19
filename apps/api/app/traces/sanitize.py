"""Sanitize trace payloads — never persist secrets or credentials."""

from __future__ import annotations

from typing import Any

# Exact keys / suffixes that indicate secrets. Do NOT match "token" as a substring
# (would strip legitimate input_tokens / output_tokens / total_tokens).
_SECRET_EXACT = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "credential",
    "credentials",
    "access_token",
    "refresh_token",
    "bearer",
    "jwt",
    "jwt_secret",
    "judge_api_key",
    "token",
}

_SECRET_SUFFIXES = ("_api_key", "_secret", "_password", "_credential")

_MAX_STRING_LEN = 2000
_MAX_STACK_LEN = 500
_MAX_TRACE_PAYLOAD_BYTES = 32_768  # ~32 KiB after sanitization


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _SECRET_EXACT:
        return True
    if any(lowered.endswith(suffix) for suffix in _SECRET_SUFFIXES):
        return True
    if "authorization" in lowered:
        return True
    return False


def sanitize_trace_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Deep-copy and strip secrets; truncate oversized strings / payloads."""
    if not data:
        return {}
    cleaned = _sanitize_value(data)
    if not isinstance(cleaned, dict):
        return {}
    # Bound total JSON size to protect the database from huge blobs.
    try:
        import json

        encoded = json.dumps(cleaned, default=str)
        if len(encoded.encode("utf-8")) > _MAX_TRACE_PAYLOAD_BYTES:
            return {
                "truncated": True,
                "message": "Trace payload exceeded size limit and was truncated",
                "keys": sorted(str(k) for k in cleaned.keys())[:50],
            }
    except (TypeError, ValueError):
        return {"truncated": True, "message": "Trace payload could not be serialized"}
    return cleaned


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                continue
            out[str(key)] = _sanitize_value(item)
        return out
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        if len(value) > _MAX_STRING_LEN:
            return value[:_MAX_STRING_LEN] + "…[truncated]"
        return value
    return value


def sanitize_error_message(message: str | None, *, error_type: str | None = None) -> dict[str, str]:
    text = (message or "unknown error").strip()
    if len(text) > _MAX_STACK_LEN:
        text = text[:_MAX_STACK_LEN] + "…[truncated]"
    payload = {"message": text}
    if error_type:
        payload["error_type"] = error_type
    return payload
