import type { Measurement } from '../api/types';

const dateFmt = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });
const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

export const fmtDate = (iso: string | null | undefined) => (iso ? dateFmt.format(new Date(iso)) : '—');
export const fmtDateTime = (iso: string | null | undefined) => (iso ? dateTimeFmt.format(new Date(iso)) : '—');
export const fmtTime = (iso: string | null | undefined) => (iso ? timeFmt.format(new Date(iso)) : '—');

export function fmtRelative(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return '';
  const days = Math.round((new Date(iso).getTime() - now) / 86_400_000);
  if (Math.abs(days) < 1) return 'today';
  if (Math.abs(days) < 30) return rtf.format(days, 'day');
  const months = Math.round(days / 30.4);
  if (Math.abs(months) < 12) return rtf.format(months, 'month');
  return rtf.format(Math.round(days / 365), 'year');
}

export function fmtDuration(start: string, end: string | null) {
  if (!end) return null;
  const min = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60_000);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

const UNIT: Record<string, string> = { m2: 'm²', m3: 'm³', cm2: 'cm²', deg: '°' };
export const fmtUnit = (u: string) => UNIT[u] ?? u;

const num = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 });
export function fmtMeasurement(m: Measurement) {
  return `${num.format(m.value)} ${fmtUnit(m.unit)}`;
}

export const fmtNumber = (n: number, digits = 2) =>
  new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(n);

export const fmtPercent = (p: number | null | undefined) => (p == null ? '—' : `${Math.round(p * 100)}%`);

export const fmtCoord = (lat: number, lon: number) => `${lat.toFixed(6)}, ${lon.toFixed(6)}`;

export function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const MEASURE_ORDER = ['width', 'length', 'depth', 'height', 'max_width', 'area', 'volume'];
export function sortedMeasurements(ms: Record<string, Measurement>) {
  return Object.entries(ms).sort(([a], [b]) => {
    const ia = MEASURE_ORDER.indexOf(a);
    const ib = MEASURE_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
}

/** A short "headline" measurement for list rows, e.g. "0.42 × 0.51 m · 62 mm deep". */
export function measurementSummary(ms: Record<string, Measurement>) {
  const parts: string[] = [];
  const { width, length, depth, height, max_width } = ms;
  if (width && length && width.unit === length.unit) {
    parts.push(`${num.format(width.value)} × ${num.format(length.value)} ${fmtUnit(width.unit)}`);
  } else if (length) {
    parts.push(`${fmtMeasurement(length)} long`);
  } else if (width) {
    parts.push(`${fmtMeasurement(width)} wide`);
  }
  if (depth) parts.push(`${fmtMeasurement(depth)} deep`);
  if (height) parts.push(`${fmtMeasurement(height)} high`);
  if (max_width && !width) parts.push(`up to ${fmtMeasurement(max_width)} wide`);
  return parts.join(' · ');
}
