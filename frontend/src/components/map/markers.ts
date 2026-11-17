import { Marker, Popup, type Map as MapLibreMap } from 'maplibre-gl';
import type { FindingListItem } from '../../api/types';
import { defectMeta, defectTitle, severityKey, severityMeta } from '../../lib/defects';
import { measurementSummary } from '../../lib/format';
import type { Position } from '../../lib/geo';

/** HTML marker: outer element is positioned by MapLibre, the inner dot is styled/animated. */
export function createFindingMarker(
  f: { finding_id: string; defect_type: string; severity: string | null },
  pos: Position,
  handlers?: { onEnter?: () => void; onLeave?: () => void; onClick?: () => void },
) {
  const el = document.createElement('div');
  el.className = 'pw-marker';
  const sev = severityKey(f.severity);
  const dot = document.createElement('div');
  dot.className = 'pw-marker__dot';
  dot.dataset.sev = sev;
  dot.dataset.approx = String(pos.approx);
  dot.textContent = defectMeta(f.defect_type).glyph;
  el.appendChild(dot);

  if (handlers) {
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute(
      'aria-label',
      `${f.finding_id}: ${defectMeta(f.defect_type).label}, ${severityMeta(f.severity).label} severity${pos.approx ? ', approximate location' : ''}`,
    );
    el.addEventListener('mouseenter', () => handlers.onEnter?.());
    el.addEventListener('mouseleave', () => handlers.onLeave?.());
    el.addEventListener('focus', () => handlers.onEnter?.());
    el.addEventListener('blur', () => handlers.onLeave?.());
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      handlers.onClick?.();
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handlers.onClick?.();
      }
    });
  } else {
    el.setAttribute('aria-hidden', 'true');
  }

  const marker = new Marker({ element: el, anchor: 'center' }).setLngLat([pos.lon, pos.lat]);
  return { marker, el };
}

/** Tooltip content built with textContent (never innerHTML) - data comes from the sender. */
export function findingPopupContent(f: FindingListItem, approx: boolean) {
  const root = document.createElement('div');
  const title = document.createElement('div');
  title.className = 'pw-popup__title';
  title.textContent = `${f.finding_id} · ${defectTitle(f.defect_type, f.subtype)}`;
  const meta = document.createElement('div');
  meta.className = 'pw-popup__meta';
  const parts = [`${severityMeta(f.severity).label} severity`];
  const ms = measurementSummary(f.measurements);
  if (ms) parts.push(ms);
  meta.textContent = parts.join(' · ');
  root.append(title, meta);
  if (approx) {
    const a = document.createElement('div');
    a.className = 'pw-popup__note';
    a.textContent = 'No GPS fix: approximate location';
    root.append(a);
  }
  const hint = document.createElement('div');
  hint.className = 'pw-popup__note';
  hint.textContent = 'Click to open';
  root.append(hint);
  return root;
}

export function textPopupContent(titleText: string, body?: string | null) {
  const root = document.createElement('div');
  const t = document.createElement('div');
  t.className = 'pw-popup__title';
  t.textContent = titleText;
  root.append(t);
  if (body) {
    const b = document.createElement('div');
    b.className = 'pw-popup__meta';
    b.textContent = body;
    root.append(b);
  }
  return root;
}

export function makePopup() {
  return new Popup({ closeButton: false, closeOnClick: false, offset: 18, className: 'pw-popup', maxWidth: '280px' });
}

export function addStartMarker(map: MapLibreMap, lon: number, lat: number) {
  const el = document.createElement('div');
  el.className = 'pw-start';
  el.title = 'Survey start point (local frame origin)';
  el.textContent = 'Start';
  return new Marker({ element: el, anchor: 'bottom', offset: [0, -4] }).setLngLat([lon, lat]).addTo(map);
}
