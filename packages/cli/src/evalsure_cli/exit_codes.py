"""Exit codes for EVALSURE CI / CLI process status."""

from __future__ import annotations

EXIT_PASS = 0
"""Evaluation completed; regression PASS (or NOT_EVALUATED — no policy failure)."""

EXIT_REGRESSION_FAIL = 1
"""Evaluation completed but regression status is FAIL."""

EXIT_CONFIG = 2
"""Configuration, usage, or local file/YAML error."""

EXIT_API = 3
"""API, network, or authentication error."""
