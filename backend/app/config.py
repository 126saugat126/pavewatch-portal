"""Runtime configuration.

Everything that differs between "local laptop" and "cloud" lives here and can be
set via environment variables (prefix ``PW_``) or a ``.env`` file in ``backend/``.
Swapping SQLite for Cloud SQL Postgres is a change to ``PW_DATABASE_URL`` only.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PW_", env_file=BACKEND_DIR / ".env", extra="ignore")

    # Database (SQLAlchemy URL). Postgres example:
    #   postgresql+psycopg://user:pass@host:5432/pavewatch
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'pavewatch.db').as_posix()}"

    # File storage backend. Only "local" exists today; "gcs" is the planned cloud option.
    storage_backend: str = "local"
    storage_dir: Path = BACKEND_DIR / "data" / "files"
    # Public URL prefix the local storage files are served under.
    storage_url_prefix: str = "/files"

    # Ingestion protection. Empty = no key required (local development).
    ingest_api_key: str = ""

    # Maximum size of a single evidence file upload.
    max_upload_mb: int = 50

    # Image derivatives generated on upload (longest edge in px).
    thumb_px: int = 480
    preview_px: int = 1600

    # Frontend dev server origins allowed by CORS.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
