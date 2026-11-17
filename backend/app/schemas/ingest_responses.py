"""Responses returned to the data sender by the ingestion API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    path: str = Field(description="Where the problem is, e.g. features[3].properties.evidence")
    message: str


class ErrorResponse(BaseModel):
    detail: str
    errors: list[ApiError] = []
    ingestion_id: str | None = None


class IngestionAccepted(BaseModel):
    ingestion_id: str
    run_id: str
    status: str = Field(examples=["pending_files"])
    files_expected: list[str]
    upload_url_template: str = Field(
        description="PUT each file's raw bytes to this URL, replacing {file} with the file name."
    )
    complete_url: str


class FileReceived(BaseModel):
    ingestion_id: str
    file: str
    size_bytes: int
    content_type: str
    width_px: int | None
    height_px: int | None
    files_remaining: list[str]


class IngestionStatus(BaseModel):
    ingestion_id: str
    status: str
    run_id: str | None
    received_at: datetime
    completed_at: datetime | None
    files_expected: list[str]
    files_received: list[str]
    files_remaining: list[str]
    errors: list[dict[str, Any]] | None


class IngestionCompleted(BaseModel):
    ingestion_id: str
    run_id: str
    status: str = Field(examples=["completed"])
    organization_id: str
    findings: int
    replaced_previous: bool
    portal_path: str
