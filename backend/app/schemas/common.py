"""Shared schema helpers and the unified error envelope."""

from __future__ import annotations

import json
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for schemas read from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


def _load_json_text(value: Any) -> Any:
    """Decode a JSON string stored in a TEXT column.

    Models persist dicts as JSON text for SQLite/MySQL portability; the API
    exposes them as real objects. Malformed or empty values become None rather
    than raising, so one bad row cannot break a whole list response.
    """
    if value is None or isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


JsonText = Annotated[Any, BeforeValidator(_load_json_text)]
"""A JSON object stored as TEXT in the database."""


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any = None


class ErrorResponse(BaseModel):
    """Every API error uses this envelope (see app/core/errors.py)."""

    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class Message(BaseModel):
    message: str
