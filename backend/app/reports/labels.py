"""Human-readable labels and number formatting for reports.

Mirrors ``frontend/src/lib/defects.ts`` and ``frontend/src/lib/format.ts`` so a
PDF says exactly what the portal says. Keep the two in sync when labels change.
"""

from datetime import UTC, datetime, tzinfo
from typing import Any

# ------------------------------------------------------------------ defect types

DEFECT_TYPES = ["pothole", "crack", "depression", "raised_area", "vertical_step", "other"]

_DEFECTS: dict[str, tuple[str, str]] = {
    # type: (label, glyph drawn in map markers)
    "pothole": ("Pothole", "P"),
    "crack": ("Crack", "C"),
    "depression": ("Depression", "D"),
    "raised_area": ("Raised area", "R"),
    "vertical_step": ("Vertical step", "S"),
    "other": ("Other", "O"),
}


def humanize(s: str) -> str:
    t = " ".join(s.replace("-", " ").replace("_", " ").split()).lower()
    return t[:1].upper() + t[1:]


def defect_label(t: str) -> str:
    return _DEFECTS.get(t, (humanize(t), ""))[0]


def defect_glyph(t: str) -> str:
    return _DEFECTS.get(t, ("", (t[:1] or "?").upper()))[1]


def defect_title(t: str, subtype: str | None = None) -> str:
    base = defect_label(t)
    if not subtype:
        return base
    return humanize(subtype) if t == "other" else f"{base} · {humanize(subtype).lower()}"


def defect_plural(t: str, n: int) -> str:
    """'3 potholes', '1 raised area', '2 other defects'."""
    if t == "other":
        word = "other defect"
    else:
        word = defect_label(t).lower()
    return f"{n} {word}{'' if n == 1 else 's'}"


# ------------------------------------------------------------------ severity

SEVERITIES = ["high", "medium", "low"]

# key: (label, fill colour, text colour on that fill, rank)
_SEVERITY: dict[str, tuple[str, str, str, int]] = {
    "high": ("High", "#d03b3b", "#ffffff", 3),
    "medium": ("Medium", "#fab219", "#22322f", 2),
    "low": ("Low", "#898781", "#ffffff", 1),
    "none": ("Not rated", "#c3c2b7", "#22322f", 0),
}


def severity_key(s: str | None) -> str:
    return s if s in ("high", "medium", "low") else "none"


def severity_label(s: str | None) -> str:
    return _SEVERITY[severity_key(s)][0]


def severity_colors(s: str | None) -> tuple[str, str]:
    """(fill, text) colours for a severity."""
    _, fill, ink, _ = _SEVERITY[severity_key(s)]
    return fill, ink


def severity_rank(s: str | None) -> int:
    return _SEVERITY[severity_key(s)][3]


# ------------------------------------------------------------------ data-quality warnings

_WARNINGS: dict[str, tuple[str, str]] = {
    "NOT_SCANNED": (
        "Area not scanned",
        "This area was not covered by the survey. No findings here does not mean the pavement is fine.",
    ),
    "NO_LIDAR_COVERAGE": (
        "No LiDAR data",
        "LiDAR returns are missing, so depths and heights could not be measured. Detection relied on images only.",
    ),
    "POSE_LOW_CONFIDENCE": (
        "Low position confidence",
        "The drone's position estimate was weak, so locations may be off by more than usual.",
    ),
    "SCAN_IMAGE_MISALIGNED": (
        "Scan and image misaligned",
        "LiDAR and camera data were not perfectly synchronised, so measurements may be less accurate.",
    ),
    "GPS_UNAVAILABLE": (
        "No GPS fix",
        "No GPS fix at detection time. The location is estimated from the drone's start point.",
    ),
}


def warning_label(code: str) -> str:
    return _WARNINGS.get(code, (humanize(code), ""))[0]


def warning_explain(code: str) -> str:
    return _WARNINGS.get(code, ("", ""))[1]


# ------------------------------------------------------------------ misc labels

SOURCE_LABEL = {"image": "Camera image", "lidar": "LiDAR scan", "fused": "Camera + LiDAR (fused)"}

_EVIDENCE_KIND = {
    "image_raw": "Raw frame",
    "image_closeup": "Close-up",
    "lidar_profile": "LiDAR profile",
    "lidar_scan": "3D scan",
}


def evidence_kind_label(kind: str) -> str:
    return _EVIDENCE_KIND.get(kind, humanize(kind))


# ------------------------------------------------------------------ numbers

_UNIT = {"m2": "m²", "m3": "m³", "cm2": "cm²", "deg": "°"}


def fmt_unit(u: str) -> str:
    return _UNIT.get(u, u)


def fmt_num(v: float, digits: int = 3) -> str:
    """1234.5 -> '1,234.5'; trailing zeros dropped."""
    s = f"{v:,.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def fmt_measurement(m: dict[str, Any]) -> str:
    try:
        return f"{fmt_num(float(m['value']))} {fmt_unit(str(m.get('unit', '')))}".strip()
    except (KeyError, TypeError, ValueError):
        return "—"


_MEASURE_ORDER = ["width", "length", "depth", "height", "max_width", "area", "volume"]


def sorted_measurements(ms: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    def key(item: tuple[str, Any]):
        name = item[0]
        return (_MEASURE_ORDER.index(name) if name in _MEASURE_ORDER else 99, name)

    return sorted(((k, v) for k, v in (ms or {}).items() if isinstance(v, dict)), key=key)


def measurement_summary(ms: dict[str, Any]) -> str:
    """Headline size, e.g. '0.42 × 0.51 m · 0.062 m deep' (same rules as the portal list)."""
    ms = ms or {}
    width, length, depth, height, max_width = (ms.get(k) for k in ("width", "length", "depth", "height", "max_width"))
    parts: list[str] = []
    try:
        if width and length and width.get("unit") == length.get("unit"):
            parts.append(f"{fmt_num(width['value'])} × {fmt_num(length['value'])} {fmt_unit(width['unit'])}")
        elif length:
            parts.append(f"{fmt_measurement(length)} long")
        elif width:
            parts.append(f"{fmt_measurement(width)} wide")
        if depth:
            parts.append(f"{fmt_measurement(depth)} deep")
        if height:
            parts.append(f"{fmt_measurement(height)} high")
        if max_width and not width:
            parts.append(f"up to {fmt_measurement(max_width)} wide")
    except (KeyError, TypeError, ValueError):
        pass
    return " · ".join(parts)


def fmt_percent(p: float | None) -> str:
    return "—" if p is None else f"{round(p * 100)}%"


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def fmt_coord(lat: float, lon: float) -> str:
    return f"{lat:.6f}, {lon:.6f}"


# ------------------------------------------------------------------ dates


def _local(d: datetime, tz: tzinfo) -> datetime:
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(tz)


def fmt_date(d: datetime | None, tz: tzinfo) -> str:
    if d is None:
        return "—"
    d = _local(d, tz)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def fmt_time(d: datetime | None, tz: tzinfo, with_zone: bool = True) -> str:
    if d is None:
        return "—"
    d = _local(d, tz)
    hour = d.hour % 12 or 12
    s = f"{hour}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"
    zone = d.tzname()
    return f"{s} {zone}" if with_zone and zone else s


def fmt_datetime(d: datetime | None, tz: tzinfo) -> str:
    if d is None:
        return "—"
    return f"{fmt_date(d, tz)}, {fmt_time(d, tz)}"


def fmt_duration(start: datetime, end: datetime | None) -> str | None:
    if end is None:
        return None
    minutes = round((end - start).total_seconds() / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min"
