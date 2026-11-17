"""Read-side queries for the portal.

Every function takes the organization explicitly. When login arrives, the
active organization will come from the user's session instead of the URL, and
these functions stay the same - that is the tenant-scoping seam.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import models as m
from app.schemas import portal as s
from app.services.errors import ApiProblem
from app.storage import Storage


def _org_ref(org: m.Organization) -> s.OrgRef:
    return s.OrgRef(org_id=org.slug, name=org.name)


# ------------------------------------------------------------- organizations


def list_organizations(db: Session) -> list[s.OrganizationSummary]:
    orgs = db.scalars(select(m.Organization).order_by(m.Organization.name)).all()

    run_rows = db.execute(
        select(m.Run.org_id, m.Run.started_at, m.Run.site_name).order_by(m.Run.started_at.desc())
    ).all()
    run_count: Counter[int] = Counter()
    latest: dict[int, tuple] = {}
    for org_id, started_at, site in run_rows:
        run_count[org_id] += 1
        latest.setdefault(org_id, (started_at, site))

    finding_rows = db.execute(
        select(m.Finding.org_id, m.Finding.severity, func.count()).group_by(m.Finding.org_id, m.Finding.severity)
    ).all()
    finding_count: Counter[int] = Counter()
    high_count: Counter[int] = Counter()
    for org_id, severity, n in finding_rows:
        finding_count[org_id] += n
        if severity == "high":
            high_count[org_id] += n

    return [
        s.OrganizationSummary(
            org_id=o.slug,
            name=o.name,
            run_count=run_count[o.id],
            finding_count=finding_count[o.id],
            high_severity_count=high_count[o.id],
            last_survey_at=latest.get(o.id, (None, None))[0],
            last_site_name=latest.get(o.id, (None, None))[1],
        )
        for o in orgs
    ]


def get_organization(db: Session, org_slug: str) -> m.Organization:
    org = db.scalar(select(m.Organization).where(m.Organization.slug == org_slug))
    if org is None:
        raise ApiProblem(404, f"Company {org_slug!r} not found.")
    return org


# ---------------------------------------------------------------------- runs


def _run_stats(db: Session, run_pks: Iterable[int]) -> dict[int, dict]:
    pks = list(run_pks)
    stats: dict[int, dict] = defaultdict(
        lambda: {"types": Counter(), "sev": Counter(), "with_warn": 0, "n": 0, "dw": 0}
    )
    if not pks:
        return stats
    rows = db.execute(
        select(m.Finding.run_pk, m.Finding.defect_type, m.Finding.severity, m.Finding.quality_warnings).where(
            m.Finding.run_pk.in_(pks)
        )
    ).all()
    for run_pk, dtype, sev, qw in rows:
        st = stats[run_pk]
        st["n"] += 1
        st["types"][dtype] += 1
        if sev:
            st["sev"][sev] += 1
        if qw:
            st["with_warn"] += 1
    for run_pk, n in db.execute(
        select(m.DataWarning.run_pk, func.count()).where(m.DataWarning.run_pk.in_(pks)).group_by(m.DataWarning.run_pk)
    ).all():
        stats[run_pk]["dw"] = n
    return stats


def _summary_fields(run: m.Run, st: dict) -> dict:
    return dict(
        run_id=run.run_id,
        site_name=run.site_name,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=run.status,
        aircraft_id=run.aircraft_id,
        finding_count=st["n"],
        counts_by_type=dict(st["types"]),
        counts_by_severity=dict(st["sev"]),
        data_warning_count=st["dw"],
        findings_with_warnings=st["with_warn"],
    )


def list_runs(db: Session, org: m.Organization) -> list[s.RunSummary]:
    runs = db.scalars(select(m.Run).where(m.Run.org_id == org.id).order_by(m.Run.started_at.desc())).all()
    stats = _run_stats(db, (r.id for r in runs))
    return [s.RunSummary(**_summary_fields(r, stats[r.id])) for r in runs]


def get_run_model(db: Session, org: m.Organization, run_id: str) -> m.Run:
    run = db.scalar(select(m.Run).where(m.Run.org_id == org.id, m.Run.run_id == run_id))
    if run is None:
        raise ApiProblem(404, f"Survey run {run_id!r} not found for this company.")
    return run


def get_run(db: Session, org: m.Organization, run_id: str) -> s.RunDetail:
    run = get_run_model(db, org, run_id)
    st = _run_stats(db, [run.id])[run.id]
    return s.RunDetail(
        **_summary_fields(run, st),
        organization=_org_ref(org),
        operator=run.operator,
        software_version=run.software_version,
        schema_version=run.schema_version,
        local_frame_origin=run.local_frame_origin,
        flight_path=run.flight_path,
        data_warnings=[s.DataWarningOut(code=w.code, message=w.message, geometry=w.geometry) for w in run.data_warnings],
        ingested_at=run.ingested_at,
    )


# ------------------------------------------------------------------ findings


def _first_thumb(storage: Storage, f: m.Finding) -> str | None:
    for ev in f.evidence:
        if ev.thumb_key:
            return storage.url(ev.thumb_key)
    return None


def _list_item_fields(storage: Storage, f: m.Finding) -> dict:
    return dict(
        finding_id=f.finding_id,
        detected_at=f.detected_at,
        defect_type=f.defect_type,
        subtype=f.subtype,
        severity=f.severity,
        confidence=f.confidence,
        detection_source=f.detection_source,
        lat=f.lat,
        lon=f.lon,
        gps_accuracy_m=f.gps_accuracy_m,
        local_x_m=f.local_x_m,
        local_y_m=f.local_y_m,
        measurements=f.measurements or {},
        warning_codes=[w.get("code", "") for w in (f.quality_warnings or [])],
        evidence_count=len(f.evidence),
        thumb_url=_first_thumb(storage, f),
    )


def list_findings(db: Session, storage: Storage, org: m.Organization, run_id: str) -> list[s.FindingListItem]:
    run = get_run_model(db, org, run_id)
    findings = db.scalars(
        select(m.Finding)
        .where(m.Finding.run_pk == run.id)
        .options(selectinload(m.Finding.evidence))
        .order_by(m.Finding.finding_id)
    ).all()
    return [s.FindingListItem(**_list_item_fields(storage, f)) for f in findings]


def _evidence_out(storage: Storage, ev: m.Evidence) -> s.EvidenceOut:
    return s.EvidenceOut(
        file=ev.file_name,
        kind=ev.kind,
        caption=ev.caption,
        captured_at=ev.captured_at,
        content_type=ev.content_type,
        size_bytes=ev.size_bytes,
        is_image=ev.thumb_key is not None,
        width_px=ev.width_px,
        height_px=ev.height_px,
        url=storage.url(ev.storage_key),
        preview_url=storage.url(ev.preview_key) if ev.preview_key else None,
        thumb_url=storage.url(ev.thumb_key) if ev.thumb_key else None,
        bounding_boxes=ev.bounding_boxes or [],
    )


def get_finding(db: Session, storage: Storage, org: m.Organization, run_id: str, finding_id: str) -> s.FindingDetail:
    run = get_run_model(db, org, run_id)
    f = db.scalar(
        select(m.Finding)
        .where(m.Finding.run_pk == run.id, m.Finding.finding_id == finding_id)
        .options(selectinload(m.Finding.evidence))
    )
    if f is None:
        raise ApiProblem(404, f"Finding {finding_id!r} not found in run {run_id!r}.")

    ids = db.scalars(select(m.Finding.finding_id).where(m.Finding.run_pk == run.id).order_by(m.Finding.finding_id)).all()
    idx = ids.index(f.finding_id)

    return s.FindingDetail(
        **_list_item_fields(storage, f),
        run_id=run.run_id,
        site_name=run.site_name,
        organization=_org_ref(org),
        description=f.description,
        alt_m=f.alt_m,
        quality_warnings=[s.QualityWarningOut(**w) for w in (f.quality_warnings or [])],
        evidence=[_evidence_out(storage, ev) for ev in f.evidence],
        prev_finding_id=ids[idx - 1] if idx > 0 else None,
        next_finding_id=ids[idx + 1] if idx + 1 < len(ids) else None,
        position_in_run=idx + 1,
        findings_in_run=len(ids),
    )
