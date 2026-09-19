"""Errors raised when the LLM judge cannot produce a valid score."""


class JudgeEvaluationError(Exception):
    """Judge call or response parsing failed — never silently scored."""
