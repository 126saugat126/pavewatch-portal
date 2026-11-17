"""Write the run-submission JSON Schema to docs/ for the data sender.

    python -m app.export_schema            # writes ../docs/run-submission.schema.json
    python -m app.export_schema out.json   # custom path

A test fails if the committed file is out of date, so re-run this after
changing app/schemas/ingest.py.
"""

import json
import sys
from pathlib import Path

from app.schemas.ingest import json_schema

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "docs" / "run-submission.schema.json"


def render() -> str:
    return json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
