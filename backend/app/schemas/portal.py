"""Response models for the read-only portal API used by the frontend."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class OrgRef(BaseModel):
    org_id: str
    name: str


class OrganizationSummary(OrgRef):
    run_count: int
    finding_count: int
    high_severity_count: int
    last_survey_at: datetime | None
    last_site_name: str | None


class RunSummary(BaseModel):
    run_id: str
    site_name: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    aircraft_id: str | None
    finding_count: int
    counts_by_type: dict[str, int]
    counts_by_severity: dict[str, int]
    data_warning_count: int
    findings_with_warnings: int


class DataWarningOut(BaseModel):
    code: str
    message: str | None
    geometry: dict[str, Any] | None


class RunDetail(RunSummary):
    organization: OrgRef
    operator: str | None
    software_version: str
    schema_version: str
    local_frame_origin: dict[str, Any] | None
    flight_path: dict[str, Any] | None
    data_warnings: list[DataWarningOut]
    ingested_at: datetime


class QualityWarningOut(BaseModel):
    code: str
    message: str | None = None


class FindingListItem(BaseModel):
    finding_id: str
    detected_at: datetime
    defect_type: str
    subtype: str | None
    severity: str | None
    confidence: float | None
    detection_source: str | None
    lat: float | None
    lon: float | None
    gps_accuracy_m: float | None
    local_x_m: float | None
    local_y_m: float | None
    measurements: dict[str, Any]
    warning_codes: list[str]
    evidence_count: int
    thumb_url: str | None


class EvidenceOut(BaseModel):
    file: str
    kind: str
    caption: str | None
    captured_at: datetime | None
    content_type: str
    size_bytes: int
    is_image: bool
    width_px: int | None
    height_px: int | None
    url: str
    preview_url: str | None
    thumb_url: str | None
    bounding_boxes: list[dict[str, Any]]


class FindingDetail(FindingListItem):
    run_id: str
    site_name: str
    organization: OrgRef
    description: str | None
    alt_m: float | None
    quality_warnings: list[QualityWarningOut]
    evidence: list[EvidenceOut]
    prev_finding_id: str | None
    next_finding_id: str | None
    position_in_run: int
    findings_in_run: int
