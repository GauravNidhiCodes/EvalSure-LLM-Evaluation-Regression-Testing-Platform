"""Typed response models matching the EVALSURE REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID
    created_at: datetime


class Dataset(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DatasetVersion(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    content_hash: str
    created_at: datetime
    test_case_count: int | None = None


class TestCase(BaseModel):
    id: UUID
    external_id: str
    input: dict[str, Any]
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class Experiment(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    baseline_run_id: UUID | None = None
    created_at: datetime


class DatasetVersionSummary(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    content_hash: str


class RegressionInfo(BaseModel):
    status: str
    baseline_run_id: UUID | None = None
    regressed_case_count: int = 0
    aggregate: dict[str, Any] = Field(default_factory=dict)
    regressed_cases: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    incomparable_cases: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvaluationRun(BaseModel):
    id: UUID
    run_id: UUID
    project_id: UUID
    experiment_id: UUID | None = None
    is_baseline: bool = False
    dataset_version_id: UUID
    dataset_version: DatasetVersionSummary | None = None
    status: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    pending_cases: int = 0
    regression_status: str = "NOT_EVALUATED"
    baseline_run_id: UUID | None = None
    regression: RegressionInfo | None = None
    metric_aggregates: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunCreated(BaseModel):
    id: UUID
    run_id: UUID
    status: str
    experiment_id: UUID | None = None


class CaseResult(BaseModel):
    id: UUID
    run_id: UUID
    test_case_id: UUID
    external_id: str | None = None
    actual_output: dict[str, Any] | None = None
    status: str
    metric_scores: dict[str, Any] = Field(default_factory=dict)
    is_regression: bool = False
    error_message: str | None = None
    created_at: datetime


class EvaluationResultsSubmitResult(BaseModel):
    run: EvaluationRun
    accepted: int


class RegressionPolicy(BaseModel):
    id: UUID
    experiment_id: UUID
    metric_name: str
    max_allowed_drop: float
    min_aggregate_score: float | None = None
    max_regressed_cases: int | None = None
    created_at: datetime


class EvaluateRegressionResult(BaseModel):
    run_id: UUID
    evaluation_status: str
    regression: RegressionInfo


class TraceEvent(BaseModel):
    id: UUID
    run_id: UUID
    case_result_id: UUID | None = None
    event_type: str
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RunTraces(BaseModel):
    run_id: UUID
    events: list[TraceEvent]


class CaseTraces(BaseModel):
    run_id: UUID
    case_result_id: UUID
    events: list[TraceEvent]
