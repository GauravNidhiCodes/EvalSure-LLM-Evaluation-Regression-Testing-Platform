from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.models import CaseResultStatus, RegressionStatus, RunStatus
from app.regression.schemas import RegressionInfo


class EvaluationRunCreate(BaseModel):
    dataset_version_id: UUID
    experiment_id: UUID | None = None
    metrics: list[str] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunCreated(BaseModel):
    id: UUID
    run_id: UUID
    status: RunStatus
    experiment_id: UUID | None = None

    model_config = {"from_attributes": True}


class DatasetVersionSummary(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    content_hash: str

    model_config = {"from_attributes": True}


class EvaluationRunOut(BaseModel):
    id: UUID
    run_id: UUID
    project_id: UUID
    experiment_id: UUID | None = None
    is_baseline: bool = False
    dataset_version_id: UUID
    dataset_version: DatasetVersionSummary | None = None
    status: RunStatus
    config_snapshot: dict[str, Any]
    error_message: str | None = None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    total_cases: int
    completed_cases: int
    failed_cases: int
    pending_cases: int
    regression_status: RegressionStatus = RegressionStatus.NOT_EVALUATED
    baseline_run_id: UUID | None = None
    regression: RegressionInfo | None = None


class CaseResultIn(BaseModel):
    test_case_id: UUID
    actual_output: dict[str, Any] | None = None
    error_message: str | None = None

    @field_validator("actual_output")
    @classmethod
    def actual_output_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and (not isinstance(value, dict) or len(value) == 0):
            raise ValueError("actual_output must be a non-empty object when provided")
        return value

    @model_validator(mode="after")
    def require_output_or_error(self) -> Self:
        if self.actual_output is None and not self.error_message:
            raise ValueError("each result requires actual_output or error_message")
        return self


class EvaluationResultsSubmit(BaseModel):
    results: list[CaseResultIn]

    @model_validator(mode="after")
    def reject_empty_and_duplicate_ids(self) -> Self:
        if not self.results:
            raise ValueError("results must not be empty")
        ids = [item.test_case_id for item in self.results]
        duplicates = sorted({str(tid) for tid in ids if ids.count(tid) > 1})
        if duplicates:
            raise ValueError(f"duplicate test_case_id values in batch: {', '.join(duplicates)}")
        return self


class CaseResultOut(BaseModel):
    id: UUID
    run_id: UUID
    test_case_id: UUID
    external_id: str | None = None
    actual_output: dict[str, Any] | None
    status: CaseResultStatus
    metric_scores: dict[str, Any]
    is_regression: bool = False
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationResultsSubmitOut(BaseModel):
    run: EvaluationRunOut
    accepted: int
