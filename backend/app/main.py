"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload   (from the backend/ folder)
API docs:     http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import ingest, portal
from app.config import BACKEND_DIR, Settings, get_settings
from app.db.migrate import upgrade_to_head
from app.db.session import make_engine, make_sessionmaker
from app.reports.maps import TileSource
from app.services.errors import ApiProblem
from app.services.ingest import record_rejection
from app.storage import LocalStorage, make_storage

DESCRIPTION = """
PaveWatch portal API.

**Data senders** (processing pipeline): use the *Ingestion* endpoints in three steps:
1. `POST /api/v1/ingest/runs` with the GeoJSON run submission
2. `PUT /api/v1/ingest/{ingestion_id}/files/{file}` for every file listed in `files_expected`
3. `POST /api/v1/ingest/{ingestion_id}/complete`

The full JSON Schema is at `GET /api/v1/ingest/schema`. See `docs/ingestion-spec.md`.
"""


def _format_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for e in errors:
        parts: list[str] = []
        for p in e.get("loc", ()):
            if p in ("body", "query", "path", "header"):
                continue
            if isinstance(p, int):
                parts.append(f"[{p}]")
            else:
                parts.append(("." if parts else "") + str(p))
        msg = str(e.get("msg", "invalid")).removeprefix("Value error, ")
        out.append({"path": "".join(parts), "message": msg})
    return out


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        upgrade_to_head(settings.database_url)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="PaveWatch Portal API", version=__version__, description=DESCRIPTION, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.SessionLocal = make_sessionmaker(app.state.engine)
    app.state.storage = make_storage(settings)
    app.state.tiles = (
        TileSource(settings.report_tile_url, settings.report_tile_cache_dir) if settings.report_basemap else None
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiProblem)
    async def _problem(_: Request, exc: ApiProblem):
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        errors = _format_validation_errors(list(exc.errors()))
        detail = "The request failed validation."
        ingestion_id = None
        if request.method == "POST" and request.url.path == f"{ingest.PREFIX}/runs":
            detail = f"Run submission rejected: {len(errors)} problem(s) found. Fix them and resend."
            body = exc.body if isinstance(exc.body, dict) else {}
            run = body.get("run") if isinstance(body.get("run"), dict) else {}
            company = run.get("company") if isinstance(run.get("company"), dict) else {}
            db = app.state.SessionLocal()
            try:
                ingestion_id = record_rejection(
                    db,
                    detail=detail,
                    errors=errors,
                    run_id=str(run.get("run_id"))[:100] if run.get("run_id") else None,
                    org_slug=str(company.get("company_id"))[:64] if company.get("company_id") else None,
                )
            finally:
                db.close()
        return JSONResponse(
            status_code=422, content={"detail": detail, "errors": errors, "ingestion_id": ingestion_id}
        )

    app.include_router(ingest.router)
    app.include_router(portal.router)

    @app.get("/api/health", tags=["Meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    if isinstance(app.state.storage, LocalStorage):
        app.mount(settings.storage_url_prefix, StaticFiles(directory=app.state.storage.root), name="files")

    # Serve the built frontend (production / single-process mode) if it exists.
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if dist.is_dir():
        from app.spa import mount_spa

        mount_spa(app, dist)

    return app


app = create_app()
