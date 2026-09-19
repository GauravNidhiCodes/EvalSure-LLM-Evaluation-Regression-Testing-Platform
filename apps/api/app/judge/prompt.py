"""Deterministic LLM-as-a-judge prompt template."""

from __future__ import annotations

import json
from typing import Any

JUDGE_SYSTEM_INSTRUCTION = (
    "You are a careful evaluation judge. Respond with valid JSON only. "
    "Do not invent facts. Evaluate only the supplied input, expected output, and actual output."
)

JUDGE_PROMPT_TEMPLATE = """\
Evaluate the actual output against the expected/reference output for the given input.

Rules:
- Do not invent facts beyond the supplied material.
- Evaluate only the supplied input, expected output, and actual output.
- Return valid JSON with exactly these keys: "score" and "reason".
- "score" must be a number between 0.0 and 1.0 (inclusive).
- "reason" must be a concise explanation of the score.
- Do not wrap the JSON in markdown unless necessary; prefer raw JSON.

Input:
{input_json}

Expected output:
{expected_json}

Actual output:
{actual_json}

Respond with JSON of the form:
{{"score": 0.0, "reason": "..."}}
"""


def build_judge_prompt(
    *,
    input_data: dict[str, Any] | None,
    expected: dict[str, Any] | None,
    actual: dict[str, Any] | None,
) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(
        input_json=json.dumps(input_data if input_data is not None else {}, ensure_ascii=False),
        expected_json=json.dumps(expected if expected is not None else {}, ensure_ascii=False),
        actual_json=json.dumps(actual if actual is not None else {}, ensure_ascii=False),
    )
