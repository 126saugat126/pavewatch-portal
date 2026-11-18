# PaveWatch portal: design system (v2, approved 2026-11-17)

v2 replaces v1 (dark-first, lime accent). Approved by the user on 2026-11-17: a **light-first** look with a dark toggle, built on a warm ivory ground with sage and mint surfaces, forest-teal actions and deep slate-teal text. The polish and motion take their cue from the Haulix logistics dashboard: icon sidebar, summary chips, rounded cards, fluid transitions. We borrow its feel only, not its branding, layout or content.

The look we're after is a **technical, geospatial inspection workspace**: calm surfaces, clear hierarchy, and colour reserved for meaning (severity, geography, selection).

## 1. Colour

Tokens live in `frontend/src/styles/global.css`. MapLibre overlays mirror them in `components/map/basemap.ts`.

| Role | Light | Dark | Use |
| --- | --- | --- | --- |
| Ground | `#F7F8F4` | `#111716` | Page background |
| Tile | `#FFFFFF` | `#18201F` | Cards, with 1px hairline and a soft shadow |
| Tile 2 / mint | `#EEF2EB` | `#212B29` | Hover, row highlight |
| Sage | `#E8EDE5` | `#1D2725` | Quiet surfaces: segmented track, raised tiles |
| Ink | `#344B49` | `#E6ECE7` | Body text |
| Ink strong | `#22322F` | `#F4F7F4` | Titles, numerals |
| Ink 2 | `#5F7370` | `#9DADA8` | Secondary text (≥ 4.5:1 on tile) |
| Hairline | `#DDE4DA` | `#2B3735` | Borders, dividers |
| **Accent (forest teal)** | `#547B70` | `#8FBCAE` | Primary actions, active nav, **selection ring** |
| Accent soft (sage) | `#A8BCA5` | `#5D7A6C` | Hover bars, text selection |
| **Geo (blue)** | `#3F74A3` | `#7FB0DC` | Flight path, GPS accuracy, map-related marks |
| Highlight (terracotta) | `#D98B54` | `#E39A66` | Small highlights only (e.g. a "new" badge). Never selection |

**Gradients** are limited to primary actions, the active sidebar item and progress bars (`--pw-accent-grad`, teal 135°).

**Severity** (functional, unchanged from v1): `#d03b3b` high, `#fab219` medium, `#898781` low. They were validated for colour-blind separation and always come with an icon and a label. Terracotta sits close to the medium amber, which is why selection uses the teal ring and not terracotta.

**Detection boxes** on evidence photos use a bright mint (`#7EE3C6`) with a dark halo, so they read on asphalt in both themes.

## 2. Type

| Role | Font | Size / line / weight |
| --- | --- | --- |
| Page title | Archivo | `clamp(28px, 2.6vw, 40px)` / 1.1 / 500 / −0.02em |
| Stat numeral | Archivo | 34–40 / 1.0 / 400, tabular |
| Tile title | Archivo | 19 / 1.25 / 600 |
| Body | Archivo | 15 / 1.5 / 400 |
| Eyebrow / caps labels | Archivo (width 112) | 12 / 1 / 600 / +0.05em / UPPERCASE |
| Data: IDs, coordinates, measurements, timestamps | IBM Plex Mono | 12.5 / 1.4 / 400, tabular |

Both fonts are self-hosted (`@fontsource`), so the app needs no CDN.

## 3. Shape, depth and spacing

- **Radius:** tiles 14px, controls 10px, small badges 6px, pills full.
- **Depth:** tiles have a 1px hairline and `--pw-shadow-1`. Interactive tiles lift 3px to `--pw-shadow-2` on hover. Popovers, modals and toasts use `--pw-shadow-pop`. Dark mode relies on borders more than shadows.
- **Spacing:** gutter and tile padding are 32/28px at ≥1280px, 24/24 at 768–1279px, and 16/18 below 768px.

## 4. Shell

- **Top bar** (sticky, translucent), left to right: the PaveWatch mark (home); **Back** and **Forward** buttons; the **trail**; summary chips; theme toggle. There is no sidebar.
- **Back / Forward** step through browser history. Back falls back to "up one level" when the page was opened directly; Forward is disabled when there is nothing ahead.
- **Trail:** Companies › Surveys › Findings (› the open finding). Each step shows its level in small caps and the name of what you are in. The current step is filled with the teal gradient (it slides between steps); earlier steps are buttons. Names come from the cached queries, so the trail costs no extra requests.
- **Summary chips** for all clients (clients, surveys, findings, high severity) and a "Live" indicator. They shorten on narrow screens and disappear below 900px.
- Page titles sit in each page's opener; the opener has no breadcrumb of its own any more.

### Survey workspace

The survey page is one workspace. The map, the findings list and the open finding share a single selection stored in the URL (`/orgs/:org/runs/:run/findings/:id`; filters stay in the query string). Clicking a list row or a map marker opens the finding in place of the list; the selected marker gets a teal ring and the map only pans if the marker is off screen. Previous / next (buttons, ← →) follow the filtered, sorted list; Esc or "All findings" closes it. On stacked layouts (<1100px) the same panel sits below the map.

### Data-quality warnings

Warnings about data quality (survey notes, per-finding quality warnings, warning areas on the map) use a faint red wash (`--pw-warn-wash`, `--pw-warn-line`, `--pw-warn-ink`). It is deliberately softer than the high-severity red. A survey with no warnings keeps the quiet sage tile.

## 5. Motion

One curve and three durations everywhere (`src/lib/motion.ts`, mirrored as CSS variables):

| Token | Value | Use |
| --- | --- | --- |
| Ease | `cubic-bezier(0.22, 1, 0.36, 1)` | Everything |
| Fast | 150ms | Colour, press feedback |
| Base | 250ms | Hover lift, tooltips, popovers, toggles |
| Slow | 450ms | Entrances, page transitions, segmented indicator |
| Stagger | 50ms | Between tiles in an entrance |

- **Entrances:** tiles and list rows fade and rise 12px when they are inserted. Elements that stay mounted (e.g. rows that survive a filter change) are not re-animated.
- **Numbers** count up on first load and glide to new values after a refresh.
- **Bars** (severity mix, type bars) grow in from the left.
- **Pages** fade and rise on route change. Filter and query changes don't replay it.
- **Live data:** company and survey lists re-check the server every 60 seconds. New surveys raise an info toast, and a failed background refresh raises a warning toast while the last data stays on screen.
- **Reduced motion:** `MotionConfig reducedMotion="user"` plus a CSS media query. Movement is removed and state changes are instant.

## 6. Toasts

`src/lib/toast.tsx` is the single entry point (`toast.success/info/warning/error`, and `copyText`). Toasts appear bottom-right, at most three at a time, with an icon tinted by kind.

## 7. Next stages (approved plan)

2. ~~Survey workspace~~ built (see section 4); still to do: preserve map position across filter changes, comparison links.
3. Detection reveal in the image viewer.
4. Flight-path visualisation (route drawing; an even-paced replay labelled "not to time").
5. Analytics.
