"""Evidence images for reports: loaded from storage, with bounding boxes burned in."""

import io
import logging
from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.db import models as m
from app.reports.labels import fmt_percent
from app.reports.maps import load_font
from app.storage import Storage

log = logging.getLogger(__name__)

BOX = (126, 227, 198)  # --pw-box
BOX_HALO = (8, 20, 18)
BOX_TEXT = (17, 17, 17)


@dataclass
class ReportImage:
    data: bytes
    width: int
    height: int
    boxes: int  # number of boxes drawn


def _flatten(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


def evidence_image(storage: Storage, ev: m.Evidence, max_px: int = 1400, boxes: bool = True) -> ReportImage | None:
    """The evidence frame scaled for print, bounding boxes drawn on it. None if not an image or unreadable."""
    if not ev.thumb_key:  # only files the ingest step recognised as images get thumbnails
        return None
    key = ev.preview_key or ev.storage_key
    try:
        src = Image.open(io.BytesIO(storage.read(key)))
        src.load()
        is_png = src.format == "PNG"
        img = _flatten(src)
        # Boxes are in ORIGINAL image pixels; the preview may be smaller.
        if ev.width_px and ev.height_px:
            ow, oh = ev.width_px, ev.height_px
        elif key == ev.storage_key:
            ow, oh = img.size
        else:
            ow, oh = Image.open(io.BytesIO(storage.read(ev.storage_key))).size
    except Exception as e:
        log.warning("Evidence %s could not be read for a report: %s", ev.storage_key, e)
        return None

    img.thumbnail((max_px, max_px), Image.LANCZOS)
    w, h = img.size
    sx, sy = w / ow, h / oh

    drawn = 0
    if boxes and ev.bounding_boxes:
        d = ImageDraw.Draw(img)
        lw = max(2, round(max(w, h) * 0.005))
        fs = max(14, round(max(w, h) * 0.034))
        font = load_font(fs)
        for b in ev.bounding_boxes:
            try:
                x0, y0, x1, y1 = (float(v) for v in b["bbox"])
            except (KeyError, TypeError, ValueError):
                continue
            x0, x1, y0, y1 = x0 * sx, x1 * sx, y0 * sy, y1 * sy
            d.rectangle([x0 - lw, y0 - lw, x1 + lw, y1 + lw], outline=BOX_HALO, width=lw * 3)
            d.rectangle([x0, y0, x1, y1], outline=BOX, width=lw)
            label = str(b.get("label") or "")
            if b.get("confidence") is not None:
                label = f"{label} {fmt_percent(float(b['confidence']))}".strip()
            if label:
                tw = d.textlength(label, font=font)
                th = fs * 1.45
                ty = y0 - th if y0 - th >= 0 else y1
                d.rectangle([x0, ty, x0 + tw + fs * 0.8, ty + th], fill=BOX)
                d.text((x0 + fs * 0.4, ty + th / 2), label, fill=BOX_TEXT, font=font, anchor="lm")
            drawn += 1

    buf = io.BytesIO()
    if is_png:  # charts such as LiDAR profiles stay sharp as PNG
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=84, optimize=True)
    return ReportImage(buf.getvalue(), w, h, drawn)
