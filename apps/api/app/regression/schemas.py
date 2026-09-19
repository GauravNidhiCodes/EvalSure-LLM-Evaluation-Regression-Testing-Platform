from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.models import RegressionStatus
from app.metrics.registry import MetricRegistry


class RegressionPolicyCreate(BaseModel):
    metric_name: str = Field(min_length=1, max_length=128)
    max_allowed_drop: float
    min_aggregate_score: float | None = None
    max_regressed_cases: int | None = None

    @field_validator("metric_name")
    @classmethod
    def metric_must_exist(cls, value: str) -> str:
        name = value.strip()
        if not MetricRegistry.has(name):
            raise ValueError(
                f"Unknown metric '{name}'. Available: {', '.join(MetricRegistry.list_metrics())}"
            )
        return name

    @field_validator("max_allowed_drop")
    @classmethod
    def validate_drop(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("max_allowed_drop must be between 0 and 1 inclusive")
        return value

    @field_validator("min_aggregate_score")
    @classmethod
    def validate_min(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 1):
            raise ValueError("min_aggregate_score must be between 0 and 1 inclusive")
        return value

    @field_validator("max_regressed_cases")
    @classmethod
    def validate_max_cases(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("max_regressed_cases must be >= 0")
        return value


class RegressionPolicyOut(BaseModel):
    id: UUID
    experiment_id: UUID
    metric_name: str
    max_allowed_drop: float
    min_aggregate_score: float | None
    max_regressed_cases: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegressionInfo(BaseModel):
    status: RegressionStatus
    baseline_run_id: UUID | None = None
    regressed_case_count: int = 0
    aggregate: dict[str, Any] = Field(default_factory=dict)
    regressed_cases: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    incomparable_cases: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvaluateRegressionOut(BaseModel):
    run_id: UUID
    evaluation_status: str
    regression: RegressionInfo
