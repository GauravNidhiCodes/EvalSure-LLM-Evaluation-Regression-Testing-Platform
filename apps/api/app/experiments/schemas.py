from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ExperimentOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    baseline_run_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
