import {
  IconAlertOctagon,
  IconAlertTriangle,
  IconCircleDot,
  IconCircleDashed,
  IconCurrentLocation,
  IconGps,
  IconLayersSubtract,
  IconMapOff,
  IconWaveSine,
  IconInfoCircle,
  type Icon,
} from '@tabler/icons-react';

// ------------------------------------------------------------------ defect types
// Identity is carried by the label + a letter glyph (also drawn inside map markers),
// never by colour alone. Colour on the map encodes severity.

export const DEFECT_TYPES = ['pothole', 'crack', 'depression', 'raised_area', 'vertical_step', 'other'] as const;

const DEFECTS: Record<string, { label: string; glyph: string; hint: string }> = {
  pothole: { label: 'Pothole', glyph: 'P', hint: 'Bowl-shaped hole where surface material has broken away.' },
  crack: { label: 'Crack', glyph: 'C', hint: 'Linear or networked fracture in the surface.' },
  depression: { label: 'Depression', glyph: 'D', hint: 'Low area where the surface has settled; may pond water.' },
  raised_area: { label: 'Raised area', glyph: 'R', hint: 'Surface pushed up (heave, roots, shoving).' },
  vertical_step: { label: 'Vertical step', glyph: 'S', hint: 'Height offset between adjacent surfaces; a trip hazard.' },
  other: { label: 'Other', glyph: 'O', hint: 'Other surface issue.' },
};

export function defectMeta(type: string) {
  return DEFECTS[type] ?? { label: humanize(type), glyph: type.charAt(0).toUpperCase() || '?', hint: '' };
}

export function defectTitle(type: string, subtype?: string | null) {
  const base = defectMeta(type).label;
  if (!subtype) return base;
  return type === 'other' ? humanize(subtype) : `${base} · ${humanize(subtype).toLowerCase()}`;
}

// ------------------------------------------------------------------ severity
// Status colours (reserved, fixed): low = neutral, medium = warning, high = critical.
// Always rendered with an icon + text label. Values live as CSS tokens in global.css.

export const SEVERITIES = ['high', 'medium', 'low'] as const;
export type SeverityKey = (typeof SEVERITIES)[number] | 'none';

const SEVERITY: Record<SeverityKey, { label: string; color: string; icon: Icon; rank: number }> = {
  high: { label: 'High', color: 'var(--pw-sev-high)', icon: IconAlertOctagon, rank: 3 },
  medium: { label: 'Medium', color: 'var(--pw-sev-medium)', icon: IconAlertTriangle, rank: 2 },
  low: { label: 'Low', color: 'var(--pw-sev-low)', icon: IconCircleDot, rank: 1 },
  none: { label: 'Not rated', color: 'var(--pw-sev-none)', icon: IconCircleDashed, rank: 0 },
};

export function severityKey(s: string | null | undefined): SeverityKey {
  return s === 'high' || s === 'medium' || s === 'low' ? s : 'none';
}

export function severityMeta(s: string | null | undefined) {
  return SEVERITY[severityKey(s)];
}

// ------------------------------------------------------------------ data-quality warnings
// These let users tell "no defects found" apart from "not enough data to know".

const WARNINGS: Record<string, { label: string; explain: string; icon: Icon }> = {
  NOT_SCANNED: {
    label: 'Area not scanned',
    explain: 'This area was not covered by the survey. No findings here does not mean the pavement is fine.',
    icon: IconMapOff,
  },
  NO_LIDAR_COVERAGE: {
    label: 'No LiDAR data',
    explain: 'LiDAR returns are missing, so depths and heights could not be measured. Detection relied on images only.',
    icon: IconWaveSine,
  },
  POSE_LOW_CONFIDENCE: {
    label: 'Low position confidence',
    explain: "The drone's position estimate was weak, so locations may be off by more than usual.",
    icon: IconCurrentLocation,
  },
  SCAN_IMAGE_MISALIGNED: {
    label: 'Scan and image misaligned',
    explain: 'LiDAR and camera data were not perfectly synchronised, so measurements may be less accurate.',
    icon: IconLayersSubtract,
  },
  GPS_UNAVAILABLE: {
    label: 'No GPS fix',
    explain: "No GPS fix at detection time. The location is estimated from the drone's start point.",
    icon: IconGps,
  },
};

export function warningMeta(code: string) {
  return WARNINGS[code] ?? { label: humanize(code), explain: '', icon: IconInfoCircle };
}

// ------------------------------------------------------------------ misc labels

export const SOURCE_LABEL: Record<string, string> = {
  image: 'Camera image',
  lidar: 'LiDAR scan',
  fused: 'Camera + LiDAR (fused)',
};

const EVIDENCE_KIND: Record<string, string> = {
  image_raw: 'Raw frame',
  image_closeup: 'Close-up',
  lidar_profile: 'LiDAR profile',
  lidar_scan: '3D scan',
};

export function evidenceKindLabel(kind: string) {
  return EVIDENCE_KIND[kind] ?? humanize(kind);
}

export function humanize(s: string) {
  const t = s.replace(/[_-]+/g, ' ').trim().toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
