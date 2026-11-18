import { Paper, SegmentedControl } from '@mantine/core';
import type { GeoJSONSource, LngLatBoundsLike, Marker } from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import { boundsOf, circlePolygon, type Position } from '../../lib/geo';
import { EMPTY_FC, overlayPalette, type BaseLayer } from './basemap';
import { createFindingMarker } from './markers';
import { useMapLibre } from './useMapLibre';

interface Props {
  position: Position;
  accuracyM: number | null;
  defectType: string;
  severity: string | null;
  flightPath?: { coordinates: number[][] } | null;
  height?: number;
}

/** Small map for one finding: marker, GPS accuracy circle, faint flight path for context. */
export function MiniMap({ position, accuracyM, defectType, severity, flightPath, height = 220 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [base, setBase] = useState<BaseLayer>('map');
  const { map, scheme } = useMapLibre(ref, {
    base,
    center: [position.lon, position.lat],
    zoom: 19,
    scrollZoom: false,
  });
  const marker = useRef<Marker | null>(null);

  useEffect(() => {
    if (!map) return;
    const radius = accuracyM && accuracyM > 0 ? accuracyM : null;
    const circle: GeoJSON.FeatureCollection = radius
      ? {
          type: 'FeatureCollection',
          features: [{ type: 'Feature', geometry: circlePolygon(position.lon, position.lat, radius), properties: {} }],
        }
      : EMPTY_FC;
    const path: GeoJSON.FeatureCollection = flightPath
      ? {
          type: 'FeatureCollection',
          features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: flightPath.coordinates }, properties: {} }],
        }
      : EMPTY_FC;

    if (!map.getSource('accuracy')) {
      map.addSource('context-path', { type: 'geojson', data: path });
      map.addLayer({
        id: 'context-path',
        type: 'line',
        source: 'context-path',
        paint: { 'line-color': '#c6f432', 'line-width': 1.5, 'line-opacity': 0.6 },
      });
      map.addSource('accuracy', { type: 'geojson', data: circle });
      map.addLayer({ id: 'accuracy-fill', type: 'fill', source: 'accuracy', paint: { 'fill-color': '#c6f432', 'fill-opacity': 0.12 } });
      map.addLayer({
        id: 'accuracy-line',
        type: 'line',
        source: 'accuracy',
        paint: { 'line-color': '#c6f432', 'line-width': 1.5, 'line-dasharray': [2, 1.5] },
      });
    } else {
      (map.getSource('accuracy') as GeoJSONSource).setData(circle);
      (map.getSource('context-path') as GeoJSONSource).setData(path);
    }

    marker.current?.remove();
    const m = createFindingMarker({ finding_id: '', defect_type: defectType, severity }, position);
    m.marker.addTo(map);
    marker.current = m.marker;

    const coords: [number, number][] = radius
      ? (circlePolygon(position.lon, position.lat, radius, 16).coordinates[0] as [number, number][])
      : [[position.lon, position.lat]];
    const b = boundsOf(coords);
    if (b) map.fitBounds(b as LngLatBoundsLike, { padding: 36, maxZoom: 20, duration: 0 });
  }, [map, position, accuracyM, defectType, severity, flightPath]);

  useEffect(() => () => {
    marker.current?.remove();
  }, []);

  useEffect(() => {
    if (!map || !map.getLayer('accuracy-fill')) return;
    const p = overlayPalette(base, scheme);
    map.setPaintProperty('accuracy-fill', 'fill-color', p.accuracy);
    map.setPaintProperty('accuracy-line', 'line-color', p.accuracy);
    map.setPaintProperty('context-path', 'line-color', p.flight);
  }, [map, base, scheme, position]);

  return (
    <Paper withBorder radius="md" style={{ overflow: 'hidden', position: 'relative', height }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} role="region" aria-label="Finding location map" />
      <SegmentedControl
        size="xs"
        value={base}
        onChange={(v) => setBase(v as BaseLayer)}
        data={[
          { label: 'Map', value: 'map' },
          { label: 'Satellite', value: 'satellite' },
        ]}
        aria-label="Base map"
        withItemsBorders={false}
        style={{ position: 'absolute', top: 8, left: 8, zIndex: 2, boxShadow: 'var(--mantine-shadow-sm)' }}
      />
    </Paper>
  );
}
