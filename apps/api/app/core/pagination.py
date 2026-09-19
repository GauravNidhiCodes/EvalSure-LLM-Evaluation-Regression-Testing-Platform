"""Pagination helpers — consistent ?page=&page_size= convention."""

from __future__ import annotations

from typing import Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class PageParams(BaseModel):
    page: int = Field(DEFAULT_PAGE, ge=1)
    page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


def page_params(
    page: int = Query(DEFAULT_PAGE, ge=1, description="1-based page number"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    ),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


def paginate(items: Sequence[T], total: int, params: PageParams) -> Page[T]:
    return Page(items=list(items), page=params.page, page_size=params.page_size, total=total)
