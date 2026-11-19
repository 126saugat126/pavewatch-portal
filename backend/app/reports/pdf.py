"""PDF reports built with ReportLab.

Two documents:
  * ``build_finding_report``: one finding (evidence, measurements, location, warnings).
  * ``build_run_report``: a whole survey run. Summary, overview map, breakdown,
    data quality, an index of findings (most severe first), then one detail page
    per finding using the same layout as the single-finding report.

Text uses the PDF base fonts (Helvetica), so no font files are needed.
"""

import io
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, tzinfo
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from app import __version__
from app.db import models as m
from app.reports import labels as L
from app.reports.geo import Position, finding_position, geometry_coords, osm_link, polygon_rings
from app.reports.images import ReportImage, evidence_image
from app.reports.maps import MapSpec, Marker, RenderedMap, TileSource, render_map
from app.storage import Storage

# ------------------------------------------------------------------ look

INK = HexColor("#344b49")
INK_STRONG = HexColor("#22322f")
INK_2 = HexColor("#5f7370")
ACCENT = HexColor("#547b70")
ACCENT_STRONG = HexColor("#456a60")
ACCENT_WASH = HexColor("#eef3f1")
RULE = HexColor("#d6ddd8")
ZEBRA = HexColor("#f6f8f6")
WARN = HexColor("#e0a10f")
WARN_WASH = HexColor("#fdf6e3")
HIGH = HexColor("#d03b3b")

PAGE = letter
MARGIN_X = 18 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 20 * mm


def _ps(name: str, **kw) -> ParagraphStyle:
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_BODY = _ps("body")
S_SMALL = _ps("small", fontSize=8, leading=11, textColor=INK_2)
S_SMALL_R = _ps("small_r", fontSize=8, leading=11, textColor=INK_2, alignment=TA_RIGHT)
S_EYEBROW = _ps("eyebrow", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=ACCENT)
S_TITLE = _ps("title", fontSize=26, leading=31, textColor=INK_STRONG)
S_SUBTITLE = _ps("subtitle", fontSize=12.5, leading=17, textColor=INK_2)
S_H2 = _ps("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=INK_STRONG)
S_FTITLE = _ps("ftitle", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK_STRONG)
S_KEY = _ps("key", fontSize=8.5, leading=12, textColor=INK_2)
S_VAL = _ps("val", fontSize=9.5, leading=12.5, textColor=INK)
S_CELL = _ps("cell", fontSize=8.5, leading=11)
S_CELL_DIM = _ps("cell_dim", fontSize=8, leading=10.5, textColor=INK_2)
S_HEAD = _ps("head", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK_2)
S_HEAD_C = _ps("head_c", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK_2, alignment=1)
S_NUM_C = _ps("num_c", fontSize=9, leading=12, alignment=1)
S_NUM_C_B = _ps("num_c_b", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=1, textColor=INK_STRONG)
S_KPI = _ps("kpi", fontName="Helvetica-Bold", fontSize=22, leading=25, textColor=INK_STRONG)
S_KPI_LABEL = _ps("kpi_label", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=INK)
S_MEASURE = _ps("measure", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK_STRONG)
S_BULLET = _ps("bullet", leftIndent=11, bulletIndent=0, spaceAfter=3)
S_BOX_TITLE = _ps("box_title", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK_STRONG, spaceAfter=4)

# Characters the base fonts cannot draw, replaced before encoding.
_SUBS = str.maketrans({"≈": "~", "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "–": "-", " ": " ", " ": " "})


def t(s: object) -> str:
    """Escape text for Paragraph markup and keep it drawable in Helvetica (WinAnsi)."""
    s = str(s).translate(_SUBS)
    s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s)


def _dest(s: str) -> str:
    return "f_" + re.sub(r"[^A-Za-z0-9_-]", "_", s)


# ------------------------------------------------------------------ small flowables


class Pill(Flowable):
    """Rounded label, used for severity."""

    def __init__(self, text: str, fill: str, ink: str, size: float = 7.5):
        super().__init__()
        self.text, self.fill, self.ink, self.size = t(text).replace("&amp;", "&"), fill, ink, size
        self.pad_x = size * 0.75
        self.width = stringWidth(self.text, "Helvetica-Bold", size) + 2 * self.pad_x
        self.height = size * 1.75

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(HexColor(self.fill))
        c.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=0, fill=1)
        c.setFillColor(HexColor(self.ink))
        c.setFont("Helvetica-Bold", self.size)
        c.drawCentredString(self.width / 2, (self.height - self.size * 0.72) / 2, self.text)


def severity_pill(sev: str | None, suffix: str = "") -> Pill:
    fill, ink = L.severity_colors(sev)
    return Pill(L.severity_label(sev) + suffix, fill, ink)


class Bookmark(Flowable):
    """Invisible anchor: a PDF outline entry plus a link destination."""

    def __init__(self, key: str, title: str | None = None, level: int = 0):
        super().__init__()
        self.key, self.title, self.level = key, title, level
        self.width = self.height = 0

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        if self.title:
            self.canv.addOutlineEntry(t(self.title).replace("&amp;", "&"), self.key, level=self.level)


class Legend(Flowable):
    """Map legend: symbols and labels laid out in rows."""

    def __init__(self, items: list[tuple[str, str, str]], width: float, size: float = 7.5):
        super().__init__()
        self.items, self.avail, self.size = items, width, size
        self._rows: list[list[tuple[float, tuple[str, str, str]]]] = []

    def _item_w(self, label: str) -> float:
        return 14 + stringWidth(label, "Helvetica", self.size) + 12

    def wrap(self, aw, ah):
        self._rows, row, x = [], [], 0.0
        for it in self.items:
            w = self._item_w(it[2])
            if row and x + w > self.avail:
                self._rows.append(row)
                row, x = [], 0.0
            row.append((x, it))
            x += w
        if row:
            self._rows.append(row)
        self.width, self.height = self.avail, len(self._rows) * 13
        return self.width, self.height

    def draw(self):
        c = self.canv
        for i, row in enumerate(self._rows):
            y = self.height - (i + 1) * 13 + 3.5
            for x, (kind, color, label) in row:
                cx, cy = x + 5, y + 2.6
                if kind == "dot":
                    c.setFillColor(HexColor(color))
                    c.setStrokeColor(white)
                    c.circle(cx, cy, 4, stroke=0, fill=1)
                elif kind == "ring":
                    c.setFillColor(HexColor(color))
                    c.circle(cx, cy, 3, stroke=0, fill=1)
                    c.setStrokeColor(INK_STRONG)
                    c.setDash(1.2, 1.2)
                    c.setLineWidth(0.7)
                    c.circle(cx, cy, 4.8, stroke=1, fill=0)
                    c.setDash()
                elif kind == "line":
                    c.setStrokeColor(HexColor(color))
                    c.setLineWidth(2)
                    c.line(cx - 5, cy, cx + 5, cy)
                elif kind == "area":
                    c.setFillColor(HexColor("#f6e3b4"))
                    c.setStrokeColor(HexColor(color))
                    c.setLineWidth(0.8)
                    c.rect(cx - 5, cy - 3.5, 10, 7, stroke=1, fill=1)
                c.setFillColor(INK)
                c.setFont("Helvetica", self.size)
                c.drawString(x + 14, y, t(label).replace("&amp;", "&"))


# ------------------------------------------------------------------ layout helpers


def section(title: str, key: str | None = None, outline: bool = True, need: float = 45 * mm) -> list[Flowable]:
    out: list[Flowable] = [CondPageBreak(need)] if need else []
    if key:
        out.append(Bookmark(key, title if outline else None, 0))
    out += [
        Paragraph(t(title), S_H2),
        HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=3, spaceAfter=7),
    ]
    return out


def _para(v: object, style: ParagraphStyle = S_VAL) -> Flowable:
    return v if isinstance(v, Flowable) else Paragraph(t(v), style)


def kv_table(rows: Sequence[tuple[str, object]], width: float, key_w: float = 34 * mm) -> Table:
    data = [[Paragraph(t(k), S_KEY), _para(v)] for k, v in rows]
    tbl = Table(data, colWidths=[key_w, width - key_w])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
    ]
    if len(data) > 1:
        style.append(("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE))
    tbl.setStyle(TableStyle(style))
    return tbl


def box(content: list[Flowable], width: float, bg=ACCENT_WASH, bar=ACCENT, pad: float = 9) -> Table:
    """Tinted callout with a coloured bar on the left."""
    tbl = Table([[content]], colWidths=[width])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, bar),
                ("LEFTPADDING", (0, 0), (-1, -1), pad + 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad - 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ]
        )
    )
    return tbl


def fit_image(img: ReportImage | RenderedMap, max_w: float, max_h: float) -> Image:
    scale = min(max_w / img.width, max_h / img.height)
    return Image(io.BytesIO(img.data), img.width * scale, img.height * scale)


def _plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


def _join_words(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


# ------------------------------------------------------------------ document shell


class _NumberedCanvas(rl_canvas.Canvas):
    """Adds 'Page X of Y' once the total is known."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict] = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(INK_2)
            self.drawRightString(PAGE[0] - MARGIN_X, 10 * mm, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


class _Doc(BaseDocTemplate):
    def __init__(self, buf: io.BytesIO, *, kind: str, header_right: str, footer_left: str, **kw):
        super().__init__(
            buf,
            pagesize=PAGE,
            leftMargin=MARGIN_X,
            rightMargin=MARGIN_X,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
            author="PaveWatch",
            creator=f"PaveWatch Portal {__version__}",
            **kw,
        )
        self.kind, self.header_right, self.footer_left = kind, header_right, footer_left
        frame = Frame(
            self.leftMargin, self.bottomMargin, self.width, self.height, id="body",
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=self._decorate)])

    def _decorate(self, c: rl_canvas.Canvas, _doc) -> None:
        w, h = PAGE
        c.saveState()
        y = h - 12 * mm
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN_X, y, "PaveWatch")
        x = MARGIN_X + stringWidth("PaveWatch", "Helvetica-Bold", 9) + 5
        c.setFillColor(INK_2)
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y, self.kind)
        right = t(self.header_right).replace("&amp;", "&")
        max_w = w / 2
        while stringWidth(right, "Helvetica", 8.5) > max_w and len(right) > 4:
            right = right[:-2].rstrip() + "…"
        c.drawRightString(w - MARGIN_X, y, right)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(MARGIN_X, y - 5, w - MARGIN_X, y - 5)
        c.line(MARGIN_X, 10 * mm + 9, w - MARGIN_X, 10 * mm + 9)
        c.setFont("Helvetica", 7.5)
        c.drawString(MARGIN_X, 10 * mm, t(self.footer_left).replace("&amp;", "&"))
        c.restoreState()


@dataclass
class Ctx:
    storage: Storage
    tiles: TileSource | None
    tz: tzinfo
    generated_at: datetime
    width: float = PAGE[0] - 2 * MARGIN_X


def _footer(ctx: Ctx) -> str:
    return (
        f"Generated {L.fmt_datetime(ctx.generated_at, ctx.tz)} · "
        "Measurements are automated estimates; verify on site before repairs."
    )


def _render(doc: _Doc, story: list[Flowable]) -> bytes:
    doc.build(story, canvasmaker=_NumberedCanvas)
    return doc.filename.getvalue()  # type: ignore[union-attr]


# ------------------------------------------------------------------ one finding


def _path_coords(run: m.Run) -> list[tuple[float, float]]:
    return geometry_coords(run.flight_path) if run.flight_path else []


def _unscanned(run: m.Run) -> list[list[tuple[float, float]]]:
    return [ring for w in run.data_warnings for ring in polygon_rings(w.geometry)]


def _map_note(rm: RenderedMap) -> str:
    return "Street map" if rm.basemap else "Site plan (street map could not be loaded)"


def _finding_head(ctx: Ctx, f: m.Finding, number: int | None, total: int | None) -> list[Flowable]:
    w = ctx.width
    right = t(f.finding_id) if number is None else f"#{number} of {total} &nbsp;·&nbsp; {t(f.finding_id)}"
    head = Table(
        [[Paragraph(t(L.defect_title(f.defect_type, f.subtype)), S_FTITLE), Paragraph(right, S_SMALL_R)]],
        colWidths=[w * 0.7, w * 0.3],
    )
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    pill = severity_pill(f.severity, " severity" if f.severity else "")
    meta = [f"Confidence {L.fmt_percent(f.confidence)}" if f.confidence is not None else "Confidence not given",
            f"Detected {L.fmt_datetime(f.detected_at, ctx.tz)}"]
    line = Table([[pill, Paragraph(t(" · ".join(meta)), S_SMALL)]], colWidths=[pill.width + 8, w - pill.width - 8])
    line.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    out: list[Flowable] = [head, line]
    if f.description:
        out += [Spacer(1, 7), Paragraph(t(f.description), S_BODY)]
    return out


def _facts(ctx: Ctx, f: m.Finding, pos: Position | None) -> list[tuple[str, object]]:
    facts: list[tuple[str, object]] = [
        ("Severity", L.severity_label(f.severity)),
        ("Confidence", L.fmt_percent(f.confidence)),
        ("Detected by", L.SOURCE_LABEL.get(f.detection_source or "", L.humanize(f.detection_source or "")) or "—"),
        ("Detected at", L.fmt_datetime(f.detected_at, ctx.tz)),
    ]
    if pos:
        facts.append(("Approx. coordinates" if pos.approx else "Coordinates", L.fmt_coord(pos.lat, pos.lon)))
    else:
        facts.append(("Coordinates", "Not available"))
    if f.gps_accuracy_m is not None:
        facts.append(("GPS accuracy", f"± {L.fmt_num(f.gps_accuracy_m, 1)} m"))
    if f.local_x_m is not None and f.local_y_m is not None:
        facts.append(("From start point", f"{L.fmt_num(f.local_x_m, 1)} m forward, {L.fmt_num(f.local_y_m, 1)} m right"))
    if f.alt_m is not None:
        facts.append(("Altitude", f"{L.fmt_num(f.alt_m, 1)} m"))
    return facts


def _measurements(f: m.Finding, width: float) -> Table:
    ms = L.sorted_measurements(f.measurements or {})
    inner_w = width - 22
    content: list[Flowable] = [Paragraph("Measurements", S_BOX_TITLE)]
    if ms:
        content.append(kv_table([(L.humanize(k), Paragraph(t(L.fmt_measurement(v)), S_MEASURE)) for k, v in ms],
                                inner_w, key_w=min(28 * mm, inner_w * 0.42)))
        content += [Spacer(1, 4), Paragraph("Estimated by the processing pipeline; verify on site before repair "
                                            "planning.", S_SMALL)]
    else:
        content.append(Paragraph("No measurements were provided for this finding.", S_SMALL))
    return box(content, width, pad=10)


def _quality(f: m.Finding, width: float) -> Table:
    ws = f.quality_warnings or []
    if not ws:
        return box([Paragraph("Quality warnings", S_BOX_TITLE),
                    Paragraph("No quality warnings were reported for this finding.", S_SMALL)], width, pad=9)
    items: list[Flowable] = [Paragraph("Quality warnings", S_BOX_TITLE)]
    for wq in ws:
        code = str(wq.get("code", ""))
        text = f"<b>{t(L.warning_label(code))}</b>"
        if wq.get("message"):
            text += f" - {t(wq['message'])}"
        items.append(Paragraph(text, S_CELL))
        if L.warning_explain(code):
            items.append(Paragraph(t(L.warning_explain(code)), S_SMALL))
        items.append(Spacer(1, 4))
    return box(items[:-1], width, bg=WARN_WASH, bar=WARN, pad=9)


def _location(ctx: Ctx, run: m.Run, f: m.Finding, pos: Position | None, marker_label: str,
              width: float) -> list[Flowable]:
    out: list[Flowable] = [Paragraph("Location", S_BOX_TITLE)]
    if pos is None:
        return out + [Paragraph("No location is available for this finding.", S_SMALL)]
    fill, ink = L.severity_colors(f.severity)
    spec = MapSpec(
        width=1000, height=540, center=(pos.lon, pos.lat), zoom=19.4, marker_radius=26, ui_scale=1.8,
        markers=[Marker(pos.lon, pos.lat, fill, ink, marker_label, pos.approx, f.gps_accuracy_m)],
        path=_path_coords(run), unscanned=_unscanned(run),
    )
    rm = render_map(spec, ctx.tiles)
    notes = [_map_note(rm), "blue line: flight path"]
    if pos.approx:
        notes.insert(0, "Approximate position (no GPS fix; estimated from the drone's start point)")
    if rm.accuracy_drawn and f.gps_accuracy_m:
        notes.append(f"dashed circle: GPS accuracy ± {L.fmt_num(f.gps_accuracy_m, 1)} m")
    link = osm_link(pos.lat, pos.lon)
    out += [fit_image(rm, width, 70 * mm), Spacer(1, 3), Paragraph(
        f"{t(' · '.join(notes))}. "
        f'<a href="{escape(link)}" color="#456a60"><u>Open in OpenStreetMap</u></a>', S_SMALL)]
    return out


def _details_grid(ctx: Ctx, run: m.Run, f: m.Finding, pos: Position | None, marker_label: str) -> Table:
    """Facts and the location map on the left; measurements and quality warnings on the right."""
    w = ctx.width
    gap = 7 * mm
    left_w = w * 0.53 - gap / 2
    right_w = w - left_w - gap
    left = [kv_table(_facts(ctx, f, pos), left_w, key_w=30 * mm), Spacer(1, 10),
            *_location(ctx, run, f, pos, marker_label, left_w)]
    right = [_measurements(f, right_w), Spacer(1, 10), _quality(f, right_w)]
    tbl = Table([[left, "", right]], colWidths=[left_w, gap, right_w])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return tbl


def _evidence(ctx: Ctx, f: m.Finding) -> list[Flowable]:
    """Images in rows of up to three, bounding boxes drawn in."""
    w = ctx.width
    gap = 5 * mm
    pics: list[tuple[m.Evidence, ReportImage]] = []
    others: list[m.Evidence] = []
    for ev in f.evidence:
        ri = evidence_image(ctx.storage, ev)
        (pics.append((ev, ri)) if ri else others.append(ev))

    def cell(ev: m.Evidence, ri: ReportImage, max_w: float, max_h: float) -> list[Flowable]:
        parts = [f"<b>{t(L.evidence_kind_label(ev.kind))}</b>"]
        if ev.caption:
            parts.append(t(ev.caption))
        if ri.boxes:
            parts.append(_plural(ri.boxes, "detection box", "detection boxes") + " marked")
        img = fit_image(ri, max_w, max_h)
        img.hAlign = "LEFT"
        return [img, Spacer(1, 3), Paragraph(" · ".join(parts), S_SMALL)]

    out: list[Flowable] = []
    if not pics:
        out.append(Paragraph("This finding has no images.", S_SMALL))
    cols = min(len(pics), 3)
    max_h = {1: 72 * mm, 2: 52 * mm}.get(cols, 40 * mm)
    for start in range(0, len(pics), max(cols, 1)):
        row = pics[start : start + cols]
        col_w = (w - gap * (cols - 1)) / cols
        cells: list[object] = []
        widths: list[float] = []
        for i, (ev, ri) in enumerate(row):
            if i:
                cells.append("")
                widths.append(gap)
            cells.append(cell(ev, ri, col_w, max_h))
            widths.append(col_w)
        while len(widths) < cols * 2 - 1:  # keep columns aligned on a short last row
            cells += ["", ""]
            widths += [gap, col_w]
        tbl = Table([cells], colWidths=widths)
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        out.append(tbl)
    if others:
        files = "; ".join(f"{t(ev.file_name)} ({t(L.evidence_kind_label(ev.kind))}, {L.fmt_bytes(ev.size_bytes)})"
                          for ev in others)
        out += [Spacer(1, 2), Paragraph(f"<b>Other files</b> (download them from the portal): {files}", S_SMALL)]
    return out


def finding_section(ctx: Ctx, run: m.Run, f: m.Finding, *, number: int | None = None, total: int | None = None,
                    outline_level: int = 0) -> list[Flowable]:
    pos = finding_position(f, run.local_frame_origin)
    title = f"{f.finding_id} · {L.defect_title(f.defect_type, f.subtype)}"
    if number is not None:
        title = f"#{number}  {title}"
    marker = str(number) if number is not None else L.defect_glyph(f.defect_type)
    story: list[Flowable] = [Bookmark(_dest(f.finding_id), title, outline_level)]
    story += _finding_head(ctx, f, number, total)
    story += [Spacer(1, 12), _details_grid(ctx, run, f, pos, marker), Spacer(1, 12)]
    evidence = _evidence(ctx, f)
    story += [KeepTogether(section("Evidence", need=0) + evidence[:1]), *evidence[1:]]
    return story


def build_finding_report(*, storage: Storage, tiles: TileSource | None, tz: tzinfo, generated_at: datetime,
                         org: m.Organization, run: m.Run, finding: m.Finding, position: int, total: int) -> bytes:
    ctx = Ctx(storage, tiles, tz, generated_at)
    buf = io.BytesIO()
    doc = _Doc(
        buf, kind="Finding report", header_right=f"{org.name} · {run.site_name} · {run.run_id}",
        footer_left=_footer(ctx), title=f"Finding {finding.finding_id} - {run.site_name}",
        subject=f"PaveWatch finding report for {finding.finding_id} in survey {run.run_id}",
    )
    w = ctx.width
    context = [
        ("Company", org.name),
        ("Site", run.site_name),
        ("Survey date", L.fmt_date(run.started_at, tz)),
        ("Run ID", run.run_id),
        ("Finding", f"{position} of {total}"),
    ]
    shares = [0.29, 0.24, 0.15, 0.22, 0.10]
    strip = Table([[Paragraph(t(k).upper(), S_HEAD) for k, _ in context],
                   [Paragraph(t(v), S_CELL) for _, v in context]],
                  colWidths=[w * sh for sh in shares])
    strip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_WASH), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                               ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                               ("TOPPADDING", (0, 1), (-1, 1), 1), ("BOTTOMPADDING", (0, 0), (-1, 0), 0)]))
    story: list[Flowable] = [Paragraph("FINDING REPORT", S_EYEBROW), Spacer(1, 5), strip, Spacer(1, 14)]
    story += finding_section(ctx, run, finding)
    return _render(doc, story)


# ------------------------------------------------------------------ whole survey


def _sorted_findings(findings: Sequence[m.Finding]) -> list[m.Finding]:
    return sorted(findings, key=lambda f: (-L.severity_rank(f.severity), f.finding_id))


def _takeaways(run: m.Run, findings: list[m.Finding], numbers: dict[str, int]) -> list[str]:
    out: list[str] = []
    n = len(findings)
    if n == 0:
        out.append("No defects were detected in this survey.")
    else:
        types = Counter(f.defect_type for f in findings)
        order = [d for d in L.DEFECT_TYPES if d in types] + sorted(d for d in types if d not in L.DEFECT_TYPES)
        out.append(f"<b>{_plural(n, 'defect')} found</b>: {_join_words([L.defect_plural(d, types[d]) for d in order])}.")
        high = [f for f in findings if f.severity == "high"]
        if high:
            shown = []
            for f in high[:5]:
                size = L.measurement_summary(f.measurements or {})
                shown.append(f"#{numbers[f.finding_id]} {t(f.finding_id)} ({t(L.defect_label(f.defect_type).lower())}"
                             f"{', ' + t(size) if size else ''})")
            more = f" and {len(high) - 5} more" if len(high) > 5 else ""
            out.append(f"<b>{_plural(len(high), 'finding')} rated high severity</b>; inspect "
                       f"{'it' if len(high) == 1 else 'these'} first: {'; '.join(shown)}{more}.")
        else:
            med = sum(1 for f in findings if f.severity == "medium")
            out.append("None rated high severity." + (f" {_plural(med, 'finding')} rated medium." if med else ""))
        warned = sum(1 for f in findings if f.quality_warnings)
        if warned:
            out.append(f"{_plural(warned, 'finding')} {'carries' if warned == 1 else 'carry'} quality warnings "
                       "(for example no GPS fix or missing LiDAR data). Treat their positions or measurements with "
                       "extra care.")
    if run.status == "incomplete":
        out.append("<b>The flight did not cover the whole planned area.</b> Findings are reported for the scanned "
                   "part only.")
    if run.data_warnings:
        labels = _join_words(sorted({L.warning_label(w.code) for w in run.data_warnings}))
        out.append(f"{_plural(len(run.data_warnings), 'survey data note')} recorded ({t(labels)}). "
                   "Areas that were not scanned, or scanned with poor data, can still contain defects.")
    return out


def _cover(ctx: Ctx, org: m.Organization, run: m.Run, findings: list[m.Finding], numbers: dict[str, int]) -> list[Flowable]:
    w, tz = ctx.width, ctx.tz
    duration = L.fmt_duration(run.started_at, run.ended_at)
    flight = L.fmt_time(run.started_at, tz, with_zone=run.ended_at is None)
    if run.ended_at:
        flight += f" - {L.fmt_time(run.ended_at, tz)}"
    if duration:
        flight += f" ({duration})"
    status = "Complete" if run.status == "complete" else ("Incomplete" if run.status == "incomplete"
                                                          else L.humanize(run.status))
    pairs = [
        ("Run ID", run.run_id), ("Survey date", L.fmt_date(run.started_at, tz)),
        ("Flight time", flight), ("Status", status),
        ("Aircraft", run.aircraft_id or "—"), ("Operator", run.operator or "—"),
        ("Processing software", run.software_version), ("Uploaded", L.fmt_datetime(run.ingested_at, tz)),
    ]
    kw, vw = 30 * mm, w / 2 - 30 * mm
    rows = [[Paragraph(t(pairs[i][0]), S_KEY), Paragraph(t(pairs[i][1]), S_VAL),
             Paragraph(t(pairs[i + 1][0]), S_KEY), Paragraph(t(pairs[i + 1][1]), S_VAL)] for i in range(0, len(pairs), 2)]
    meta = Table(rows, colWidths=[kw, vw, kw, vw])
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE)]))

    n = len(findings)
    high = sum(1 for f in findings if f.severity == "high")
    warned = sum(1 for f in findings if f.quality_warnings)
    types = len({f.defect_type for f in findings})
    kpis = [
        (str(n), "Findings", _plural(types, "defect type"), ACCENT),
        (str(high), "High severity", f"{round(high / n * 100)}% of findings" if n else "—", HIGH),
        (str(warned), "Findings with warnings", "position or data quality", WARN),
        (str(len(run.data_warnings)), "Survey data notes", "e.g. areas not scanned", INK_2),
    ]
    gap = 4 * mm
    cw = (w - 3 * gap) / 4
    tiles = []
    for value, label, hint, bar in kpis:
        tile = Table([[Paragraph(t(value), S_KPI)], [Paragraph(t(label), S_KPI_LABEL)], [Paragraph(t(hint), S_SMALL)]],
                     colWidths=[cw])
        tile.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_WASH), ("LINEABOVE", (0, 0), (-1, 0), 2.5, bar),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                  ("TOPPADDING", (0, 0), (-1, 0), 9), ("TOPPADDING", (0, 1), (-1, -1), 1),
                                  ("BOTTOMPADDING", (0, 0), (-1, -2), 0), ("BOTTOMPADDING", (0, -1), (-1, -1), 9)]))
        tiles.append(tile)
    row: list[object] = []
    widths: list[float] = []
    for i, tile in enumerate(tiles):
        row.append(tile)
        widths.append(cw)
        if i < len(tiles) - 1:
            row.append("")
            widths.append(gap)
    kpi_row = Table([row], colWidths=widths)
    kpi_row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP")]))

    story: list[Flowable] = [
        Bookmark("summary", "Summary", 0),
        Paragraph("SURVEY REPORT", S_EYEBROW), Spacer(1, 6),
        Paragraph(t(run.site_name), S_TITLE), Paragraph(t(org.name), S_SUBTITLE), Spacer(1, 14),
        meta, Spacer(1, 14),
    ]
    if run.status == "incomplete":
        story += [box([Paragraph("<b>Incomplete survey.</b> This flight did not cover the whole planned area. Findings "
                                 "are reported for the scanned part only; unscanned areas are outlined on the overview "
                                 "map and listed under Survey data quality.", S_BODY)], w, bg=WARN_WASH, bar=WARN),
                  Spacer(1, 12)]
    story += [kpi_row, Spacer(1, 14)]
    bullets = [Paragraph(b, S_BULLET, bulletText="•") for b in _takeaways(run, findings, numbers)]
    story.append(box([Paragraph("Key points", S_BOX_TITLE), *bullets], w))
    story += [Spacer(1, 12), Paragraph(
        "<b>In this report:</b> overview map · breakdown by type and severity · survey data quality · findings index "
        "(most severe first) · one detail page per finding with evidence, measurements and location. Finding numbers "
        "(#1, #2 ...) match the map markers; finding IDs in the index link to their pages.", S_SMALL)]
    return story


def _overview_map(ctx: Ctx, run: m.Run, findings: list[m.Finding], numbers: dict[str, int]) -> list[Flowable]:
    w = ctx.width
    markers: list[Marker] = []
    any_approx = False
    # Low severity first so high-severity markers are drawn on top.
    for f in sorted(findings, key=lambda f: (L.severity_rank(f.severity), f.finding_id), reverse=False):
        pos = finding_position(f, run.local_frame_origin)
        if pos is None:
            continue
        any_approx |= pos.approx
        fill, ink = L.severity_colors(f.severity)
        markers.append(Marker(pos.lon, pos.lat, fill, ink, str(numbers[f.finding_id]), pos.approx))
    unscanned = _unscanned(run)
    path = _path_coords(run)
    if not markers and not path and not unscanned:
        return [Paragraph("No positions were reported for this survey, so no map can be drawn.", S_SMALL)]
    spec = MapSpec(width=1400, height=880, markers=markers, path=path, unscanned=unscanned,
                   marker_radius=17, max_fit_zoom=20.5)
    rm = render_map(spec, ctx.tiles)
    items: list[tuple[str, str, str]] = []
    present = {L.severity_key(f.severity) for f in findings}
    for sev in ["high", "medium", "low", "none"]:
        if sev in present:
            items.append(("dot", L.severity_colors(sev)[0], L.severity_label(sev)))
    if path:
        items.append(("line", "#2f6fdf", "Flight path"))
    if unscanned:
        items.append(("area", "#b07800", "Area not scanned"))
    if any_approx:
        items.append(("ring", "#c3c2b7", "Dashed ring: approximate position (no GPS)"))
    unplaced = len(findings) - len(markers)
    note = _map_note(rm) + ". Numbers match the findings index."
    if unplaced:
        note += f" {_plural(unplaced, 'finding')} without any position {'is' if unplaced == 1 else 'are'} not shown."
    return [KeepTogether([fit_image(rm, w, 118 * mm), Spacer(1, 5), Legend(items, w), Spacer(1, 2),
                          Paragraph(t(note), S_SMALL)])]


def _breakdown(findings: list[m.Finding], width: float) -> list[Flowable]:
    if not findings:
        return [Paragraph("No defects were detected, so there is nothing to break down.", S_SMALL)]
    cols = ["high", "medium", "low", "none"]
    counts: Counter[tuple[str, str]] = Counter((f.defect_type, L.severity_key(f.severity)) for f in findings)
    types = [d for d in L.DEFECT_TYPES if any(k[0] == d for k in counts)]
    types += sorted({k[0] for k in counts} - set(types))
    used_cols = [c for c in cols if any(k[1] == c for k in counts)]

    def num(v: int, bold: bool = False) -> Paragraph:
        if v == 0:
            return Paragraph('<font color="#a7b2ae">-</font>', S_NUM_C)
        return Paragraph(str(v), S_NUM_C_B if bold else S_NUM_C)

    head = [Paragraph("DEFECT TYPE", S_HEAD)] + [Paragraph(t(L.severity_label(c).upper()), S_HEAD_C) for c in used_cols]
    head.append(Paragraph("TOTAL", S_HEAD_C))
    data: list[list[Flowable]] = [head]
    for d in types:
        row_total = sum(counts[(d, c)] for c in cols)
        data.append([Paragraph(t(L.defect_label(d)), S_CELL)] + [num(counts[(d, c)]) for c in used_cols] + [num(row_total, True)])
    data.append([Paragraph("<b>All types</b>", S_CELL)] + [num(sum(counts[(d, c)] for d in types), True) for c in used_cols]
                + [num(len(findings), True)])
    first = 50 * mm
    cw = (width - first) / (len(used_cols) + 1)
    tbl = Table(data, colWidths=[first] + [cw] * (len(used_cols) + 1), repeatRows=1)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_WASH),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK_2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [white, ZEBRA]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]
    # Colour key above the severity columns
    for i, c in enumerate(used_cols, start=1):
        style.append(("LINEABOVE", (i, 0), (i, 0), 2.5, HexColor(L.severity_colors(c)[0])))
    tbl.setStyle(TableStyle(style))
    return [tbl]


def _data_quality(run: m.Run, findings: list[m.Finding], width: float) -> list[Flowable]:
    out: list[Flowable] = []
    if not run.data_warnings:
        out.append(box([Paragraph("No survey-level data problems were reported.", S_BODY)], width, pad=8))
    else:
        items: list[Flowable] = []
        for dw in run.data_warnings:
            text = f"<b>{t(L.warning_label(dw.code))}</b>"
            if dw.message:
                text += f" - {t(dw.message)}"
            items.append(Paragraph(text, S_BODY))
            if L.warning_explain(dw.code):
                items.append(Paragraph(t(L.warning_explain(dw.code)), S_SMALL))
            items.append(Spacer(1, 5))
        out.append(box(items[:-1], width, bg=WARN_WASH, bar=WARN))
    warned = sum(1 for f in findings if f.quality_warnings)
    if warned:
        out += [Spacer(1, 6), Paragraph(
            f"In addition, {_plural(warned, 'finding')} {'has its' if warned == 1 else 'have their'} own quality warnings. "
            "They are listed in the index and explained on each finding's page.", S_SMALL)]
    return out


def _index(ctx: Ctx, run: m.Run, findings: list[m.Finding], numbers: dict[str, int]) -> list[Flowable]:
    w = ctx.width
    if not findings:
        return [Paragraph("No defects were detected in this survey.", S_SMALL)]
    head = [Paragraph(h, S_HEAD) for h in ("#", "FINDING", "TYPE", "SEVERITY", "SIZE", "LOCATION", "WARNINGS")]
    data: list[list[object]] = [head]
    for f in findings:
        pos = finding_position(f, run.local_frame_origin)
        if pos:
            loc = t(L.fmt_coord(pos.lat, pos.lon))
            if pos.approx:
                loc += '<br/><font color="#5f7370">approx. (no GPS)</font>'
        else:
            loc = '<font color="#5f7370">not available</font>'
        warns = [L.warning_label(str(wq.get("code", ""))) for wq in (f.quality_warnings or [])]
        data.append([
            Paragraph(str(numbers[f.finding_id]), S_CELL),
            Paragraph(f'<a href="#{_dest(f.finding_id)}" color="#456a60"><u>{t(f.finding_id)}</u></a>', S_CELL),
            Paragraph(t(L.defect_title(f.defect_type, f.subtype)), S_CELL),
            severity_pill(f.severity),
            Paragraph(t(L.measurement_summary(f.measurements or {}) or "—"), S_CELL),
            Paragraph(loc, S_CELL_DIM),
            Paragraph(t(", ".join(warns)) if warns else '<font color="#a7b2ae">none</font>', S_CELL_DIM),
        ])
    fixed = [9 * mm, 19 * mm, 31 * mm, 19 * mm, 0, 33 * mm, 27 * mm]
    fixed[4] = w - sum(fixed)
    tbl = Table(data, colWidths=fixed, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_WASH),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ZEBRA]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    return [tbl]


def build_run_report(*, storage: Storage, tiles: TileSource | None, tz: tzinfo, generated_at: datetime,
                     org: m.Organization, run: m.Run) -> bytes:
    ctx = Ctx(storage, tiles, tz, generated_at)
    buf = io.BytesIO()
    doc = _Doc(
        buf, kind="Survey report", header_right=f"{org.name} · {run.site_name} · {run.run_id}",
        footer_left=_footer(ctx), title=f"Survey report - {run.site_name} ({L.fmt_date(run.started_at, tz)})",
        subject=f"PaveWatch survey report for run {run.run_id}",
    )
    w = ctx.width
    findings = _sorted_findings(run.findings)
    numbers = {f.finding_id: i + 1 for i, f in enumerate(findings)}

    story: list[Flowable] = _cover(ctx, org, run, findings, numbers)
    story += [PageBreak()]
    story += section("Overview map", "map", need=150 * mm) + _overview_map(ctx, run, findings, numbers) + [Spacer(1, 14)]
    story += section("Breakdown by type and severity", "breakdown", need=50 * mm) + _breakdown(findings, w)
    story += [Spacer(1, 14)]
    story += section("Survey data quality", "quality", need=40 * mm) + _data_quality(run, findings, w)
    story += [PageBreak()]
    story += section("Findings index", "index") + [Paragraph(
        "Most severe first. Click a finding ID to jump to its page.", S_SMALL), Spacer(1, 6)]
    story += _index(ctx, run, findings, numbers)
    for i, f in enumerate(findings):
        story += [PageBreak()]
        if i == 0:
            story += [Bookmark("details", "Finding details", 0)]
        story += [Paragraph('<a href="#index" color="#5f7370">Back to findings index</a>', S_SMALL_R),
                  Spacer(1, 2)]
        story += finding_section(ctx, run, f, number=numbers[f.finding_id], total=len(findings), outline_level=1)
    return _render(doc, story)
