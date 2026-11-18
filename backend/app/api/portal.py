"""Read-only API used by the portal frontend.

URLs are nested under the organization on purpose: when login is added, a
middleware/dependency can check the user's membership for ``org_id`` here
without changing any URL.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import portal as s
from app.schemas.ingest_responses import ErrorResponse
from app.services import portal as svc

router = APIRouter(prefix="/api/v1", tags=["Portal"], responses={404: {"model": ErrorResponse}})


@router.get("/orgs", summary="Companies that use the service")
def list_orgs(request: Request, db: Session = Depends(get_db)) -> list[s.OrganizationSummary]:
    return svc.list_organizations(db, request.app.state.storage)


@router.get("/orgs/{org_id}", summary="One company")
def get_org(org_id: str, db: Session = Depends(get_db)) -> s.OrgRef:
    org = svc.get_organization(db, org_id)
    return s.OrgRef(org_id=org.slug, name=org.name)


@router.get("/orgs/{org_id}/runs", summary="Survey runs of a company (newest first)")
def list_runs(org_id: str, request: Request, db: Session = Depends(get_db)) -> list[s.RunSummary]:
    return svc.list_runs(db, request.app.state.storage, svc.get_organization(db, org_id))


@router.get("/orgs/{org_id}/runs/{run_id}", summary="One survey run with flight path and data warnings")
def get_run(org_id: str, run_id: str, db: Session = Depends(get_db)) -> s.RunDetail:
    return svc.get_run(db, svc.get_organization(db, org_id), run_id)


@router.get("/orgs/{org_id}/runs/{run_id}/findings", summary="Findings in a run")
def list_findings(org_id: str, run_id: str, request: Request, db: Session = Depends(get_db)) -> list[s.FindingListItem]:
    return svc.list_findings(db, request.app.state.storage, svc.get_organization(db, org_id), run_id)


@router.get("/orgs/{org_id}/runs/{run_id}/findings/{finding_id}", summary="Full detail of one finding")
def get_finding(org_id: str, run_id: str, finding_id: str, request: Request, db: Session = Depends(get_db)) -> s.FindingDetail:
    return svc.get_finding(db, request.app.state.storage, svc.get_organization(db, org_id), run_id, finding_id)
