import type { FindingListItem, GeoJSONGeometry, LocalFrameOrigin } from '../api/types';

const M_PER_DEG_LAT = 111_320;

/**
 * Local survey frame -> lon/lat. x points along heading_deg (0 = north, clockwise),
 * y points 90 degrees clockwise from x (forward-right, as in PX4). Metres.
 * Accurate to centimetres over a few hundred metres, which is all a survey site needs.
 */
export function localToLonLat(origin: LocalFrameOrigin, x: number, y: number): [number, number] {
  const h = ((origin.heading_deg ?? 0) * Math.PI) / 180;
  const east = x * Math.sin(h) + y * Math.cos(h);
  const north = x * Math.cos(h) - y * Math.sin(h);
  const lat = origin.lat + north / M_PER_DEG_LAT;
  const lon = origin.lon + east / (M_PER_DEG_LAT * Math.cos((origin.lat * Math.PI) / 180));
  return [lon, lat];
}

export interface Position {
  lon: number;
  lat: number;
  /** true when derived from the local frame because there was no GPS fix */
  approx: boolean;
}

export function findingPosition(
  f: Pick<FindingListItem, 'lat' | 'lon' | 'local_x_m' | 'local_y_m'>,
  origin: LocalFrameOrigin | null | undefined,
): Position | null {
  if (f.lat != null && f.lon != null) return { lon: f.lon, lat: f.lat, approx: false };
  if (origin && f.local_x_m != null && f.local_y_m != null) {
    const [lon, lat] = localToLonLat(origin, f.local_x_m, f.local_y_m);
    return { lon, lat, approx: true };
  }
  return null;
}

export function circlePolygon(lon: number, lat: number, radiusM: number, steps = 64) {
  const ring: [number, number][] = [];
  const dLat = radiusM / M_PER_DEG_LAT;
  const dLon = radiusM / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: 'Polygon' as const, coordinates: [ring] };
}

/** All [lon, lat] pairs in a GeoJSON geometry (any type). */
export function geometryCoords(g: GeoJSONGeometry | null | undefined): [number, number][] {
  const out: [number, number][] = [];
  const walk = (c: unknown) => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === 'number' && typeof c[1] === 'number') out.push([c[0], c[1]]);
    else c.forEach(walk);
  };
  walk(g?.coordinates);
  return out;
}

export function boundsOf(coords: [number, number][]): [[number, number], [number, number]] | null {
  if (!coords.length) return null;
  let [w, s] = coords[0];
  let [e, n] = coords[0];
  for (const [x, y] of coords) {
    w = Math.min(w, x);
    e = Math.max(e, x);
    s = Math.min(s, y);
    n = Math.max(n, y);
  }
  return [
    [w, s],
    [e, n],
  ];
}

export const osmLink = (lat: number, lon: number) =>
  `https://www.openstreetmap.org/?mlat=${lat.toFixed(6)}&mlon=${lon.toFixed(6)}#map=20/${lat.toFixed(6)}/${lon.toFixed(6)}`;
