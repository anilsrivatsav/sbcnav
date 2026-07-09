from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    success: bool = True
    message: str = ""
    data: T


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=255)


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)
    sort_by: str | None = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")
    search: str | None = None

