"""Ingestion API used by the processing pipeline (the "data sender")."""

import secrets

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.models import Ingestion
from app.db.session import get_db
from app.schemas.ingest import RunSubmission, json_schema
from app.schemas.ingest_responses import (
    ErrorResponse,
    FileReceived,
    IngestionAccepted,
    IngestionCompleted,
    IngestionStatus,
)
from app.services import ingest as svc
from app.services.errors import ApiProblem

PREFIX = "/api/v1/ingest"


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, description="Required only if the server sets PW_INGEST_API_KEY."),
) -> None:
    expected = request.app.state.settings.ingest_api_key
    if expected and not (x_api_key and secrets.compare_digest(x_api_key, expected)):
        raise ApiProblem(401, "Missing or wrong X-API-Key header.")


ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing or wrong API key"},
    404: {"model": ErrorResponse, "description": "Unknown ingestion or file"},
    409: {"model": ErrorResponse, "description": "Conflict (run exists, files missing, wrong state)"},
    422: {"model": ErrorResponse, "description": "Payload or file failed validation"},
}

router = APIRouter(prefix=PREFIX, tags=["Ingestion (data sender)"], responses=ERRORS)


@router.get("/schema", summary="Download the JSON Schema of the run submission")
def get_schema() -> dict:
    return json_schema()


@router.post(
    "/runs",
    status_code=201,
    summary="Step 1 - submit a run (GeoJSON FeatureCollection)",
    dependencies=[Depends(require_api_key)],
)
def submit_run(
    payload: RunSubmission,
    replace: bool = Query(False, description="Overwrite an existing run with the same run_id."),
    db: Session = Depends(get_db),
) -> IngestionAccepted:
    """Validates the payload. If it is valid the response lists every evidence file
    that must be uploaded next. Nothing is shown in the portal until step 3."""
    ing = svc.stage_run(db, payload, replace=replace)
    return IngestionAccepted(
        ingestion_id=ing.id,
        run_id=ing.run_id or "",
        status=ing.status,
        files_expected=ing.expected_files or [],
        upload_url_template=f"{PREFIX}/{ing.id}/files/{{file}}",
        complete_url=f"{PREFIX}/{ing.id}/complete",
    )


@router.put(
    "/{ingestion_id}/files/{file_name}",
    summary="Step 2 - upload one evidence file (raw bytes)",
    dependencies=[Depends(require_api_key)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            "description": "The file's raw bytes. Set Content-Type (e.g. image/jpeg) if you can.",
        }
    },
)
async def upload_file(
    ingestion_id: str,
    file_name: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileReceived:
    """Uploading the same file again overwrites the previous copy, so retries are safe.
    Images are checked against ``width_px``/``height_px`` and their bounding boxes."""
    data = await request.body()
    return await run_in_threadpool(
        svc.receive_file,
        db,
        request.app.state.storage,
        request.app.state.settings,
        ingestion_id,
        file_name,
        data,
        request.headers.get("content-type"),
    )


@router.post(
    "/{ingestion_id}/complete",
    summary="Step 3 - publish the run once all files are uploaded",
    dependencies=[Depends(require_api_key)],
)
def complete_ingestion(ingestion_id: str, request: Request, db: Session = Depends(get_db)) -> IngestionCompleted:
    """Fails with 409 and the list of missing files if anything is still missing.
    Safe to call again after success (returns the same result)."""
    return svc.complete(db, request.app.state.storage, ingestion_id)


@router.get("/{ingestion_id}", summary="Check the status of an ingestion", dependencies=[Depends(require_api_key)])
def ingestion_status(ingestion_id: str, db: Session = Depends(get_db)) -> IngestionStatus:
    ing = db.get(Ingestion, ingestion_id)
    if ing is None:
        raise ApiProblem(404, f"Unknown ingestion {ingestion_id!r}.")
    return IngestionStatus(
        ingestion_id=ing.id,
        status=ing.status,
        run_id=ing.run_id,
        received_at=ing.received_at,
        completed_at=ing.completed_at,
        files_expected=ing.expected_files or [],
        files_received=list((ing.received_files or {}).keys()),
        files_remaining=svc.remaining_files(ing),
        errors=ing.errors,
    )
