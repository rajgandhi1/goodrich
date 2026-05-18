from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import JobStatus


class ExtractionCreate(BaseModel):
    source_type: str = "email"
    text: str | None = None
    quote_id: str | None = None
    customer: str = ""
    project_ref: str = ""
    api_key: str | None = None


class ExtractionAccepted(BaseModel):
    job_id: str
    status: JobStatus


class JobRead(BaseModel):
    id: str
    org_id: str
    status: JobStatus
    source_type: str
    quote_id: str | None = None
    progress: float = 0.0
    message: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    skipped_count: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobStatusRead(BaseModel):
    id: str
    status: JobStatus
    source_type: str
    quote_id: str | None = None
    progress: float = 0.0
    message: str = ""
    parsed_count: int = 0
    skipped_count: int = 0
    error: str | None = None
    updated_at: datetime
