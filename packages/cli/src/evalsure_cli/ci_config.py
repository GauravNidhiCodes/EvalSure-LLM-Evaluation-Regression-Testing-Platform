"""Load and validate repository-level evalsure.yml configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evalsure_cli.exit_codes import EXIT_CONFIG


class CiConfigError(Exception):
    """Invalid or missing CI configuration. Maps to exit code 2."""

    exit_code = EXIT_CONFIG


_FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "apikey",
    "evalsure_api_key",
    "access_token",
    "password",
    "secret",
    "token",
    "authorization",
}


@dataclass
class EvalSureCiConfig:
    project_id: str
    experiment_id: str
    dataset_version_id: str
    metrics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "dataset_version_id": self.dataset_version_id,
            "metrics": list(self.metrics),
        }


def _reject_secrets(raw: dict[str, Any]) -> None:
    for key in raw:
        lowered = str(key).lower().replace("-", "_")
        if lowered in _FORBIDDEN_SECRET_KEYS or lowered.endswith("_api_key"):
            raise CiConfigError(
                f"Configuration must not contain secrets (found key '{key}'). "
                "Use EVALSURE_API_KEY / GitHub Actions secrets instead."
            )


def load_ci_config(path: Path) -> EvalSureCiConfig:
    if not path.exists():
        raise CiConfigError(f"Configuration file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CiConfigError(f"Could not read configuration file: {path}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CiConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if raw is None:
        raise CiConfigError(f"Configuration file is empty: {path}")
    if not isinstance(raw, dict):
        raise CiConfigError(f"Configuration root must be a mapping/object: {path}")

    _reject_secrets(raw)

    required = ("project_id", "experiment_id", "dataset_version_id")
    missing = [name for name in required if not raw.get(name)]
    if missing:
        raise CiConfigError(
            f"Missing required field(s): {', '.join(missing)}. "
            "Expected project_id, experiment_id, dataset_version_id."
        )

    metrics_raw = raw.get("metrics") or []
    if metrics_raw is None:
        metrics_raw = []
    if not isinstance(metrics_raw, list):
        raise CiConfigError("metrics must be a list of strings")
    metrics = [str(m).strip() for m in metrics_raw if str(m).strip()]

    return EvalSureCiConfig(
        project_id=str(raw["project_id"]).strip(),
        experiment_id=str(raw["experiment_id"]).strip(),
        dataset_version_id=str(raw["dataset_version_id"]).strip(),
        metrics=metrics,
    )
