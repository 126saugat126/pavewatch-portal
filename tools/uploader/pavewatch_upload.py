#!/usr/bin/env python3
"""PaveWatch upload helper for the processing pipeline.

Zero dependencies (Python 3.10+ standard library only). Copy this single file
into the pipeline and call ``upload_run(...)``, or use it from the command line:

    python pavewatch_upload.py path/to/payload.geojson --files path/to/evidence_dir \
        --url http://localhost:8000 [--api-key KEY] [--replace]

It performs the portal's three ingestion steps:
  1. POST the GeoJSON run submission (validated by the server)
  2. PUT every evidence file the server asks for (retried on network errors)
  3. POST complete -> the run becomes visible in the portal
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote


class IngestError(Exception):
    """The server refused something. ``.body`` holds the JSON error (detail + errors list)."""

    def __init__(self, status: int, body: Any, step: str):
        self.status = status
        self.body = body
        self.step = step
        super().__init__(self.pretty())

    def pretty(self) -> str:
        lines = [f"[{self.step}] HTTP {self.status}"]
        if isinstance(self.body, dict):
            lines.append(str(self.body.get("detail", "")))
            for e in self.body.get("errors") or []:
                lines.append(f"  - {e.get('path') or '(root)'}: {e.get('message')}")
            if self.body.get("ingestion_id"):
                lines.append(f"  ingestion_id: {self.body['ingestion_id']}")
        else:
            lines.append(str(self.body))
        return "\n".join(lines)


def _request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout: float, step: str) -> Any:
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw.decode("utf-8", "replace")
        raise IngestError(e.code, body, step) from None


def _with_retries(fn, attempts: int = 3):
    for i in range(attempts):
        try:
            return fn()
        except IngestError as e:
            if e.status < 500 or i == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == attempts - 1:
                raise
        time.sleep(1.5 * (i + 1))


def upload_run(
    base_url: str,
    payload: dict | str | Path,
    files_dir: str | Path,
    *,
    api_key: str | None = None,
    replace: bool = False,
    timeout: float = 120,
    verbose: bool = True,
) -> dict:
    """Upload one survey run. Returns the server's completion response.

    Raises ``IngestError`` with a readable list of problems if the server rejects it.
    """
    base = base_url.rstrip("/")
    files_dir = Path(files_dir)
    if not isinstance(payload, dict):
        payload = json.loads(Path(payload).read_text(encoding="utf-8"))
    auth = {"X-API-Key": api_key} if api_key else {}
    log = print if verbose else (lambda *a, **k: None)

    # Step 1
    run_id = payload.get("run", {}).get("run_id")
    log(f"-> submitting run {run_id}")
    accepted = _with_retries(
        lambda: _request(
            "POST",
            f"{base}/api/v1/ingest/runs?replace={'true' if replace else 'false'}",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json", **auth},
            timeout,
            "submit",
        )
    )
    ing_id = accepted["ingestion_id"]
    expected = accepted["files_expected"]
    log(f"   accepted (ingestion {ing_id}); {len(expected)} file(s) to upload")

    # Step 2
    missing_local = [f for f in expected if not (files_dir / f).is_file()]
    if missing_local:
        raise FileNotFoundError(f"Missing evidence files in {files_dir}: {', '.join(missing_local)}")
    for i, name in enumerate(expected, 1):
        path = files_dir / name
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        data = path.read_bytes()
        _with_retries(
            lambda: _request(
                "PUT",
                f"{base}/api/v1/ingest/{ing_id}/files/{quote(name)}",
                data,
                {"Content-Type": ctype, **auth},
                timeout,
                f"upload {name}",
            )
        )
        log(f"   [{i}/{len(expected)}] {name} ({len(data) / 1024:.0f} KB)")

    # Step 3
    done = _with_retries(
        lambda: _request("POST", f"{base}/api/v1/ingest/{ing_id}/complete", b"", auth, timeout, "complete")
    )
    log(f"<- published {done['run_id']}: {done['findings']} finding(s)" + (" (replaced)" if done["replaced_previous"] else ""))
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upload a PaveWatch survey run to the portal.")
    ap.add_argument("payload", help="GeoJSON run submission file")
    ap.add_argument("--files", help="Folder with the evidence files (default: the payload's folder)")
    ap.add_argument("--url", default="http://localhost:8000", help="Portal base URL")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--replace", action="store_true", help="Overwrite an existing run with the same run_id")
    args = ap.parse_args(argv)
    try:
        upload_run(
            args.url,
            args.payload,
            args.files or Path(args.payload).parent,
            api_key=args.api_key,
            replace=args.replace,
        )
    except IngestError as e:
        print(e.pretty(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
