"""Deterministic content hashing for immutable dataset versions."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize_test_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build a stable, order-independent representation for hashing.

    Cases are sorted by external_id. Nested objects use sorted JSON keys.
    """
    normalized: list[dict[str, Any]] = []
    for case in cases:
        normalized.append(
            {
                "external_id": case["external_id"],
                "input": case["input"],
                "expected": case.get("expected"),
                "metadata": case.get("metadata") or {},
                "tags": list(case.get("tags") or []),
            }
        )
    normalized.sort(key=lambda c: c["external_id"])
    return normalized


def content_hash_for_cases(cases: list[dict[str, Any]]) -> str:
    canonical = canonicalize_test_cases(cases)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
