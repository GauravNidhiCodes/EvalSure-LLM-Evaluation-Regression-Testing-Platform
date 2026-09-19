from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=255)


class ApiKeyCreated(BaseModel):
    """Plaintext `api_key` is returned only at creation time."""

    id: UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["active", "revoked"]:
        return "revoked" if self.revoked_at is not None else "active"
