import io

from conftest import ingest
from pypdf import PdfReader

BASE = "/api/v1/orgs/test-co/runs/PW-TEST-0001"


def _text(pdf: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(pdf))
    return len(reader.pages), "\n".join(p.extract_text() or "" for p in reader.pages)


def test_survey_report_pdf(client, payload):
    ingest(client, payload)
    r = client.get(f"{BASE}/report.pdf", params={"tz": "America/Toronto"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="PaveWatch_PW-TEST-0001_survey_report.pdf"' in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    pages, text = _text(r.content)
    # cover + map/breakdown + index + one page per finding (2)
    assert pages >= 5
    for expected in ("SURVEY REPORT", "Lot C", "Test Company", "Findings index", "F-0001", "F-0002",
                     "Area not scanned", "Low position confidence", "EST"):
        assert expected in text, expected


def test_finding_report_pdf(client, payload):
    ingest(client, payload)
    r = client.get(f"{BASE}/findings/F-0001/report.pdf")
    assert r.status_code == 200, r.text
    assert 'filename="PaveWatch_PW-TEST-0001_F-0001.pdf"' in r.headers["content-disposition"]
    _, text = _text(r.content)
    for expected in ("FINDING REPORT", "Pothole", "F-0001", "1 of 2", "Measurements", "0.42 m", "High severity",
                     "UTC"):
        assert expected in text, expected


def test_finding_without_gps_or_images_still_reports(client, payload):
    ingest(client, payload)
    r = client.get(f"{BASE}/findings/F-0002/report.pdf", params={"tz": "Not/AZone"})  # unknown zone -> UTC
    assert r.status_code == 200, r.text
    _, text = _text(r.content)
    assert "Approximate position" in text and "Approx. coordinates" in text
    assert "No measurements were provided" in text


def test_empty_run_report(client, payload):
    payload["features"] = []
    r = client.post("/api/v1/ingest/runs", json=payload)
    assert client.post(f"/api/v1/ingest/{r.json()['ingestion_id']}/complete").status_code == 200
    r = client.get(f"{BASE}/report.pdf")
    assert r.status_code == 200, r.text
    _, text = _text(r.content)
    assert "No defects were detected" in text


def test_report_404s(client, payload):
    ingest(client, payload)
    assert client.get(f"{BASE}/findings/F-9999/report.pdf").status_code == 404
    assert client.get("/api/v1/orgs/test-co/runs/NOPE/report.pdf").status_code == 404
    assert client.get("/api/v1/orgs/nobody/runs/PW-TEST-0001/report.pdf").status_code == 404
