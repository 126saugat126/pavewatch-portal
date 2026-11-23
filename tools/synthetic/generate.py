#!/usr/bin/env python3
"""Generate synthetic PaveWatch survey runs and push them through the real ingestion API.

    python tools/synthetic/generate.py                    # generate + upload to http://localhost:8000
    python tools/synthetic/generate.py --no-upload        # only write files to tools/synthetic/out/
    python tools/synthetic/generate.py --seed 7 --url http://localhost:8000 --api-key KEY

All companies, sites and people are fictional. Output is deterministic for a given seed.
Uploads use ?replace=true, so re-running simply refreshes the data.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "uploader"))

import render  # noqa: E402
from pavewatch_upload import IngestError, upload_run  # noqa: E402

SOFTWARE_VERSIONS = ["pw-proc 0.2.4", "pw-proc 0.3.0", "pw-proc 0.3.1"]
OPERATORS = ["R. Okafor", "J. Lindqvist", "M. Haddad", "S. Tremblay"]


@dataclass
class Site:
    name: str
    lat: float
    lon: float
    heading_deg: float
    width_m: float  # along x (heading)
    depth_m: float  # along y (right of heading)


@dataclass
class Company:
    company_id: str
    name: str
    sites: list[Site]
    runs: list[tuple[int, str, str]]  # (site index, ISO start time, special: ""|"incomplete"|"empty")


COMPANIES = [
    Company(
        "northgate-roads",
        "Northgate Municipal Roads",
        [
            Site("Civic Centre Lot B", 43.76152, -79.41108, 72, 64, 38),
            Site("Public Works Yard", 43.77011, -79.39876, 15, 80, 45),
            Site("Branch Library Lot", 43.75590, -79.42230, 105, 40, 26),
        ],
        [
            (0, "2026-06-18T14:10:00-04:00", ""),
            (1, "2026-08-05T09:32:00-04:00", ""),
            (0, "2026-10-21T13:45:00-04:00", ""),
            (2, "2026-11-14T15:02:00-05:00", "empty"),
        ],
    ),
    Company(
        "lakeshore-logistics",
        "Lakeshore Logistics Park",
        [
            Site("Dock Apron North", 43.58903, -79.64412, 0, 90, 40),
            Site("Truck Marshalling Yard", 43.58615, -79.63950, 38, 110, 55),
        ],
        [
            (0, "2026-07-09T07:15:00-04:00", ""),
            (1, "2026-09-16T06:50:00-04:00", ""),
            (0, "2026-11-03T08:05:00-05:00", ""),
        ],
    ),
    Company(
        "maple-ridge-university",
        "Maple Ridge University Facilities",
        [
            Site("Parking Lot X", 43.47231, -80.54490, 130, 70, 42),
            Site("Stadium Lot", 43.47610, -80.55230, 60, 95, 50),
        ],
        [
            (1, "2026-09-27T16:20:00-04:00", "incomplete"),
            (0, "2026-10-30T11:00:00-04:00", ""),
        ],
    ),
    Company(
        "harbourview-retail",
        "Harbourview Retail Centre",
        [Site("Main Customer Lot", 43.25570, -79.87110, 22, 85, 48)],
        [(0, "2026-10-12T07:40:00-04:00", "")],
    ),
]

DEFECTS = ["pothole", "crack", "depression", "raised_area", "vertical_step", "other"]
DEFECT_P = [0.30, 0.36, 0.12, 0.08, 0.08, 0.06]


# ----------------------------------------------------------------- geometry


def local_to_lonlat(site: Site, x: float, y: float) -> tuple[float, float]:
    """x along heading, y to the right of heading (metres) -> lon, lat."""
    h = math.radians(site.heading_deg)
    east = x * math.sin(h) + y * math.cos(h)
    north = x * math.cos(h) - y * math.sin(h)
    lat = site.lat + north / 111_320
    lon = site.lon + east / (111_320 * math.cos(math.radians(site.lat)))
    return round(lon, 7), round(lat, 7)


def lawnmower(site: Site, coverage: float, rng) -> list[tuple[float, float]]:
    """Local-frame survey path; coverage < 1 stops early (aborted flight)."""
    spacing = 5.0
    lanes = int(site.depth_m // spacing) + 1
    pts = [(0.0, 0.0)]
    for i in range(lanes):
        y = min(i * spacing, site.depth_m)
        xs = (0.0, site.width_m) if i % 2 == 0 else (site.width_m, 0.0)
        pts += [(xs[0] + rng.normal(0, 0.3), y + rng.normal(0, 0.2)), (xs[1] + rng.normal(0, 0.3), y + rng.normal(0, 0.2))]
    pts.append((0.0, 0.0))
    if coverage < 1:
        pts = pts[: max(3, int(len(pts) * coverage))]
    return pts


def rect_polygon(site: Site, x0, y0, x1, y1) -> dict:
    ring = [local_to_lonlat(site, x, y) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]
    return {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}


# ------------------------------------------------------------------ findings


def make_finding(rng, idx: int, site: Site, t: datetime, x: float, y: float, run_dir: Path, gps_ok: bool) -> dict:
    fid = f"F-{idx:04d}"
    dtype = rng.choice(DEFECTS, p=DEFECT_P)
    subtype = None
    measurements: dict = {}
    files: list[dict] = []
    qwarn: list[dict] = []
    conf = float(np.round(rng.uniform(0.62, 0.98), 2))
    lidar_ok = rng.random() > 0.12

    if dtype == "pothole":
        w, l = rng.uniform(0.25, 0.9), 0
        l = w * rng.uniform(0.7, 1.4)
        depth = rng.uniform(0.02, 0.11)
        r = render.pothole(rng, w, l)
        measurements = {
            "width": {"value": round(w, 2), "unit": "m"},
            "length": {"value": round(l, 2), "unit": "m"},
            "depth": {"value": round(depth, 3), "unit": "m"},
            "area": {"value": round(math.pi * w * l / 4, 2), "unit": "m2"},
        }
        severity = "high" if depth > 0.08 or w > 0.78 else "medium" if depth > 0.045 or w > 0.5 else "low"
        source = "fused" if lidar_ok else "image"
        desc = f"Pothole about {w * 100:.0f} x {l * 100:.0f} cm, {depth * 1000:.0f} mm deep. Edges ravelled; loose aggregate in the bowl."
        mag = depth
    elif dtype == "crack":
        subtype = str(rng.choice(["longitudinal", "transverse", "alligator", "block"], p=[0.35, 0.3, 0.2, 0.15]))
        length = rng.uniform(0.6, 2.4) if subtype != "alligator" else rng.uniform(0.8, 1.6)
        width_mm = rng.uniform(3, 18)
        r = render.crack(rng, length, width_mm, subtype)
        measurements = {"length": {"value": round(length, 2), "unit": "m"}, "max_width": {"value": round(width_mm, 1), "unit": "mm"}}
        if subtype == "alligator":
            measurements["area"] = {"value": round(length * length * 0.7, 2), "unit": "m2"}
        severity = "high" if subtype == "alligator" or width_mm > 14 else "medium" if width_mm > 7 else "low"
        source = "image"
        lidar_ok = False
        desc = f"{subtype.capitalize()} crack, {length:.1f} m long, up to {width_mm:.0f} mm wide."
        if subtype == "alligator":
            desc += " Interconnected cracking suggests base failure."
        mag = 0
    elif dtype in ("depression", "raised_area"):
        w = rng.uniform(0.6, 1.8)
        l = w * rng.uniform(0.8, 1.5)
        mag = rng.uniform(0.012, 0.045)
        r = render.depression(rng, w, l, raised=dtype == "raised_area")
        key = "depth" if dtype == "depression" else "height"
        measurements = {
            "width": {"value": round(w, 2), "unit": "m"},
            "length": {"value": round(l, 2), "unit": "m"},
            key: {"value": round(mag, 3), "unit": "m"},
        }
        severity = "medium" if mag > 0.03 else "low"
        source = "lidar" if rng.random() < 0.5 else "fused"
        lidar_ok = True
        desc = (
            f"Shallow depression {w:.1f} x {l:.1f} m, {mag * 1000:.0f} mm deep; likely ponds water."
            if dtype == "depression"
            else f"Raised area {w:.1f} x {l:.1f} m, {mag * 1000:.0f} mm high (possible heave or root intrusion)."
        )
    elif dtype == "vertical_step":
        length = rng.uniform(0.8, 3.0)
        mag = rng.uniform(0.008, 0.035)
        r = render.vertical_step(rng, length)
        measurements = {"height": {"value": round(mag * 1000, 1), "unit": "mm"}, "length": {"value": round(length, 2), "unit": "m"}}
        severity = "high" if mag > 0.025 else "medium" if mag > 0.013 else "low"
        source = "lidar"
        lidar_ok = True
        desc = f"Vertical offset of {mag * 1000:.0f} mm along a {length:.1f} m joint (trip hazard above 13 mm)."
    else:
        subtype = "debris"
        w = rng.uniform(0.3, 0.8)
        r = render.debris(rng, w)
        measurements = {"width": {"value": round(w, 2), "unit": "m"}}
        severity = "low"
        source = "image"
        lidar_ok = False
        desc = "Loose debris / gravel spill on the surface. Not structural, but may hide defects."
        mag = 0

    # --- evidence
    raw_name = f"{fid}_raw.jpg"
    (run_dir / raw_name).write_bytes(render.to_jpeg(r.image))
    files.append(
        {
            "file": raw_name,
            "kind": "image_raw",
            "caption": f"Nadir frame, {rng.uniform(5.2, 7.8):.1f} m AGL",
            "captured_at": t.isoformat(),
            "width_px": render.FRAME_W,
            "height_px": render.FRAME_H,
            "bounding_boxes": [{"label": r.label, "bbox": r.bbox, "confidence": conf}],
        }
    )
    if source in ("image", "fused"):
        crop, bb = render.closeup(r)
        name = f"{fid}_closeup.jpg"
        (run_dir / name).write_bytes(render.to_jpeg(crop, 88))
        files.append(
            {
                "file": name,
                "kind": "image_closeup",
                "caption": "Close-up crop from the raw frame",
                "captured_at": t.isoformat(),
                "width_px": crop.width,
                "height_px": crop.height,
                "bounding_boxes": [{"label": r.label, "bbox": bb, "confidence": conf}],
            }
        )
    if lidar_ok and source in ("lidar", "fused"):
        width_for_profile = measurements.get("width", measurements.get("length", {"value": 1.0}))["value"]
        name = f"{fid}_lidar_profile.png"
        png = render.lidar_profile_png(rng, str(dtype), float(width_for_profile), float(mag), f"{fid} - LiDAR cross-section")
        (run_dir / name).write_bytes(png)
        files.append({"file": name, "kind": "lidar_profile", "caption": "LiDAR cross-section through the deepest/highest point"})
    if dtype == "pothole" and not lidar_ok:
        qwarn.append({"code": "NO_LIDAR_COVERAGE", "message": "Depth estimated from imagery only"})

    # --- position & quality
    gps_acc = float(np.round(rng.uniform(0.4, 3.2), 1))
    if rng.random() < 0.15:
        qwarn.append({"code": "POSE_LOW_CONFIDENCE", "message": "Few GNSS satellites during this segment"})
        gps_acc = float(np.round(gps_acc + rng.uniform(1.5, 4), 1))
    if rng.random() < 0.08:
        qwarn.append({"code": "SCAN_IMAGE_MISALIGNED", "message": "LiDAR and image timestamps differ by > 40 ms"})

    geometry = None
    if gps_ok:
        nx, ny = x + rng.normal(0, gps_acc / 2), y + rng.normal(0, gps_acc / 2)
        lon, lat = local_to_lonlat(site, nx, ny)
        geometry = {"type": "Point", "coordinates": [lon, lat]}
    else:
        qwarn.append({"code": "GPS_UNAVAILABLE", "message": "No GNSS fix; only the local position is known"})

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "finding_id": fid,
            "detected_at": t.isoformat(),
            "defect_type": str(dtype),
            "subtype": subtype,
            "description": desc,
            "severity": severity,
            "confidence": conf,
            "detection_source": source,
            "gps_accuracy_m": gps_acc if gps_ok else None,
            "position_local_m": {"x": round(x, 2), "y": round(y, 2)},
            "measurements": measurements,
            "quality_warnings": qwarn,
            "evidence": files,
        },
    }


# ---------------------------------------------------------------------- runs


def make_run(rng, company: Company, site: Site, start_iso: str, special: str, aircraft: str, out: Path) -> tuple[dict, Path]:
    started = datetime.fromisoformat(start_iso)
    run_id = f"PW-{started.strftime('%Y%m%d-%H%M')}-{aircraft[-2:]}"
    run_dir = out / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    coverage = rng.uniform(0.5, 0.65) if special == "incomplete" else 1.0
    path_local = lawnmower(site, coverage, rng)
    flight_minutes = 4 + (site.width_m * site.depth_m) / 260 * coverage
    ended = started + timedelta(minutes=flight_minutes)

    warnings: list[dict] = []
    if special == "incomplete":
        covered_y = max(p[1] for p in path_local)
        warnings.append(
            {
                "code": "NOT_SCANNED",
                "message": f"Flight aborted at {coverage * 100:.0f}% coverage (low battery). Remaining area not surveyed.",
                "geometry": rect_polygon(site, 0, covered_y + 2.5, site.width_m, site.depth_m),
            }
        )
    elif rng.random() < 0.6:
        x0 = rng.uniform(0, site.width_m * 0.6)
        y0 = rng.uniform(0, site.depth_m * 0.6)
        warnings.append(
            {
                "code": "NOT_SCANNED",
                "message": "Area blocked by parked vehicles",
                "geometry": rect_polygon(site, x0, y0, x0 + rng.uniform(6, 14), y0 + rng.uniform(4, 9)),
            }
        )
    if rng.random() < 0.45:
        y0 = rng.uniform(0, site.depth_m * 0.7)
        warnings.append(
            {
                "code": "NO_LIDAR_COVERAGE",
                "message": "LiDAR returns dropped (wet surface glare)",
                "geometry": rect_polygon(site, 0, y0, site.width_m, y0 + rng.uniform(3, 6)),
            }
        )
    if rng.random() < 0.3:
        warnings.append({"code": "POSE_LOW_CONFIDENCE", "message": "GNSS degraded for ~40 s near the building edge"})

    n = 0 if special == "empty" else int(rng.integers(5, 15))
    max_y = max(p[1] for p in path_local) if special == "incomplete" else site.depth_m
    positions = sorted(
        ((float(rng.uniform(2, site.width_m - 2)), float(rng.uniform(2, max(3, max_y - 2)))) for _ in range(n)),
        key=lambda p: (round(p[1] / 5), p[0]),
    )
    features = []
    for i, (x, y) in enumerate(positions, 1):
        t = started + timedelta(minutes=1 + (flight_minutes - 2) * i / (n + 1))
        features.append(make_finding(rng, i, site, t, x, y, run_dir, gps_ok=rng.random() > 0.08))

    payload = {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "run": {
            "run_id": run_id,
            "company": {"company_id": company.company_id, "name": company.name},
            "site_name": site.name,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "status": "incomplete" if special == "incomplete" else "complete",
            "aircraft_id": aircraft,
            "operator": str(rng.choice(OPERATORS)),
            "software_version": str(rng.choice(SOFTWARE_VERSIONS[-2:] if started.month >= 9 else SOFTWARE_VERSIONS)),
            "local_frame_origin": {"lat": site.lat, "lon": site.lon, "alt_m": round(float(rng.uniform(75, 190)), 1), "heading_deg": float(site.heading_deg)},
            "flight_path": {"type": "LineString", "coordinates": [list(local_to_lonlat(site, x, y)) for x, y in path_local]},
            "data_warnings": warnings,
        },
        "features": features,
    }
    (run_dir / "payload.geojson").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload, run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=HERE / "out")
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[dict, Path]] = []
    for c in COMPANIES:
        for site_idx, start, special in c.runs:
            aircraft = "PW-01" if rng.random() < 0.7 else "PW-02"
            payload, run_dir = make_run(rng, c, c.sites[site_idx], start, special, aircraft, args.out)
            print(f"generated {payload['run']['run_id']:<24} {c.name:<36} {len(payload['features']):>2} findings")
            generated.append((payload, run_dir))

    # A small, complete example for the data sender.
    small = [(p, d) for p, d in generated if p["run"]["status"] == "complete" and 4 <= len(p["features"]) <= 8]
    _, sample_dir = small[0] if small else generated[0]
    sample_out = ROOT / "samples" / "sample_run"
    if sample_out.exists():
        shutil.rmtree(sample_out)
    shutil.copytree(sample_dir, sample_out)
    print(f"sample run copied to {sample_out.relative_to(ROOT)}")

    if args.no_upload:
        return 0
    failures = 0
    for payload, run_dir in generated:
        try:
            upload_run(args.url, payload, run_dir, api_key=args.api_key, replace=True, verbose=False)
            print(f"uploaded  {payload['run']['run_id']}")
        except IngestError as e:
            failures += 1
            print(e.pretty(), file=sys.stderr)
        except OSError as e:
            print(f"Could not reach {args.url}: {e}. Is the backend running?", file=sys.stderr)
            return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
