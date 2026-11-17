# Sample run for the data sender

`sample_run/` is one complete, valid survey run exactly as the portal expects it:

- `payload.geojson`: the run submission (6 findings: cracks, potholes, a raised area; GPS and local positions; quality warnings; bounding boxes)
- `F-xxxx_*.jpg / .png`: the evidence files it references (raw frame, close-up crop, LiDAR profile)

The data is synthetic (fictional company and site) and was produced by `tools/synthetic/generate.py`. A backend test checks that it stays valid against the current schema.

Upload it to a running portal:

```bash
python tools/uploader/pavewatch_upload.py samples/sample_run/payload.geojson --url http://localhost:8000 --replace
```

Format details: [docs/ingestion-spec.md](../docs/ingestion-spec.md).
