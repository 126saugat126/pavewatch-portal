"""Ingestion contract: the GeoJSON FeatureCollection the processing pipeline sends.

This module is the single source of truth. The API docs page, the downloadable
JSON Schema (``GET /api/v1/ingest/schema``) and server-side validation are all
generated from these classes, so they cannot drift apart.

Strictness: our own objects (``run``, ``properties``, evidence, ...) reject
unknown fields so typos are caught early. The outer GeoJSON wrappers allow
extra standard members (e.g. ``bbox``, ``id``).
"""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"

DefectType = Literal["pothole", "crack", "depression", "raised_area", "vertical_step", "other"]
Severity = Literal["low", "medium", "high"]
DetectionSource = Literal["image", "lidar", "fused"]
RunStatus = Literal["complete", "incomplete"]

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$", examples=["northgate-roads"])]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")]
FileName = Annotated[
    str,
    Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
        description="Plain file name (no folders). Unique within the run.",
        examples=["F-0001_raw.jpg"],
    ),
]
Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$", examples=["POSE_LOW_CONFIDENCE"])]
Probability = Annotated[float, Field(ge=0, le=1)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Lenient(BaseModel):
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------- run section


class Company(Strict):
    company_id: Slug = Field(description="Stable identifier of the customer company (lowercase, digits, dashes).")
    name: str = Field(min_length=1, max_length=200)


class LocalFrameOrigin(Strict):
    """Where the drone's local x/y frame starts. x points along ``heading_deg`` (0 = north, clockwise)."""

    lat: Latitude
    lon: Longitude
    alt_m: float | None = None
    heading_deg: float | None = Field(default=None, ge=0, lt=360)


class LineString(Lenient):
    type: Literal["LineString"]
    coordinates: list[Annotated[list[float], Field(min_length=2, max_length=3)]] = Field(min_length=2)


class DataWarning(Strict):
    code: Code = Field(description="e.g. NOT_SCANNED, POSE_LOW_CONFIDENCE, SCAN_IMAGE_MISALIGNED, NO_LIDAR_COVERAGE")
    message: str | None = None
    geometry: dict[str, Any] | None = Field(
        default=None, description="Optional GeoJSON geometry (usually a Polygon) of the affected area."
    )

    @field_validator("geometry")
    @classmethod
    def _geometry_type(cls, v: dict[str, Any] | None):
        if v is None:
            return v
        allowed = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
        if v.get("type") not in allowed:
            raise ValueError(f"geometry.type must be one of {sorted(allowed)}")
        if not isinstance(v.get("coordinates"), list):
            raise ValueError("geometry.coordinates must be an array")
        return v


class RunInfo(Strict):
    run_id: Identifier = Field(description="Globally unique survey run id.", examples=["PW-20261114-1502-A1"])
    company: Company
    site_name: str = Field(min_length=1, max_length=200)
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    status: RunStatus = Field(description="'incomplete' if the flight or processing did not cover the planned area.")
    aircraft_id: str | None = Field(default=None, max_length=100)
    operator: str | None = Field(default=None, max_length=200)
    software_version: str = Field(min_length=1, max_length=100, examples=["pw-proc 0.3.1"])
    local_frame_origin: LocalFrameOrigin | None = None
    flight_path: LineString | None = None
    data_warnings: list[DataWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def _times(self):
        if self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        return self


# ------------------------------------------------------------ finding section


class Measurement(Strict):
    value: float
    unit: str = Field(min_length=1, max_length=20, examples=["m", "mm", "m2"])


class BoundingBox(Strict):
    label: str = Field(min_length=1, max_length=64)
    bbox: Annotated[list[float], Field(min_length=4, max_length=4)] = Field(
        description="[x_min, y_min, x_max, y_max] in pixels of the ORIGINAL image (origin top-left)."
    )
    confidence: Probability | None = None

    @field_validator("bbox")
    @classmethod
    def _ordered(cls, v: list[float]):
        x0, y0, x1, y1 = v
        if min(v) < 0:
            raise ValueError("bbox values must be >= 0")
        if not (x1 > x0 and y1 > y0):
            raise ValueError("bbox must satisfy x_max > x_min and y_max > y_min")
        return v


class Evidence(Strict):
    file: FileName
    kind: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")] = Field(
        description="image_raw, image_closeup, lidar_profile, lidar_scan, other..."
    )
    caption: str | None = None
    captured_at: AwareDatetime | None = None
    width_px: int | None = Field(default=None, gt=0, description="Original image width. Checked against the upload.")
    height_px: int | None = Field(default=None, gt=0, description="Original image height. Checked against the upload.")
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)

    @model_validator(mode="after")
    def _boxes_inside(self):
        if self.width_px and self.height_px:
            for i, b in enumerate(self.bounding_boxes):
                if b.bbox[2] > self.width_px or b.bbox[3] > self.height_px:
                    raise ValueError(f"bounding_boxes[{i}] lies outside the {self.width_px}x{self.height_px} image")
        return self


class QualityWarning(Strict):
    code: Code
    message: str | None = None


class LocalPosition(Strict):
    x: float
    y: float
    z: float | None = None


class FindingProperties(Strict):
    finding_id: Identifier = Field(examples=["F-0001"])
    detected_at: AwareDatetime
    defect_type: DefectType
    subtype: str | None = Field(default=None, max_length=64, examples=["alligator"])
    description: str | None = None
    severity: Severity | None = None
    confidence: Probability | None = None
    detection_source: DetectionSource | None = None
    gps_accuracy_m: float | None = Field(default=None, ge=0, description="Estimated horizontal GPS error (metres).")
    position_local_m: LocalPosition | None = Field(
        default=None, description="Position in metres from the drone's start point (local frame)."
    )
    measurements: dict[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")], Measurement] = Field(
        default_factory=dict, examples=[{"width": {"value": 0.42, "unit": "m"}}]
    )
    quality_warnings: list[QualityWarning] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1, description="At least one evidence file is required.")


class PointGeometry(Lenient):
    type: Literal["Point"]
    coordinates: Annotated[list[float], Field(min_length=2, max_length=3, description="[lon, lat] or [lon, lat, alt]")]

    @field_validator("coordinates")
    @classmethod
    def _range(cls, v: list[float]):
        if not (-180 <= v[0] <= 180):
            raise ValueError("longitude (first value) must be between -180 and 180")
        if not (-90 <= v[1] <= 90):
            raise ValueError("latitude (second value) must be between -90 and 90")
        return v


class Feature(Lenient):
    type: Literal["Feature"]
    geometry: PointGeometry | None = Field(description="Best-effort GPS position, or null if only a local position exists.")
    properties: FindingProperties

    @model_validator(mode="after")
    def _some_position(self):
        if self.geometry is None and self.properties.position_local_m is None:
            raise ValueError("a finding needs a GPS geometry or properties.position_local_m (or both)")
        return self


class RunSubmission(Lenient):
    """A complete survey run: run metadata plus zero or more findings."""

    type: Literal["FeatureCollection"]
    schema_version: Literal["1.0"]
    run: RunInfo
    features: list[Feature] = Field(description="May be empty: a complete run with no findings is valid.")

    @model_validator(mode="after")
    def _uniqueness(self):
        seen_ids: set[str] = set()
        seen_files: set[str] = set()
        for i, f in enumerate(self.features):
            fid = f.properties.finding_id
            if fid in seen_ids:
                raise ValueError(f"features[{i}]: duplicate finding_id {fid!r}")
            seen_ids.add(fid)
            for ev in f.properties.evidence:
                if ev.file in seen_files:
                    raise ValueError(f"features[{i}]: evidence file {ev.file!r} is used more than once in this run")
                seen_files.add(ev.file)
        return self

    def evidence_files(self) -> list[str]:
        return [ev.file for f in self.features for ev in f.properties.evidence]

    def evidence_by_file(self) -> dict[str, Evidence]:
        return {ev.file: ev for f in self.features for ev in f.properties.evidence}


def json_schema() -> dict[str, Any]:
    schema = RunSubmission.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://pavewatch.local/schema/run-submission-{SCHEMA_VERSION}.json"
    schema["title"] = f"PaveWatch run submission v{SCHEMA_VERSION}"
    return schema
