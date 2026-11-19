"""Position helpers (same maths as ``frontend/src/lib/geo.ts``)."""

import math
from dataclasses import dataclass
from typing import Any

M_PER_DEG_LAT = 111_320.0


def local_to_lonlat(origin: dict[str, Any], x: float, y: float) -> tuple[float, float]:
    """Local survey frame -> (lon, lat). x points along heading_deg (0 = north, clockwise),
    y points 90 degrees clockwise from x. Metres."""
    h = math.radians(origin.get("heading_deg") or 0.0)
    east = x * math.sin(h) + y * math.cos(h)
    north = x * math.cos(h) - y * math.sin(h)
    lat = origin["lat"] + north / M_PER_DEG_LAT
    lon = origin["lon"] + east / (M_PER_DEG_LAT * math.cos(math.radians(origin["lat"])))
    return lon, lat


@dataclass(frozen=True)
class Position:
    lon: float
    lat: float
    approx: bool  # True when derived from the local frame because there was no GPS fix


def finding_position(f: Any, origin: dict[str, Any] | None) -> Position | None:
    if f.lat is not None and f.lon is not None:
        return Position(f.lon, f.lat, False)
    if origin and f.local_x_m is not None and f.local_y_m is not None:
        lon, lat = local_to_lonlat(origin, f.local_x_m, f.local_y_m)
        return Position(lon, lat, True)
    return None


def geometry_coords(g: dict[str, Any] | None) -> list[tuple[float, float]]:
    """All (lon, lat) pairs in a GeoJSON geometry of any type."""
    out: list[tuple[float, float]] = []

    def walk(c: Any) -> None:
        if not isinstance(c, list | tuple):
            return
        if len(c) >= 2 and isinstance(c[0], int | float) and isinstance(c[1], int | float):
            out.append((float(c[0]), float(c[1])))
        else:
            for item in c:
                walk(item)

    walk((g or {}).get("coordinates"))
    return out


def polygon_rings(g: dict[str, Any] | None) -> list[list[tuple[float, float]]]:
    """Outer rings of a Polygon / MultiPolygon (other geometry types give [])."""
    if not g:
        return []
    t, c = g.get("type"), g.get("coordinates") or []
    try:
        if t == "Polygon" and c:
            return [[(float(p[0]), float(p[1])) for p in c[0]]]
        if t == "MultiPolygon":
            return [[(float(p[0]), float(p[1])) for p in poly[0]] for poly in c if poly]
    except (TypeError, IndexError, ValueError):
        return []
    return []


def osm_link(lat: float, lon: float) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=20/{lat:.6f}/{lon:.6f}"
