"""Static map images for PDF reports, drawn with Pillow.

The base layer is OpenStreetMap raster tiles (cached on disk). When tiles cannot
be fetched (offline, blocked, disabled with ``PW_REPORT_BASEMAP=false``), the map
falls back to a plain site plan with a metre grid, so a report is always produced.
The overlays (flight path, unscanned areas, markers, scale bar) are identical in
both cases.

OSM's tile servers are fine for local development and demos. Before a public
deployment point ``PW_REPORT_TILE_URL`` at a provider with a usage plan, the same
advice as for the web map in ``frontend/src/components/map/basemap.ts``.
"""

import io
import logging
import math
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

log = logging.getLogger(__name__)

TILE = 256
MAX_TILE_ZOOM = 19
USER_AGENT = "PaveWatch-Portal/0.1 (pavement survey reports; capstone demo)"
OSM_ATTRIBUTION = "© OpenStreetMap contributors"

# Colours (match the portal's map)
BG = (238, 241, 236)
GRID = (214, 220, 212)
PATH = (47, 111, 223)
HALO = (255, 255, 255)
UNSCANNED_FILL = (224, 161, 15, 60)
UNSCANNED_LINE = (176, 120, 0, 255)
INK = (34, 50, 47)


# ------------------------------------------------------------------ tiles


class TileSource:
    """Fetches raster tiles with a small disk cache. Thread-safe.

    After a network failure, fetching pauses for a minute so an offline machine
    does not wait for timeouts on every report.
    """

    def __init__(self, url_template: str, cache_dir: Path, timeout_s: float = 4.0, max_age_days: int = 30):
        self.url_template = url_template
        self.cache_dir = Path(cache_dir)
        self.timeout_s = timeout_s
        self.max_age_s = max_age_days * 86400
        self._offline_until = 0.0
        self._lock = threading.Lock()

    @property
    def offline(self) -> bool:
        return time.monotonic() < self._offline_until

    def _mark_offline(self) -> None:
        with self._lock:
            self._offline_until = time.monotonic() + 60

    def get(self, z: int, x: int, y: int) -> Image.Image | None:
        path = self.cache_dir / str(z) / str(x) / f"{y}.png"
        try:
            if path.is_file() and time.time() - path.stat().st_mtime < self.max_age_s:
                return Image.open(path).convert("RGB")
        except OSError:
            pass
        if self.offline:
            return None
        url = self.url_template.format(z=z, x=x, y=y, s="a")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:  # network, HTTP or decode error: fall back
            log.info("Map tile %s/%s/%s unavailable: %s", z, x, y, e)
            self._mark_offline()
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        except OSError:
            pass
        return img


# ------------------------------------------------------------------ projection


def _world_px(lon: float, lat: float, z: float) -> tuple[float, float]:
    n = TILE * 2.0**z
    lat = max(-85.05, min(85.05, lat))
    r = math.radians(lat)
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n
    return x, y


def _m_per_px(lat: float, z: float) -> float:
    return 156_543.033_92 * math.cos(math.radians(lat)) / 2.0**z


# ------------------------------------------------------------------ fonts


def load_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    names = (
        ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


# ------------------------------------------------------------------ map spec


@dataclass
class Marker:
    lon: float
    lat: float
    fill: str  # hex
    ink: str  # text colour on the fill
    label: str = ""
    approx: bool = False
    accuracy_m: float | None = None


@dataclass
class MapSpec:
    width: int
    height: int
    markers: list[Marker] = field(default_factory=list)
    path: list[tuple[float, float]] = field(default_factory=list)
    unscanned: list[list[tuple[float, float]]] = field(default_factory=list)
    center: tuple[float, float] | None = None  # (lon, lat); None = fit everything
    zoom: float | None = None  # None = fit everything
    max_fit_zoom: float = 20.0
    marker_radius: int = 18
    ui_scale: float = 1.0  # size of scale bar, north arrow, lines (maps printed small need more)


@dataclass
class RenderedMap:
    data: bytes  # JPEG
    width: int
    height: int
    basemap: bool  # True when street tiles were drawn
    attribution: str | None
    accuracy_drawn: bool = False  # a GPS accuracy circle was large enough to draw


def _hex(c: str, alpha: int | None = None) -> tuple[int, ...]:
    c = c.lstrip("#")
    rgb = tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))
    return rgb if alpha is None else (*rgb, alpha)


def _fit(spec: MapSpec) -> tuple[tuple[float, float], float]:
    pts = [(m.lon, m.lat) for m in spec.markers] + list(spec.path) + [p for ring in spec.unscanned for p in ring]
    if spec.center and spec.zoom is not None:
        return spec.center, spec.zoom
    if not pts:
        return spec.center or (0.0, 0.0), spec.zoom if spec.zoom is not None else 2.0
    w, e = min(p[0] for p in pts), max(p[0] for p in pts)
    s, n = min(p[1] for p in pts), max(p[1] for p in pts)
    center = spec.center or ((w + e) / 2, (s + n) / 2)
    if spec.zoom is not None:
        return center, spec.zoom
    pad = spec.marker_radius * 2 + 30
    x0, y0 = _world_px(w, n, 0)
    x1, y1 = _world_px(e, s, 0)
    dx, dy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    z = min(math.log2((spec.width - 2 * pad) / dx), math.log2((spec.height - 2 * pad) / dy))
    return center, max(1.0, min(spec.max_fit_zoom, z))


def _basemap(tiles: TileSource, center: tuple[float, float], z: float, w: int, h: int) -> Image.Image | None:
    """Street tiles for the view, resampled to the (possibly fractional) zoom. None if no tile loaded."""
    tz = min(MAX_TILE_ZOOM, max(0, round(z)))
    factor = 2.0 ** (z - tz)  # output px per tile px
    cw, ch = math.ceil(w / factor), math.ceil(h / factor)
    cx, cy = _world_px(center[0], center[1], tz)
    left, top = cx - cw / 2, cy - ch / 2
    n = 2**tz
    tx0, ty0 = math.floor(left / TILE), math.floor(top / TILE)
    tx1, ty1 = math.floor((left + cw) / TILE), math.floor((top + ch) / TILE)
    jobs = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1) if 0 <= ty < n]
    if not jobs or len(jobs) > 80:  # guard against absurd requests
        return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda t: tiles.get(tz, t[0] % n, t[1]), jobs))
    if not any(results):
        return None
    canvas = Image.new("RGB", (cw, ch), BG)
    for (tx, ty), img in zip(jobs, results, strict=True):
        if img is not None:
            canvas.paste(img, (round(tx * TILE - left), round(ty * TILE - top)))
    if (cw, ch) != (w, h):
        canvas = canvas.resize((w, h), Image.LANCZOS)
    # Mute the colours so markers and the blue flight path stand out (as on the web map).
    canvas = ImageEnhance.Color(canvas).enhance(0.45)
    canvas = ImageEnhance.Brightness(canvas).enhance(1.04)
    return canvas


def _nice(x: float) -> float:
    """Largest 1/2/5 x 10^k not above x."""
    if x <= 0:
        return 1.0
    k = 10 ** math.floor(math.log10(x))
    for m in (5, 2, 1):
        if m * k <= x:
            return m * k
    return k


def _fmt_m(m: float) -> str:
    if m >= 1000:
        return f"{m / 1000:g} km"
    return f"{m:g} m"


def _dashed_circle(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color, width: int, dash_deg: int = 14) -> None:
    box = [cx - r, cy - r, cx + r, cy + r]
    for a in range(0, 360, dash_deg * 2):
        d.arc(box, a, a + dash_deg, fill=color, width=width)


def render_map(spec: MapSpec, tiles: TileSource | None) -> RenderedMap:
    w, h = spec.width, spec.height
    center, z = _fit(spec)
    base = _basemap(tiles, center, z, w, h) if tiles else None
    img = base if base is not None else Image.new("RGB", (w, h), BG)
    mpp = _m_per_px(center[1], z)
    ccx, ccy = _world_px(center[0], center[1], z)

    def px(lon: float, lat: float) -> tuple[float, float]:
        x, y = _world_px(lon, lat, z)
        return x - ccx + w / 2, y - ccy + h / 2

    s = max(1.0, w / 1000) * spec.ui_scale  # stroke / furniture scale

    # Plain site plan: metre grid instead of streets.
    if base is None:
        d = ImageDraw.Draw(img)
        step_m = _nice(mpp * w / 8)
        step_px = step_m / mpp
        if step_px > 8:
            ox = (w / 2) % step_px
            oy = (h / 2) % step_px
            x = ox
            while x < w:
                d.line([(x, 0), (x, h)], fill=GRID, width=1)
                x += step_px
            y = oy
            while y < h:
                d.line([(0, y), (w, y)], fill=GRID, width=1)
                y += step_px

    # Unscanned areas (translucent fill + outline)
    if spec.unscanned:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for ring in spec.unscanned:
            pts = [px(*p) for p in ring]
            if len(pts) >= 3:
                ld.polygon(pts, fill=UNSCANNED_FILL)
                ld.line([*pts, pts[0]], fill=UNSCANNED_LINE, width=round(2 * s), joint="curve")
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    d = ImageDraw.Draw(img)

    # Flight path
    if len(spec.path) >= 2:
        pts = [px(*p) for p in spec.path]
        d.line(pts, fill=HALO, width=round(6 * s), joint="curve")
        d.line(pts, fill=PATH, width=round(3 * s), joint="curve")
        # start point
        x0, y0 = pts[0]
        r0 = 5 * s
        d.ellipse([x0 - r0, y0 - r0, x0 + r0, y0 + r0], fill=HALO, outline=PATH, width=round(2 * s))

    # Accuracy circles under the markers
    accuracy_drawn = False
    for m in spec.markers:
        if m.accuracy_m and m.accuracy_m / mpp > spec.marker_radius * 1.2:
            accuracy_drawn = True
            x, y = px(m.lon, m.lat)
            _dashed_circle(d, x, y, m.accuracy_m / mpp, _hex(m.fill), max(1, round(2 * s)))

    # Markers: high severity drawn last so it sits on top
    r = spec.marker_radius
    font = load_font(round(r * (1.05 if len(max((m.label for m in spec.markers), key=len, default="")) <= 2 else 0.85)))
    for m in spec.markers:
        x, y = px(m.lon, m.lat)
        ro = r + max(1.5, r * 0.1)
        d.ellipse([x - ro, y - ro, x + ro, y + ro], fill=(40, 52, 50))  # thin dark rim keeps white edge visible
        d.ellipse([x - r, y - r, x + r, y + r], fill=_hex(m.fill), outline=HALO, width=max(2, round(r * 0.16)))
        if m.approx:
            _dashed_circle(d, x, y, r + max(3, r * 0.3), INK, max(1, round(s * 1.5)), dash_deg=20)
        if m.label:
            d.text((x, y + 0.5), m.label, fill=_hex(m.ink), font=font, anchor="mm")

    # Scale bar (bottom-left)
    bar_m = _nice(mpp * w * 0.18)
    bar_px = bar_m / mpp
    f_small = load_font(round(13 * s), bold=False)
    bx, by = round(14 * s), h - round(14 * s)
    label = _fmt_m(bar_m)
    tw = d.textlength(label, font=f_small)
    d.rectangle([bx - 6 * s, by - 26 * s, bx + max(bar_px, tw) + 8 * s, by + 6 * s], fill=(255, 255, 255))
    d.line([(bx, by), (bx + bar_px, by)], fill=INK, width=round(3 * s))
    d.line([(bx, by - 6 * s), (bx, by)], fill=INK, width=round(2 * s))
    d.line([(bx + bar_px, by - 6 * s), (bx + bar_px, by)], fill=INK, width=round(2 * s))
    d.text((bx, by - 9 * s), label, fill=INK, font=f_small, anchor="ls")

    # North arrow (top-right)
    nx, ny = w - round(26 * s), round(20 * s)
    d.ellipse([nx - 15 * s, ny - 6 * s, nx + 15 * s, ny + 40 * s], fill=(255, 255, 255))
    d.polygon([(nx, ny), (nx - 7 * s, ny + 16 * s), (nx + 7 * s, ny + 16 * s)], fill=INK)
    d.text((nx, ny + 28 * s), "N", fill=INK, font=load_font(round(13 * s)), anchor="mm")

    attribution = OSM_ATTRIBUTION if base is not None else None
    if attribution:
        tw = d.textlength(attribution, font=f_small)
        ax, ay = w - tw - 10 * s, h - 6 * s
        d.rectangle([ax - 6 * s, ay - 18 * s, w, h], fill=(255, 255, 255))
        d.text((ax, ay), attribution, fill=(70, 80, 78), font=f_small, anchor="ls")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return RenderedMap(data=buf.getvalue(), width=w, height=h, basemap=base is not None, attribution=attribution,
                       accuracy_drawn=accuracy_drawn)
