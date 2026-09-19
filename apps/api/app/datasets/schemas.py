from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TestCaseIn(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    input: dict[str, Any]
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("external_id")
    @classmethod
    def strip_external_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("external_id must not be blank")
        return cleaned

    @field_validator("input")
    @classmethod
    def input_must_be_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict) or len(value) == 0:
            raise ValueError("input must be a non-empty object")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag and tag.strip()]


class DatasetVersionCreate(BaseModel):
    test_cases: list[TestCaseIn]

    @model_validator(mode="after")
    def reject_empty_and_duplicate_ids(self) -> Self:
        if not self.test_cases:
            raise ValueError("test_cases must not be empty")
        ids = [case.external_id for case in self.test_cases]
        duplicates = sorted({eid for eid in ids if ids.count(eid) > 1})
        if duplicates:
            raise ValueError(f"duplicate external_id values: {', '.join(duplicates)}")
        return self


class DatasetVersionOut(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    content_hash: str
    created_at: datetime
    test_case_count: int | None = None

    model_config = {"from_attributes": True}


class TestCaseOut(BaseModel):
    id: UUID
    external_id: str
    input: dict[str, Any]
    expected: dict[str, Any] | None
    metadata: dict[str, Any]
    tags: list[str]

    model_config = {"from_attributes": True}
