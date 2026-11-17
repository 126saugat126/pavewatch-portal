"""Guards for what we hand to the data sender: the published schema and the sample must stay valid."""

import json
from pathlib import Path

from app.export_schema import DEFAULT_PATH, render
from app.schemas.ingest import RunSubmission

ROOT = Path(__file__).resolve().parents[2]


def test_published_json_schema_is_up_to_date():
    assert DEFAULT_PATH.is_file(), "run `python -m app.export_schema` to create docs/run-submission.schema.json"
    assert DEFAULT_PATH.read_text(encoding="utf-8") == render(), (
        "docs/run-submission.schema.json is stale - run `python -m app.export_schema`"
    )


def test_sample_payload_is_valid_and_complete():
    sample_dir = ROOT / "samples" / "sample_run"
    payload = json.loads((sample_dir / "payload.geojson").read_text(encoding="utf-8"))
    sub = RunSubmission.model_validate(payload)
    missing = [f for f in sub.evidence_files() if not (sample_dir / f).is_file()]
    assert not missing, f"sample references files that are not in samples/sample_run: {missing}"


def test_sample_passes_the_published_json_schema():
    """Non-Python senders validate with the JSON Schema file, so it must accept a real payload
    (and reject an obviously broken one) using a standard validator."""
    import jsonschema

    schema = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    payload = json.loads((ROOT / "samples" / "sample_run" / "payload.geojson").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(payload, schema, cls=jsonschema.Draft202012Validator)

    payload["run"]["status"] = "finished"
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(payload))
    assert errors, "schema should reject an invalid run.status"
