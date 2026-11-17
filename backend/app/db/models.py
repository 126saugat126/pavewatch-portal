"""Database tables.

Portability rules (so SQLite -> Cloud SQL Postgres is a config change):
  * only generic SQLAlchemy types (String, Float, Integer, DateTime, JSON, ...)
  * no SQLite-specific SQL anywhere
  * coordinates stored as plain lat/lon floats + GeoJSON in JSON columns
    (PostGIS geometry columns can be added later in a migration)

Multi-tenancy readiness: every tenant-owned table carries ``org_id`` so that
future users / memberships / roles tables can scope every query by the active
organization without reshaping these tables.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UTCDateTime(TypeDecorator):
    """Stores aware datetimes as UTC and always returns aware UTC datetimes
    (SQLite drops tzinfo; Postgres keeps it)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Organization(Base):
    """A customer company = a tenant."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # payload: run.company.company_id
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    runs: Mapped[list["Run"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Run(Base):
    """One survey flight."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    site_name: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20))  # complete | incomplete
    aircraft_id: Mapped[str | None] = mapped_column(String(100))
    operator: Mapped[str | None] = mapped_column(String(200))
    software_version: Mapped[str] = mapped_column(String(100))
    local_frame_origin: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    flight_path: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # GeoJSON LineString
    schema_version: Mapped[str] = mapped_column(String(20))
    storage_prefix: Mapped[str] = mapped_column(String(300))
    ingestion_id: Mapped[str] = mapped_column(String(36))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="runs")
    data_warnings: Mapped[list["DataWarning"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="DataWarning.id"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Finding.finding_id"
    )


class DataWarning(Base):
    """Run-level data-quality warning (area not scanned, no LiDAR, bad pose, ...)."""

    __tablename__ = "data_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_pk: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    run: Mapped[Run] = relationship(back_populates="data_warnings")


class Finding(Base):
    """One defect (pothole, crack, ...)."""

    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("run_pk", "finding_id", name="uq_finding_per_run"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_pk: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    defect_type: Mapped[str] = mapped_column(String(32), index=True)
    subtype: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    detection_source: Mapped[str | None] = mapped_column(String(16))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    alt_m: Mapped[float | None] = mapped_column(Float)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float)
    local_x_m: Mapped[float | None] = mapped_column(Float)
    local_y_m: Mapped[float | None] = mapped_column(Float)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    quality_warnings: Mapped[list[Any]] = mapped_column(JSON, default=list)

    run: Mapped[Run] = relationship(back_populates="findings")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan", order_by="Evidence.position"
    )


class Evidence(Base):
    """An evidence file (image, close-up, LiDAR profile, 3D scan...) attached to a finding."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    finding_pk: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)  # order as sent
    file_name: Mapped[str] = mapped_column(String(200))
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(64))
    caption: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    thumb_key: Mapped[str | None] = mapped_column(String(500))
    preview_key: Mapped[str | None] = mapped_column(String(500))
    bounding_boxes: Mapped[list[Any]] = mapped_column(JSON, default=list)

    finding: Mapped[Finding] = relationship(back_populates="evidence")


class Ingestion(Base):
    """Every ingestion attempt: rejected, waiting for files, or completed.

    Doubles as the ingestion log the approach document asks for.
    """

    __tablename__ = "ingestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # rejected | pending_files | completed
    run_id: Mapped[str | None] = mapped_column(String(100), index=True)
    org_slug: Mapped[str | None] = mapped_column(String(64))
    replace: Mapped[bool] = mapped_column(default=False)
    errors: Mapped[list[Any] | None] = mapped_column(JSON)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    storage_prefix: Mapped[str | None] = mapped_column(String(300))
    expected_files: Mapped[list[Any] | None] = mapped_column(JSON)
    received_files: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
