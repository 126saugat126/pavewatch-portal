"""Procedural pavement imagery for synthetic PaveWatch data.

Every function returns the image plus pixel-accurate bounding boxes so the
portal's bbox overlay can be checked visually.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

# Pi Camera Module 3 frames, downscaled 2x to keep the demo data light.
FRAME_W, FRAME_H = 2304, 1296
# Ground sampling distance at ~6 m AGL with the Pi Cam 3 (66 deg HFOV), at this resolution.
GSD_M_PER_PX = 0.0034


@dataclass
class Rendered:
    image: Image.Image
    bbox: list[float]  # [x0, y0, x1, y1] in pixels
    label: str


def _low_freq(rng: np.random.Generator, w: int, h: int, cells: int, blur: float) -> np.ndarray:
    small = rng.normal(0, 1, (max(2, h // cells), max(2, w // cells))).astype(np.float32)
    img = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-6) * 255).astype(np.uint8))
    img = img.resize((w, h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(img, dtype=np.float32) / 255.0 - 0.5


def asphalt(rng: np.random.Generator, w: int = FRAME_W, h: int = FRAME_H) -> np.ndarray:
    """Float32 HxWx3 array (0-255) of weathered asphalt."""
    tone = rng.uniform(78, 112)
    g = np.full((h, w), tone, np.float32)
    g += 22 * _low_freq(rng, w, h, 160, 30)  # patches / stains
    g += 9 * _low_freq(rng, w, h, 12, 1.5)  # mid texture
    g += rng.normal(0, 7, (h, w)).astype(np.float32)  # grain
    agg = rng.random((h, w)) > 0.988  # light aggregate stones
    g[agg] += rng.uniform(20, 45)
    dark = rng.random((h, w)) > 0.993
    g[dark] -= 25
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    g = np.asarray(img, np.float32)
    tint = np.array([1.0, 0.99, 0.965], np.float32) * rng.uniform(0.97, 1.03)
    return g[..., None] * tint


def _markings(rng: np.random.Generator, arr: np.ndarray) -> None:
    """Worn parking-stall stripes, sometimes."""
    if rng.random() < 0.45:
        return
    h, w, _ = arr.shape
    yellow = rng.random() < 0.3
    color = np.array([205, 170, 60] if yellow else [215, 215, 205], np.float32)
    angle = rng.uniform(-0.12, 0.12)
    spacing = rng.uniform(700, 900)
    x = rng.uniform(0, spacing)
    wear = 0.55 + 0.45 * (_low_freq(rng, w, h, 40, 4) + 0.5)
    yy, xx = np.mgrid[0:h, 0:w]
    while x < w:
        dist = np.abs((xx - x) - (yy - h / 2) * math.tan(angle))
        stripe = np.clip(1 - (dist - 18) / 3, 0, 1) * wear
        arr[:] = arr * (1 - stripe[..., None]) + color * stripe[..., None]
        x += spacing


def _finish(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _place(rng: np.random.Generator, half_w: float, half_h: float) -> tuple[float, float]:
    margin_x, margin_y = half_w + 60, half_h + 60
    cx = rng.uniform(margin_x, FRAME_W - margin_x) if FRAME_W > 2 * margin_x else FRAME_W / 2
    cy = rng.uniform(margin_y, FRAME_H - margin_y) if FRAME_H > 2 * margin_y else FRAME_H / 2
    # bias towards the centre third, as a nadir camera over the target would be
    return (cx + FRAME_W / 2) / 2, (cy + FRAME_H / 2) / 2


def _blob_mask(rng, cx, cy, rx, ry, rough=0.18):
    h, w = FRAME_H, FRAME_W
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (xx - cx) / rx, (yy - cy) / ry
    theta = np.arctan2(dy, dx)
    r = np.sqrt(dx**2 + dy**2)
    edge = np.ones_like(theta)
    for k in range(2, 7):
        edge += rng.uniform(0, rough / k * 2) * np.sin(k * theta + rng.uniform(0, 2 * np.pi))
    return r / edge  # < 1 inside


def pothole(rng: np.random.Generator, width_m: float, length_m: float) -> Rendered:
    arr = asphalt(rng)
    _markings(rng, arr)
    rx, ry = width_m / GSD_M_PER_PX / 2, length_m / GSD_M_PER_PX / 2
    cx, cy = _place(rng, rx * 1.3, ry * 1.3)
    rn = _blob_mask(rng, cx, cy, rx, ry, rough=0.3)
    inside = rn < 1
    # depth shading: darker towards the centre and on the "shadow" side
    yy, xx = np.mgrid[0:FRAME_H, 0:FRAME_W].astype(np.float32)
    shade = 0.42 + 0.18 * np.clip(rn, 0, 1) + 0.08 * np.clip((xx - cx) / rx, -1, 1)
    gravel = 1 + 0.25 * rng.normal(0, 1, rn.shape).astype(np.float32)
    arr[inside] *= (shade * gravel)[inside, None]
    rim = (rn >= 1) & (rn < 1.12)
    arr[rim] *= 1.18
    crumb = (rn >= 1.12) & (rn < 1.45) & (rng.random(rn.shape) > 0.97)
    arr[crumb] *= 0.6
    ys, xs = np.nonzero(rn < 1.12)
    return Rendered(_finish(arr), [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)], "pothole")


def depression(rng: np.random.Generator, width_m: float, length_m: float, raised: bool = False) -> Rendered:
    arr = asphalt(rng)
    _markings(rng, arr)
    rx, ry = width_m / GSD_M_PER_PX / 2, length_m / GSD_M_PER_PX / 2
    cx, cy = _place(rng, rx, ry)
    rn = _blob_mask(rng, cx, cy, rx, ry, rough=0.12)
    weight = np.clip(1 - rn, 0, 1) ** 0.8
    factor = 1 + (0.20 if raised else -0.26) * weight
    if raised:  # hairline cracking on the crest of the heave
        factor -= 0.10 * ((rn > 0.25) & (rn < 0.29))
    else:  # damp patch / standing-water stain
        factor -= 0.06 * weight * (_low_freq(rng, FRAME_W, FRAME_H, 30, 4) + 0.5)
    factor -= 0.07 * ((rn > 0.93) & (rn < 1.0))  # faint outline where the surface bends
    arr *= factor[..., None]
    ys, xs = np.nonzero(rn < 0.95)
    label = "raised_area" if raised else "depression"
    return Rendered(_finish(arr), [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)], label)


def _walk(rng, x, y, angle, steps, step_len, wobble):
    pts = [(x, y)]
    for _ in range(steps):
        angle += rng.normal(0, wobble)
        x += math.cos(angle) * step_len
        y += math.sin(angle) * step_len
        pts.append((x, y))
    return pts


def crack(rng: np.random.Generator, length_m: float, width_mm: float, subtype: str) -> Rendered:
    arr = asphalt(rng)
    _markings(rng, arr)
    img = _finish(arr)
    draw = ImageDraw.Draw(img)
    px_len = length_m / GSD_M_PER_PX
    lw = max(2, int(round(width_mm / 1000 / GSD_M_PER_PX)))
    all_pts: list[tuple[float, float]] = []

    def stroke(pts, width):
        draw.line(pts, fill=(28, 27, 26), width=width, joint="curve")
        draw.line(pts, fill=(48, 46, 44), width=max(1, width + 2))
        draw.line(pts, fill=(22, 21, 20), width=width)
        all_pts.extend(pts)

    if subtype == "alligator":
        half = px_len / 2
        cx, cy = _place(rng, half, half * 0.7)
        for _ in range(int(rng.integers(9, 15))):
            sx, sy = cx + rng.uniform(-half, half), cy + rng.uniform(-half * 0.7, half * 0.7)
            pts = _walk(rng, sx, sy, rng.uniform(0, 2 * math.pi), int(rng.integers(6, 12)), half / 6, 0.6)
            pts = [(min(max(x, cx - half), cx + half), min(max(y, cy - half * 0.7), cy + half * 0.7)) for x, y in pts]
            stroke(pts, max(2, lw - 1))
    else:
        angle = {"longitudinal": rng.normal(0, 0.15), "transverse": math.pi / 2 + rng.normal(0, 0.15)}.get(
            subtype, rng.uniform(0, math.pi)
        )
        steps = 40
        step_len = px_len / steps
        span_x = abs(math.cos(angle)) * px_len / 2 + 40
        span_y = abs(math.sin(angle)) * px_len / 2 + 40
        cx, cy = _place(rng, min(span_x, FRAME_W / 2 - 80), min(span_y, FRAME_H / 2 - 80))
        sx, sy = cx - math.cos(angle) * px_len / 2, cy - math.sin(angle) * px_len / 2
        main = _walk(rng, sx, sy, angle, steps, step_len, 0.12)
        main = [(min(max(x, 4), FRAME_W - 4), min(max(y, 4), FRAME_H - 4)) for x, y in main]
        stroke(main, lw)
        for _ in range(int(rng.integers(1, 4))):
            bx, by = main[int(rng.integers(5, steps - 5))]
            br = _walk(rng, bx, by, angle + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1), 10, step_len * 0.6, 0.25)
            br = [(min(max(x, 4), FRAME_W - 4), min(max(y, 4), FRAME_H - 4)) for x, y in br]
            stroke(br, max(1, lw - 2))

    img = img.filter(ImageFilter.GaussianBlur(0.5))
    xs, ys = [p[0] for p in all_pts], [p[1] for p in all_pts]
    pad = lw + 3
    bbox = [max(0.0, min(xs) - pad), max(0.0, min(ys) - pad), min(FRAME_W, max(xs) + pad), min(FRAME_H, max(ys) + pad)]
    return Rendered(img, [float(round(v)) for v in bbox], "crack")


def vertical_step(rng: np.random.Generator, length_m: float) -> Rendered:
    arr = asphalt(rng)
    h, w, _ = arr.shape
    angle = rng.uniform(-0.5, 0.5)
    px_len = min(length_m / GSD_M_PER_PX, w * 0.8)
    cx, cy = w / 2 + rng.uniform(-200, 200), h / 2 + rng.uniform(-150, 150)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # signed distance from the step line, limited along its length
    nx, ny = -math.sin(angle), math.cos(angle)
    d = (xx - cx) * nx + (yy - cy) * ny
    along = (xx - cx) * math.cos(angle) + (yy - cy) * math.sin(angle)
    seg = np.abs(along) < px_len / 2
    taper = np.clip(1 - (np.abs(along) - px_len / 2 + 40) / 40, 0, 1)  # soft ends
    lit = (d > 0) & (d < 10)
    arr[lit] *= (1 + 0.22 * taper[lit])[:, None]  # raised slab edge catches light
    shadow = (d > -16) & (d <= 0)
    arr[shadow] *= (1 - 0.5 * taper[shadow])[:, None]
    corners = [
        (cx + math.cos(angle) * s * px_len / 2 + nx * o, cy + math.sin(angle) * s * px_len / 2 + ny * o)
        for s in (-1, 1)
        for o in (-30, 30)
    ]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    bbox = [max(0, min(xs)), max(0, min(ys)), min(w, max(xs)), min(h, max(ys))]
    return Rendered(_finish(arr), [float(round(v)) for v in bbox], "vertical_step")


def debris(rng: np.random.Generator, width_m: float) -> Rendered:
    arr = asphalt(rng)
    img = _finish(arr)
    draw = ImageDraw.Draw(img)
    r = width_m / GSD_M_PER_PX / 2
    cx, cy = _place(rng, r, r)
    pts = []
    for _ in range(int(rng.integers(25, 50))):
        x, y = cx + rng.normal(0, r / 2), cy + rng.normal(0, r / 2)
        s = rng.uniform(4, 16)
        c = int(rng.uniform(120, 200))
        draw.ellipse([x - s, y - s * 0.7, x + s, y + s * 0.7], fill=(c, c - 8, c - 20))
        pts.append((x - s, y - s, x + s, y + s))
    bbox = [max(0, min(p[0] for p in pts)), max(0, min(p[1] for p in pts)), min(FRAME_W, max(p[2] for p in pts)), min(FRAME_H, max(p[3] for p in pts))]
    return Rendered(img, [float(round(v)) for v in bbox], "debris")


def closeup(src: Rendered, out_w: int = 960) -> tuple[Image.Image, list[float]]:
    """Crop around the bbox (with margin) and scale; returns the crop and the bbox in crop pixels."""
    x0, y0, x1, y1 = src.bbox
    bw, bh = x1 - x0, y1 - y0
    m = max(bw, bh) * 0.45 + 40
    cx0, cy0 = max(0, x0 - m), max(0, y0 - m)
    cx1, cy1 = min(FRAME_W, x1 + m), min(FRAME_H, y1 + m)
    crop = src.image.crop((int(cx0), int(cy0), int(math.ceil(cx1)), int(math.ceil(cy1))))
    scale = out_w / crop.width
    out_h = max(1, int(round(crop.height * scale)))
    crop = crop.resize((out_w, out_h), Image.Resampling.LANCZOS)
    bb = [(x0 - int(cx0)) * scale, (y0 - int(cy0)) * scale, (x1 - int(cx0)) * scale, (y1 - int(cy0)) * scale]
    bb = [round(min(max(0, bb[0]), out_w), 1), round(min(max(0, bb[1]), out_h), 1), round(min(bb[2], out_w), 1), round(min(bb[3], out_h), 1)]
    return crop, bb


def lidar_profile_png(rng: np.random.Generator, kind: str, width_m: float, magnitude_m: float, title: str) -> bytes:
    """Cross-section chart as the GeometryAnalyzer might export it."""
    half = max(1.0, width_m * 1.6)
    x = np.linspace(-half, half, 360)
    noise = rng.normal(0, 0.0025, x.size) + 0.004 * np.sin(x * rng.uniform(2, 5))
    w2 = width_m / 2
    if kind == "pothole":
        prof = -magnitude_m * np.clip(1 - (np.abs(x) / w2) ** 4, 0, 1) ** 0.5
    elif kind == "depression":
        prof = -magnitude_m * np.exp(-(x**2) / (2 * (w2 / 1.6) ** 2))
    elif kind == "raised_area":
        prof = magnitude_m * np.exp(-(x**2) / (2 * (w2 / 1.6) ** 2))
    elif kind == "vertical_step":
        prof = np.where(x > 0, magnitude_m, 0.0) + 0.002 * np.tanh(x * 30)
    else:
        prof = np.zeros_like(x)
    z = (prof + noise) * 1000  # mm

    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=120)
    ax.plot(x, z, color="#2a6fdb", linewidth=1.6)
    ax.fill_between(x, z, z.min() - 5, color="#2a6fdb", alpha=0.08)
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    peak = z.min() if kind in ("pothole", "depression") else z.max()
    ax.annotate(
        f"{abs(peak):.0f} mm",
        xy=(x[np.argmin(z) if peak == z.min() else np.argmax(z)], peak),
        xytext=(10, -14 if peak < 0 else 8),
        textcoords="offset points",
        fontsize=9,
        color="#333",
    )
    ax.set_xlabel("Distance across defect (m)")
    ax.set_ylabel("Height vs. surface (mm)")
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(True, alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def to_jpeg(img: Image.Image, quality: int = 86) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
