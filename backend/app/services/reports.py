"""Loads the data for a PDF report and builds it.

Same tenant-scoping seam as ``services.portal``: every function takes the
organization explicitly.
"""

import re
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models as m
from app.reports.maps import TileSource
from app.reports.pdf import build_finding_report, build_run_report
from app.services.errors import ApiProblem
from app.services.portal import get_run_model
from app.storage import Storage


def resolve_tz(name: str | None) -> tzinfo:
    """IANA zone name sent by the browser (e.g. 'America/Toronto'); UTC if missing or unknown."""
    if not name:
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "report"


def run_report(
    db: Session, storage: Storage, tiles: TileSource | None, org: m.Organization, run_id: str, tz_name: str | None
) -> tuple[bytes, str]:
    run = get_run_model(db, org, run_id)
    run = db.scalar(
        select(m.Run)
        .where(m.Run.id == run.id)
        .options(selectinload(m.Run.findings).selectinload(m.Finding.evidence), selectinload(m.Run.data_warnings))
    )
    pdf = build_run_report(
        storage=storage, tiles=tiles, tz=resolve_tz(tz_name), generated_at=datetime.now(UTC), org=org, run=run
    )
    return pdf, f"PaveWatch_{_safe(run.run_id)}_survey_report.pdf"


def finding_report(
    db: Session,
    storage: Storage,
    tiles: TileSource | None,
    org: m.Organization,
    run_id: str,
    finding_id: str,
    tz_name: str | None,
) -> tuple[bytes, str]:
    run = get_run_model(db, org, run_id)
    f = db.scalar(
        select(m.Finding)
        .where(m.Finding.run_pk == run.id, m.Finding.finding_id == finding_id)
        .options(selectinload(m.Finding.evidence))
    )
    if f is None:
        raise ApiProblem(404, f"Finding {finding_id!r} not found in run {run_id!r}.")
    ids = list(db.scalars(select(m.Finding.finding_id).where(m.Finding.run_pk == run.id).order_by(m.Finding.finding_id)))
    pdf = build_finding_report(
        storage=storage,
        tiles=tiles,
        tz=resolve_tz(tz_name),
        generated_at=datetime.now(UTC),
        org=org,
        run=run,
        finding=f,
        position=ids.index(f.finding_id) + 1,
        total=len(ids),
    )
    return pdf, f"PaveWatch_{_safe(run.run_id)}_{_safe(f.finding_id)}.pdf"
