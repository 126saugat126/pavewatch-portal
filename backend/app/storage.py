"""File storage behind a tiny interface.

Today: local disk. Planned: Google Cloud Storage (implement the same four
methods in a ``GCSStorage`` class and select it with ``PW_STORAGE_BACKEND=gcs``).
Keys are always forward-slash paths such as ``northgate-roads/PW-.../<ingestion>/F-0001_raw.jpg``.
"""

import shutil
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.config import Settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def url(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self, root: Path, url_prefix: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.url_prefix = url_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"Invalid storage key: {key!r}")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(p)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete_prefix(self, prefix: str) -> None:
        p = self._path(prefix)
        if p == self.root:
            raise ValueError("Refusing to delete the storage root")
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)

    def url(self, key: str) -> str:
        return f"{self.url_prefix}/{quote(key)}"


def make_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_dir, settings.storage_url_prefix)
    raise ValueError(f"Unknown storage backend {settings.storage_backend!r} (only 'local' is implemented)")
