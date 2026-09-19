"""Trace API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceEventOut(BaseModel):
    id: UUID
    run_id: UUID
    case_result_id: UUID | None = None
    event_type: str
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class RunTracesOut(BaseModel):
    run_id: UUID
    events: list[TraceEventOut]
    page: int = 1
    page_size: int = 50
    total: int = 0


class CaseTracesOut(BaseModel):
    run_id: UUID
    case_result_id: UUID
    events: list[TraceEventOut]
