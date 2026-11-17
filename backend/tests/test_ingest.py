from conftest import FILES, ingest, jpeg, upload_all

from app.config import Settings
from app.main import create_app


def test_full_flow_and_portal_reads(client, payload):
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending_files"
    assert sorted(body["files_expected"]) == sorted(FILES)
    ing_id = body["ingestion_id"]

    # Not visible before completion.
    assert client.get("/api/v1/orgs").json() == []

    upload_all(client, ing_id)
    status = client.get(f"/api/v1/ingest/{ing_id}").json()
    assert status["files_remaining"] == []

    r = client.post(f"/api/v1/ingest/{ing_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["findings"] == 2
    assert r.json()["portal_path"] == "/orgs/test-co/runs/PW-TEST-0001"

    # Completing again is safe.
    assert client.post(f"/api/v1/ingest/{ing_id}/complete").status_code == 200

    orgs = client.get("/api/v1/orgs").json()
    assert orgs[0]["org_id"] == "test-co"
    assert orgs[0]["run_count"] == 1 and orgs[0]["finding_count"] == 2 and orgs[0]["high_severity_count"] == 1

    runs = client.get("/api/v1/orgs/test-co/runs").json()
    assert runs[0]["counts_by_type"] == {"pothole": 1, "crack": 1}
    assert runs[0]["data_warning_count"] == 1
    assert runs[0]["findings_with_warnings"] == 1

    run = client.get("/api/v1/orgs/test-co/runs/PW-TEST-0001").json()
    assert run["data_warnings"][0]["code"] == "NOT_SCANNED"
    assert run["flight_path"]["type"] == "LineString"

    findings = client.get("/api/v1/orgs/test-co/runs/PW-TEST-0001/findings").json()
    assert [f["finding_id"] for f in findings] == ["F-0001", "F-0002"]
    assert findings[0]["thumb_url"].startswith("/files/")
    assert findings[1]["lat"] is None and findings[1]["local_x_m"] == 20.0

    d = client.get("/api/v1/orgs/test-co/runs/PW-TEST-0001/findings/F-0001").json()
    assert d["prev_finding_id"] is None and d["next_finding_id"] == "F-0002"
    assert d["lat"] == 43.6501 and d["lon"] == -79.3798
    raw = d["evidence"][0]
    assert raw["is_image"] and raw["width_px"] == 640 and raw["bounding_boxes"][0]["bbox"] == [100, 50, 300, 200]
    # Small image: preview is the original. Files are actually served.
    assert raw["preview_url"] == raw["url"]
    assert client.get(raw["url"]).status_code == 200
    assert client.get(raw["thumb_url"]).status_code == 200


def test_invalid_payload_is_rejected_with_paths_and_logged(client, payload):
    payload["features"][0]["properties"]["evidence"] = []
    payload["features"][1]["properties"]["finding_id"] = "F-0001"  # duplicate (reported once evidence is fixed)
    payload["run"]["status"] = "done"
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 422
    body = r.json()
    paths = {e["path"] for e in body["errors"]}
    assert "run.status" in paths
    assert "features[0].properties.evidence" in paths
    assert body["ingestion_id"]
    log = client.get(f"/api/v1/ingest/{body['ingestion_id']}").json()
    assert log["status"] == "rejected" and log["run_id"] == "PW-TEST-0001"


def test_duplicate_finding_ids_rejected(client, payload):
    payload["features"][1]["properties"]["finding_id"] = "F-0001"
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 422
    assert "duplicate finding_id" in r.text


def test_bbox_outside_declared_image_rejected(client, payload):
    payload["features"][0]["properties"]["evidence"][0]["bounding_boxes"][0]["bbox"] = [100, 50, 700, 200]
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 422
    assert "outside" in r.text


def test_finding_without_any_position_rejected(client, payload):
    payload["features"][1]["properties"].pop("position_local_m")
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 422
    assert "position_local_m" in r.text


def test_complete_with_missing_files_lists_them(client, payload):
    ing_id = client.post("/api/v1/ingest/runs", json=payload).json()["ingestion_id"]
    client.put(f"/api/v1/ingest/{ing_id}/files/F-0001_raw.jpg", content=jpeg(), headers={"Content-Type": "image/jpeg"})
    r = client.post(f"/api/v1/ingest/{ing_id}/complete")
    assert r.status_code == 409
    assert {e["path"] for e in r.json()["errors"]} == {"F-0001_profile.png", "F-0002_raw.jpg"}


def test_unknown_file_and_dimension_mismatch(client, payload):
    ing_id = client.post("/api/v1/ingest/runs", json=payload).json()["ingestion_id"]
    r = client.put(f"/api/v1/ingest/{ing_id}/files/nope.jpg", content=jpeg(), headers={"Content-Type": "image/jpeg"})
    assert r.status_code == 404
    r = client.put(
        f"/api/v1/ingest/{ing_id}/files/F-0001_raw.jpg", content=jpeg(800, 600), headers={"Content-Type": "image/jpeg"}
    )
    assert r.status_code == 422
    assert "width_px" in r.text
    r = client.put(
        f"/api/v1/ingest/{ing_id}/files/F-0002_raw.jpg", content=b"not an image", headers={"Content-Type": "image/jpeg"}
    )
    assert r.status_code == 422


def test_duplicate_run_needs_replace_and_replace_swaps_files(client, payload, settings):
    first = ingest(client, payload)
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 409
    assert "replace=true" in r.json()["detail"]

    old_dir = settings.storage_dir / "test-co" / "PW-TEST-0001" / first["ingestion_id"]
    assert old_dir.is_dir()

    payload["run"]["site_name"] = "Lot C (re-processed)"
    second = ingest(client, payload, replace=True)
    assert second["replaced_previous"] is True
    assert not old_dir.exists()
    assert client.get("/api/v1/orgs/test-co/runs").json()[0]["site_name"] == "Lot C (re-processed)"
    assert len(client.get("/api/v1/orgs/test-co/runs").json()) == 1


def test_run_id_cannot_be_taken_over_by_another_company(client, payload):
    ingest(client, payload)
    payload["run"]["company"] = {"company_id": "other-co", "name": "Other"}
    r = client.post("/api/v1/ingest/runs", json=payload, params={"replace": True})
    assert r.status_code == 409
    assert "another company" in r.json()["detail"]


def test_empty_run_is_valid(client, payload):
    payload["features"] = []
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert r.status_code == 201
    assert client.post(f"/api/v1/ingest/{r.json()['ingestion_id']}/complete").json()["findings"] == 0


def test_api_key_enforced_when_configured(tmp_path, payload):
    from fastapi.testclient import TestClient

    s = Settings(
        database_url=f"sqlite:///{(tmp_path / 'k.db').as_posix()}", storage_dir=tmp_path / "f", ingest_api_key="s3cret"
    )
    with TestClient(create_app(s)) as c:
        assert c.post("/api/v1/ingest/runs", json=payload).status_code == 401
        assert c.post("/api/v1/ingest/runs", json=payload, headers={"X-API-Key": "wrong"}).status_code == 401
        assert c.post("/api/v1/ingest/runs", json=payload, headers={"X-API-Key": "s3cret"}).status_code == 201
        assert c.get("/api/v1/orgs").status_code == 200  # portal reads stay open (no login yet)


def test_schema_endpoint(client):
    schema = client.get("/api/v1/ingest/schema").json()
    assert schema["title"].startswith("PaveWatch run submission")
    assert "RunInfo" in schema["$defs"]


def test_large_image_gets_preview(client, payload):
    payload["features"][0]["properties"]["evidence"][0].update(width_px=2400, height_px=1350)
    ing_id = client.post("/api/v1/ingest/runs", json=payload).json()["ingestion_id"]
    files = dict(FILES)
    files["F-0001_raw.jpg"] = (lambda: jpeg(2400, 1350), "image/jpeg")
    upload_all(client, ing_id, files)
    assert client.post(f"/api/v1/ingest/{ing_id}/complete").status_code == 200
    raw = client.get("/api/v1/orgs/test-co/runs/PW-TEST-0001/findings/F-0001").json()["evidence"][0]
    assert raw["preview_url"] != raw["url"] and "_preview" in raw["preview_url"]


def test_unknown_org_404(client):
    r = client.get("/api/v1/orgs/missing/runs")
    assert r.status_code == 404
    assert r.json()["detail"]
