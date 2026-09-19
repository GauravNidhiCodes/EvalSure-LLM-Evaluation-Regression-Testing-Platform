"""Load evaluation result JSON for CI submission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evalsure_cli.exit_codes import EXIT_CONFIG


class CiResultsError(Exception):
    """Invalid or missing results file. Maps to exit code 2."""

    exit_code = EXIT_CONFIG


def _normalize_actual_output(value: Any) -> Any:
    """Backend requires actual_output as an object when provided.

    Strings are wrapped as ``{"text": "..."}`` for CI convenience.
    """
    if isinstance(value, str):
        return {"text": value}
    return value


def load_results_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise CiResultsError(f"Results file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CiResultsError(f"Could not read results file: {path}") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CiResultsError(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, dict) and "results" in payload:
        results = payload["results"]
    elif isinstance(payload, list):
        results = payload
    else:
        raise CiResultsError(
            "Results JSON must be a list or an object with a 'results' array"
        )

    if not isinstance(results, list) or not results:
        raise CiResultsError("results must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise CiResultsError(f"results[{index}] must be an object")
        if "test_case_id" not in item:
            raise CiResultsError(f"results[{index}] missing test_case_id")
        entry = dict(item)
        if "actual_output" in entry and entry["actual_output"] is not None:
            entry["actual_output"] = _normalize_actual_output(entry["actual_output"])
        if entry.get("actual_output") is None and not entry.get("error_message"):
            raise CiResultsError(
                f"results[{index}] requires actual_output or error_message"
            )
        normalized.append(entry)
    return normalized
