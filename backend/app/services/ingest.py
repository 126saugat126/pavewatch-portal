"""Three-step ingestion.

1. ``stage_run``     - payload validated; an Ingestion row is created in ``pending_files``.
2. ``receive_file``  - each evidence file is uploaded (raw bytes), checked and stored.
3. ``complete``      - all files present -> findings are published atomically.

Nothing is visible in the portal until step 3 succeeds, so a half-finished upload
never shows up as a half-finished survey. On a cloud deployment step 2 maps onto
signed upload URLs to Cloud Storage without changing the sender's contract.
"""

import io
import mimetypes
import uuid
from datetime import UTC, datetime
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models as m
from app.schemas.ingest import RunSubmission
from app.schemas.ingest_responses import FileReceived, IngestionCompleted
from app.services.errors import ApiProblem
from app.storage import Storage

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}


def _now() -> datetime:
    return datetime.now(UTC)


def record_rejection(
    db: Session, *, detail: str, errors: list[dict[str, Any]], run_id: str | None = None, org_slug: str | None = None
) -> str:
    ing = m.Ingestion(
        id=str(uuid.uuid4()),
        status="rejected",
        run_id=run_id,
        org_slug=org_slug,
        errors=errors or [{"path": "", "message": detail}],
    )
    db.add(ing)
    db.commit()
    return ing.id


def _get_pending(db: Session, ingestion_id: str) -> m.Ingestion:
    ing = db.get(m.Ingestion, ingestion_id)
    if ing is None:
        raise ApiProblem(404, f"Unknown ingestion {ingestion_id!r}.")
    if ing.status == "rejected":
        raise ApiProblem(409, "This ingestion was rejected. Fix the payload and start a new one.", ingestion_id=ing.id)
    return ing


def _check_run_conflict(db: Session, sub: RunSubmission, replace: bool) -> m.Run | None:
    existing = db.scalar(select(m.Run).where(m.Run.run_id == sub.run.run_id))
    if existing is None:
        return None
    if existing.organization.slug != sub.run.company.company_id:
        raise ApiProblem(
            409,
            f"run_id {sub.run.run_id!r} already belongs to another company. run_id must be globally unique.",
            [{"path": "run.run_id", "message": "already used by another company"}],
        )
    if not replace:
        raise ApiProblem(
            409,
            f"Run {sub.run.run_id!r} already exists. Resend with ?replace=true to overwrite it.",
            [{"path": "run.run_id", "message": "already exists"}],
        )
    return existing


# ------------------------------------------------------------------- step 1


def stage_run(db: Session, sub: RunSubmission, *, replace: bool) -> m.Ingestion:
    try:
        _check_run_conflict(db, sub, replace)
    except ApiProblem as p:
        p.ingestion_id = record_rejection(
            db, detail=p.detail, errors=p.errors, run_id=sub.run.run_id, org_slug=sub.run.company.company_id
        )
        raise

    ing_id = str(uuid.uuid4())
    ing = m.Ingestion(
        id=ing_id,
        status="pending_files",
        run_id=sub.run.run_id,
        org_slug=sub.run.company.company_id,
        replace=replace,
        payload=sub.model_dump(mode="json"),
        storage_prefix=f"{sub.run.company.company_id}/{sub.run.run_id}/{ing_id}",
        expected_files=sub.evidence_files(),
        received_files={},
    )
    db.add(ing)
    db.commit()
    return ing


def remaining_files(ing: m.Ingestion) -> list[str]:
    received = ing.received_files or {}
    return [f for f in (ing.expected_files or []) if f not in received]


# ------------------------------------------------------------------- step 2


def _derivative(img: Image.Image, max_px: int) -> bytes:
    d = img.copy()
    if d.mode not in ("RGB", "L"):
        background = Image.new("RGB", d.size, (255, 255, 255))
        rgba = d.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        d = background
    d.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    d.save(buf, format="JPEG", quality=84, optimize=True, progressive=True)
    return buf.getvalue()


def receive_file(
    db: Session,
    storage: Storage,
    settings: Settings,
    ingestion_id: str,
    file_name: str,
    data: bytes,
    content_type: str | None,
) -> FileReceived:
    ing = _get_pending(db, ingestion_id)
    if ing.status != "pending_files":
        raise ApiProblem(409, f"Ingestion is already {ing.status}; files can no longer be added.", ingestion_id=ing.id)

    expected = ing.expected_files or []
    if file_name not in expected:
        raise ApiProblem(
            404,
            f"File {file_name!r} is not referenced by any finding in this run.",
            [{"path": "file", "message": "expected one of: " + ", ".join(remaining_files(ing) or expected)}],
            ingestion_id=ing.id,
        )
    if not data:
        raise ApiProblem(422, f"File {file_name!r} is empty.", ingestion_id=ing.id)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ApiProblem(413, f"File {file_name!r} is larger than {settings.max_upload_mb} MB.", ingestion_id=ing.id)

    ctype = (content_type or "").split(";")[0].strip().lower()
    if not ctype or ctype == "application/octet-stream":
        ctype = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    sub = RunSubmission.model_validate(ing.payload)
    spec = sub.evidence_by_file()[file_name]

    width = height = None
    thumb_key = preview_key = None
    key = f"{ing.storage_prefix}/{file_name}"
    derivatives: list[tuple[str, bytes]] = []

    if ctype in IMAGE_TYPES:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
            raise ApiProblem(422, f"File {file_name!r} is not a readable image ({e}).", ingestion_id=ing.id) from e
        width, height = img.size
        errs = []
        if spec.width_px and spec.width_px != width:
            errs.append({"path": f"{file_name}.width_px", "message": f"payload says {spec.width_px}, image is {width}"})
        if spec.height_px and spec.height_px != height:
            errs.append({"path": f"{file_name}.height_px", "message": f"payload says {spec.height_px}, image is {height}"})
        for i, b in enumerate(spec.bounding_boxes):
            if b.bbox[2] > width or b.bbox[3] > height:
                errs.append(
                    {"path": f"{file_name}.bounding_boxes[{i}]", "message": f"outside the {width}x{height} image"}
                )
        if errs:
            raise ApiProblem(422, f"File {file_name!r} does not match its description in the payload.", errs, ing.id)

        thumb_key = f"{ing.storage_prefix}/_thumb/{file_name}.jpg"
        derivatives.append((thumb_key, _derivative(img, settings.thumb_px)))
        if max(width, height) > settings.preview_px:
            preview_key = f"{ing.storage_prefix}/_preview/{file_name}.jpg"
            derivatives.append((preview_key, _derivative(img, settings.preview_px)))
        else:
            preview_key = key
    elif spec.bounding_boxes:
        raise ApiProblem(
            422,
            f"File {file_name!r} has bounding boxes but was not uploaded as an image (Content-Type {ctype}).",
            ingestion_id=ing.id,
        )

    storage.put(key, data, ctype)
    for dkey, dbytes in derivatives:
        storage.put(dkey, dbytes, "image/jpeg")

    received = dict(ing.received_files or {})
    received[file_name] = {
        "storage_key": key,
        "content_type": ctype,
        "size_bytes": len(data),
        "width_px": width,
        "height_px": height,
        "thumb_key": thumb_key,
        "preview_key": preview_key,
    }
    ing.received_files = received
    db.commit()

    return FileReceived(
        ingestion_id=ing.id,
        file=file_name,
        size_bytes=len(data),
        content_type=ctype,
        width_px=width,
        height_px=height,
        files_remaining=remaining_files(ing),
    )


# ------------------------------------------------------------------- step 3


def _completed_response(ing: m.Ingestion, run: m.Run, replaced: bool) -> IngestionCompleted:
    return IngestionCompleted(
        ingestion_id=ing.id,
        run_id=run.run_id,
        status="completed",
        organization_id=run.organization.slug,
        findings=len(run.findings),
        replaced_previous=replaced,
        portal_path=f"/orgs/{run.organization.slug}/runs/{run.run_id}",
    )


def complete(db: Session, storage: Storage, ingestion_id: str) -> IngestionCompleted:
    ing = _get_pending(db, ingestion_id)

    if ing.status == "completed":  # idempotent: safe to retry
        run = db.scalar(select(m.Run).where(m.Run.ingestion_id == ing.id))
        if run is None:
            raise ApiProblem(409, "This ingestion was completed but its run has since been replaced.", ingestion_id=ing.id)
        return _completed_response(ing, run, replaced=ing.replace)

    missing = remaining_files(ing)
    if missing:
        raise ApiProblem(
            409,
            f"{len(missing)} evidence file(s) have not been uploaded yet.",
            [{"path": f, "message": "not uploaded"} for f in missing],
            ingestion_id=ing.id,
        )

    sub = RunSubmission.model_validate(ing.payload)
    try:
        existing = _check_run_conflict(db, sub, ing.replace)
    except ApiProblem as p:
        p.ingestion_id = ing.id
        raise

    old_prefix = None
    if existing is not None:
        old_prefix = existing.storage_prefix
        db.delete(existing)
        db.flush()

    company = sub.run.company
    org = db.scalar(select(m.Organization).where(m.Organization.slug == company.company_id))
    if org is None:
        org = m.Organization(slug=company.company_id, name=company.name)
        db.add(org)
        db.flush()
    elif org.name != company.name:
        org.name = company.name

    r = sub.run
    run = m.Run(
        org_id=org.id,
        run_id=r.run_id,
        site_name=r.site_name,
        started_at=r.started_at,
        ended_at=r.ended_at,
        status=r.status,
        aircraft_id=r.aircraft_id,
        operator=r.operator,
        software_version=r.software_version,
        local_frame_origin=r.local_frame_origin.model_dump(mode="json") if r.local_frame_origin else None,
        flight_path=r.flight_path.model_dump(mode="json") if r.flight_path else None,
        schema_version=sub.schema_version,
        storage_prefix=ing.storage_prefix,
        ingestion_id=ing.id,
    )
    run.organization = org
    for w in r.data_warnings:
        run.data_warnings.append(m.DataWarning(org_id=org.id, code=w.code, message=w.message, geometry=w.geometry))

    received = ing.received_files or {}
    for feat in sub.features:
        p = feat.properties
        coords = feat.geometry.coordinates if feat.geometry else None
        finding = m.Finding(
            org_id=org.id,
            finding_id=p.finding_id,
            detected_at=p.detected_at,
            defect_type=p.defect_type,
            subtype=p.subtype,
            description=p.description,
            severity=p.severity,
            confidence=p.confidence,
            detection_source=p.detection_source,
            lon=coords[0] if coords else None,
            lat=coords[1] if coords else None,
            alt_m=coords[2] if coords and len(coords) > 2 else None,
            gps_accuracy_m=p.gps_accuracy_m,
            local_x_m=p.position_local_m.x if p.position_local_m else None,
            local_y_m=p.position_local_m.y if p.position_local_m else None,
            measurements={k: v.model_dump() for k, v in p.measurements.items()},
            quality_warnings=[q.model_dump() for q in p.quality_warnings],
        )
        for pos, ev in enumerate(p.evidence):
            f = received[ev.file]
            finding.evidence.append(
                m.Evidence(
                    org_id=org.id,
                    position=pos,
                    file_name=ev.file,
                    storage_key=f["storage_key"],
                    content_type=f["content_type"],
                    size_bytes=f["size_bytes"],
                    kind=ev.kind,
                    caption=ev.caption,
                    captured_at=ev.captured_at,
                    width_px=f["width_px"] or ev.width_px,
                    height_px=f["height_px"] or ev.height_px,
                    thumb_key=f["thumb_key"],
                    preview_key=f["preview_key"],
                    bounding_boxes=[b.model_dump() for b in ev.bounding_boxes],
                )
            )
        run.findings.append(finding)

    db.add(run)
    ing.status = "completed"
    ing.completed_at = _now()
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ApiProblem(409, f"Run {r.run_id!r} was published by another upload at the same time.", ingestion_id=ing.id) from e

    if old_prefix and old_prefix != ing.storage_prefix:
        storage.delete_prefix(old_prefix)

    return _completed_response(ing, run, replaced=existing is not None)
