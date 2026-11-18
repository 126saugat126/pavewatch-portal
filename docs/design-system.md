# PaveWatch portal: design system (v1, approved 2026-11-17)

Approved by the user on 2026-11-17: dark-first with the light toggle kept, lime accent, and evidence photos as tile backgrounds on the Companies and Runs pages.

Reference: Squarespace AI-builder page. We borrow its **layout rhythm, border treatment and type scale**. We do not borrow its imagery, copy or branding. The look we're after is a **dark field-survey ledger**: warm charcoal tiles that hold survey evidence, with oversized light numerals and monospaced data.

## 1. What we take from the reference

| Reference trait | Observed | PaveWatch adaptation |
| --- | --- | --- |
| Page ground | Near-black page, warm stone/taupe tiles | Charcoal ground, two warmer tile steps |
| Separation | Tonal steps, **no borders, no shadows** | Same. 1px hairlines only on inputs, table rows and the map frame |
| Corners | ~8px tiles, square white CTAs | **4px** tiles, **0px** buttons/inputs |
| Display type | Big, light-weight grotesk, tight tracking (~56px/1.0) | Archivo 300, −0.025em, used for page titles and stat numerals |
| Tile titles | ~24px medium, white, top-left, with a 2-line muted blurb | Same placement for every tile |
| Nav | Small UPPERCASE labels; pill segmented sub-nav | UPPERCASE top bar; pill segmented control for Map/List, sort and view toggles |
| Rhythm | 40px outer gutter, 40px tile gap, 40px tile padding | Same on desktop; 24 / 16 on smaller screens |
| Columns | Two columns of **unequal height**, right column starts offset | 12-col grid, 7/5 and 5/7 splits that alternate by section, staggered starts |
| Primary CTA | Solid white rectangle, dark caps label | Same ("Open finding", "Export PDF") |

## 2. Colour (2 base + 1 accent)

| Token | Hex | Role |
| --- | --- | --- |
| `--pw-ink-900` (base 1) | `#1A1918` | Page ground |
| `--pw-ink-800` | `#262422` | Tile surface (step 1) |
| `--pw-ink-700` | `#38342F` | Raised tile / hover (step 2, warm taupe) |
| `--pw-paper` (base 2) | `#EEEAE3` | Primary text on dark; CTA fill; input fill |
| `--pw-paper-dim` | `#A39E95` | Secondary text (≥ 4.5:1 on 800) |
| `--pw-hairline` | `#3F3B36` | 1px rules, table dividers |
| `--pw-accent` | `#C6F432` | **Machine annotation**: bounding boxes, flight path, selected marker, focus ring, active nav |

Tile steps are tints of base 1, so they don't add a colour. The accent stands for **what the system drew** (detections, path, selection). It is never used for decoration or large fills.

**Exception (functional, not brand):** the severity colours stay exactly as they are (`#d03b3b` high, `#fab219` medium, `#898781` low). They were validated for colour-blind separation and always come with an icon and a label. Lime sits clear of red and amber, so the accent can't be confused with a severity.

**Light mode** keeps the existing toggle: paper `#F4F0EA` ground, white tiles, ink `#111111` text. On paper, lime is too pale to read as text, so the accent becomes `#4F6B00` for text and lines, and lime remains only as a fill under dark text.

## 3. Type

| Role | Font | Size / line / weight / tracking |
| --- | --- | --- |
| Display (page title, hero stat) | **Archivo** | `clamp(40px, 4.2vw, 64px)` / 1.0 / 300 / −0.025em |
| Stat numeral (tiles) | Archivo | 48 / 1.0 / 300 / −0.02em, tabular |
| H2 tile title | Archivo | 24 / 1.2 / 600 / −0.01em |
| H3 / list primary | Archivo | 17 / 1.35 / 500 |
| Body | Archivo | 15 / 1.5 / 400 |
| Nav / eyebrow labels | Archivo (width 112, semi-expanded) | 13 / 1 / 600 / +0.04em / UPPERCASE |
| Data: IDs, coords, measurements, timestamps | **IBM Plex Mono** | 13 / 1.4 / 450, tabular |

Scale steps: 12 · 13 · 15 · 17 · 24 · 32 · 48 · 64.

Archivo is a variable grotesk (weights 100–900, widths 62–125), so one family covers both the light display face and the expanded caps. Plex Mono gives the run IDs (`PW-20261114-1502-A1`), finding IDs and `0.85 × 0.83 m · 0.027 m deep` a ledger feel. Fonts are self-hosted through `@fontsource-variable/archivo` and `@fontsource/ibm-plex-mono`, so the local app needs no CDN.

## 4. Grid and layout behaviour

- **Grid:** 12 columns, max width 1840px. Gutter and gap are 40px at ≥1280px, 24px at 768–1279px, and 16px below 768px. On phones it collapses to one column with no horizontal scroll.
- **Header:** 72px, `ink-900`, wordmark on the left, UPPERCASE nav, and a theme toggle as a square icon button. A sticky pill segmented sub-nav sits under the page title where views switch.
- **Section opener ("Meet…" pattern):** display title in cols 1–6, and a short factual paragraph plus key counts in cols 8–12, aligned to the title's baseline.
- **Tiles:** 40px padding. Title and blurb sit top-left, and content anchors to the bottom of the tile. Survey imagery (real evidence frames) can bleed full-tile behind a dark scrim. No borders.

Per screen:

| Screen | Structure |
| --- | --- |
| Companies | Opener ("Survey clients" + totals). Below it, a 2-column staggered tile list: the left column starts flush, the right column starts 80px lower. Each tile shows company name, sites, run count, last survey date (mono) and open high-severity count |
| Runs | Opener with company name. A 7/5 split: on the left, a tall tile for the latest run (evidence frame, status, stat numerals); on the right, a dense run ledger (date, site, run ID, findings, warnings) with hairline rows |
| Run detail | Incomplete/data-warning banner as a full-width `ink-700` tile, not yellow. A stat strip of 4 tiles with 48px light numerals. Then a 7/5 split: map tile left (sticky), findings ledger right. Filters sit in the pill segmented bar above |
| Finding detail | A 7/5 split flipped to 5/7 on alternate sections. Image viewer is a large tile with accent bounding boxes; the spec sheet is a mono key/value list, then location mini-map and quality warnings |

## 5. Components (deltas from today)

- **Buttons:** 0 radius. Primary is paper fill with ink caps; secondary is a 1px paper outline. Height 44.
- **Inputs:** 0 radius, paper fill, ink text, 17px. This matches the reference's white search field.
- **Segmented control:** pill shape (the one place we allow full rounding), `ink-700` track, `ink-800` active thumb, caps label.
- **Badges:** square 2px radius, mono 12px. Severity badges keep icon, label and colour.
- **Map:** a dark basemap style in dark mode. Markers keep the severity colours and letter glyphs; the selected marker gets an accent ring, and the flight path turns accent.
- **Motion:** 120ms colour and opacity only. No lift or translate on hover; hover raises the tile one tonal step (800 → 700).
- **Removed:** drop shadows, `md` rounded cards, blue primary, system-ui font.

## 6. Open points for approval

1. Dark-first with the light toggle kept, or dark only?
2. Accent `#C6F432` lime as the "machine annotation" colour. Alternative: a road-marking white-only scheme with no hue accent.
3. Should Companies and Runs tiles use real evidence frames as tile backgrounds? This needs one representative image per run from the API.
