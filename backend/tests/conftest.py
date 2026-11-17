import copy
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        storage_dir=tmp_path / "files",
        ingest_api_key="",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def jpeg(width=640, height=360, color=(90, 90, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


def png(width=400, height=200) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), (255, 255, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


BASE_PAYLOAD = {
    "type": "FeatureCollection",
    "schema_version": "1.0",
    "run": {
        "run_id": "PW-TEST-0001",
        "company": {"company_id": "test-co", "name": "Test Company"},
        "site_name": "Lot C",
        "started_at": "2026-11-14T15:02:00Z",
        "ended_at": "2026-11-14T15:20:00Z",
        "status": "complete",
        "software_version": "pw-proc 0.3.1",
        "local_frame_origin": {"lat": 43.65, "lon": -79.38, "alt_m": 80, "heading_deg": 90},
        "flight_path": {"type": "LineString", "coordinates": [[-79.38, 43.65], [-79.3795, 43.65]]},
        "data_warnings": [
            {
                "code": "NOT_SCANNED",
                "message": "North corner blocked by a parked truck",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-79.38, 43.65], [-79.3799, 43.65], [-79.3799, 43.6501], [-79.38, 43.65]]],
                },
            }
        ],
    },
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-79.3798, 43.6501]},
            "properties": {
                "finding_id": "F-0001",
                "detected_at": "2026-11-14T15:05:00Z",
                "defect_type": "pothole",
                "severity": "high",
                "confidence": 0.91,
                "detection_source": "fused",
                "gps_accuracy_m": 1.5,
                "position_local_m": {"x": 12.4, "y": 3.1},
                "measurements": {"width": {"value": 0.42, "unit": "m"}, "depth": {"value": 0.06, "unit": "m"}},
                "quality_warnings": [{"code": "POSE_LOW_CONFIDENCE"}],
                "evidence": [
                    {
                        "file": "F-0001_raw.jpg",
                        "kind": "image_raw",
                        "width_px": 640,
                        "height_px": 360,
                        "bounding_boxes": [{"label": "pothole", "bbox": [100, 50, 300, 200], "confidence": 0.91}],
                    },
                    {"file": "F-0001_profile.png", "kind": "lidar_profile"},
                ],
            },
        },
        {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "finding_id": "F-0002",
                "detected_at": "2026-11-14T15:06:00Z",
                "defect_type": "crack",
                "subtype": "longitudinal",
                "position_local_m": {"x": 20.0, "y": 1.0},
                "evidence": [{"file": "F-0002_raw.jpg", "kind": "image_raw"}],
            },
        },
    ],
}

FILES = {
    "F-0001_raw.jpg": (jpeg, "image/jpeg"),
    "F-0001_profile.png": (png, "image/png"),
    "F-0002_raw.jpg": (jpeg, "image/jpeg"),
}


@pytest.fixture
def payload():
    return copy.deepcopy(BASE_PAYLOAD)


def upload_all(client, ingestion_id, files=FILES, headers=None):
    for name, (maker, ctype) in files.items():
        r = client.put(
            f"/api/v1/ingest/{ingestion_id}/files/{name}",
            content=maker(),
            headers={"Content-Type": ctype, **(headers or {})},
        )
        assert r.status_code == 200, r.text


def ingest(client, payload, replace=False):
    r = client.post("/api/v1/ingest/runs", json=payload, params={"replace": replace})
    assert r.status_code == 201, r.text
    ing_id = r.json()["ingestion_id"]
    upload_all(client, ing_id)
    r = client.post(f"/api/v1/ingest/{ing_id}/complete")
    assert r.status_code == 200, r.text
    return r.json()
