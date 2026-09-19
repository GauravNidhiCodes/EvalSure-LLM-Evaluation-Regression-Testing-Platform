"""Safe parsing of LLM judge responses into score + reason."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.judge.errors import JudgeEvaluationError

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise JudgeEvaluationError("Judge response is empty")

    fence = _FENCE_RE.search(text)
    if fence:
        return fence.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise JudgeEvaluationError("Judge response does not contain JSON object")


def _validate_score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JudgeEvaluationError(f"Judge score must be numeric, got {type(value).__name__}")
    score = float(value)
    if math.isnan(score) or math.isinf(score):
        raise JudgeEvaluationError("Judge score must be a finite number")
    if score < 0.0 or score > 1.0:
        raise JudgeEvaluationError(f"Judge score {score} is outside required range [0.0, 1.0]")
    return score


def parse_judge_response(raw: str) -> tuple[float, str]:
    """Parse judge output into (score, reason). Rejects invalid scores; never clamps."""
    payload_text = _extract_json_text(raw)
    try:
        data = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise JudgeEvaluationError(f"Judge response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise JudgeEvaluationError("Judge JSON must be an object")
    if "score" not in data:
        raise JudgeEvaluationError("Judge JSON missing required field 'score'")

    score = _validate_score(data["score"])
    reason_raw = data.get("reason", "")
    if reason_raw is None:
        reason = ""
    elif not isinstance(reason_raw, str):
        reason = str(reason_raw)
    else:
        reason = reason_raw.strip()
    return score, reason
