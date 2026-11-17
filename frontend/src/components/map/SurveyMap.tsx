import { ActionIcon, Group, Paper, SegmentedControl, Text, Tooltip } from '@mantine/core';
import { IconFocus2 } from '@tabler/icons-react';
import type { GeoJSONSource, LngLatBoundsLike, MapLayerMouseEvent, Marker } from 'maplibre-gl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FindingListItem, RunDetail } from '../../api/types';
import { SEVERITIES, severityMeta, warningMeta } from '../../lib/defects';
import { boundsOf, findingPosition, geometryCoords, type Position } from '../../lib/geo';
import { EMPTY_FC, overlayPalette, type BaseLayer } from './basemap';
import { addStartMarker, createFindingMarker, findingPopupContent, makePopup, textPopupContent } from './markers';
import { useMapLibre } from './useMapLibre';

interface Props {
  run: RunDetail;
  /** Findings to draw (already filtered). */
  findings: FindingListItem[];
  /** All findings in the run - used once to frame the map. */
  allFindings: FindingListItem[];
  hoveredId: string | null;
  onHover: (id: string | null, fromMap: boolean) => void;
  onOpen: (id: string) => void;
  height: number | string;
}

export function SurveyMap({ run, findings, allFindings, hoveredId, onHover, onOpen, height }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [base, setBase] = useState<BaseLayer>('map');
  const origin = run.local_frame_origin;

  const bounds = useMemo(() => {
    const coords: [number, number][] = [];
    run.flight_path?.coordinates.forEach((c) => coords.push([c[0], c[1]]));
    run.data_warnings.forEach((w) => coords.push(...geometryCoords(w.geometry)));
    allFindings.forEach((f) => {
      const p = findingPosition(f, origin);
      if (p) coords.push([p.lon, p.lat]);
    });
    if (origin) coords.push([origin.lon, origin.lat]);
    return boundsOf(coords);
  }, [run, allFindings, origin]);

  // Start already framed on the survey, so the first tiles fetched are the right ones.
  const { map, scheme } = useMapLibre(ref, {
    base,
    ...(bounds ? { bounds: bounds as LngLatBoundsLike, fitBoundsOptions: { padding: 48, maxZoom: 20 } } : {}),
  });
  const markers = useRef(new Map<string, { marker: Marker; el: HTMLElement; pos: Position; f: FindingListItem }>());
  const popup = useRef(makePopup());
  const cb = useRef({ onHover, onOpen });
  cb.current = { onHover, onOpen };

  const fit = useCallback(
    (animate = true) => {
      if (map && bounds) map.fitBounds(bounds as LngLatBoundsLike, { padding: 48, maxZoom: 20, duration: animate ? 500 : 0 });
    },
    [map, bounds],
  );

  // Static overlays: data-warning areas, flight path, start point.
  useEffect(() => {
    if (!map) return;
    const warnings: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: run.data_warnings
        .filter((w) => w.geometry)
        .map((w) => ({
          type: 'Feature',
          geometry: w.geometry as GeoJSON.Geometry,
          properties: { code: w.code, label: warningMeta(w.code).label, message: w.message ?? '' },
        })),
    };
    const flight: GeoJSON.FeatureCollection = run.flight_path
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: run.flight_path, properties: {} }] }
      : EMPTY_FC;

    if (!map.getSource('warnings')) {
      map.addSource('warnings', { type: 'geojson', data: warnings });
      map.addLayer({
        id: 'warnings-fill',
        type: 'fill',
        source: 'warnings',
        filter: ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
        paint: { 'fill-color': '#52514e', 'fill-opacity': 0.14 },
      });
      map.addLayer({
        id: 'warnings-line',
        type: 'line',
        source: 'warnings',
        paint: { 'line-color': '#52514e', 'line-width': 1.5, 'line-dasharray': [3, 2] },
      });
      map.addSource('flight', { type: 'geojson', data: flight });
      map.addLayer({
        id: 'flight-casing',
        type: 'line',
        source: 'flight',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#fff', 'line-width': 5 },
      });
      map.addLayer({
        id: 'flight-line',
        type: 'line',
        source: 'flight',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#2a78d6', 'line-width': 2.5, 'line-opacity': 0.9 },
      });
    } else {
      (map.getSource('warnings') as GeoJSONSource).setData(warnings);
      (map.getSource('flight') as GeoJSONSource).setData(flight);
    }
    const start = origin ? addStartMarker(map, origin.lon, origin.lat) : null;
    return () => {
      start?.remove();
    };
  }, [map, run, origin]);

  // Frame the survey once the map is ready.
  useEffect(() => fit(false), [fit]);

  // Overlay colours follow the theme and base layer.
  useEffect(() => {
    if (!map || !map.getLayer('flight-line')) return;
    const p = overlayPalette(base, scheme);
    map.setPaintProperty('flight-line', 'line-color', p.flight);
    map.setPaintProperty('flight-casing', 'line-color', p.flightCasing);
    map.setPaintProperty('warnings-fill', 'fill-color', p.warnFill);
    map.setPaintProperty('warnings-fill', 'fill-opacity', p.warnFillOpacity);
    map.setPaintProperty('warnings-line', 'line-color', p.warnLine);
  }, [map, base, scheme, run]);

  // Hovering a warning area explains it.
  useEffect(() => {
    if (!map) return;
    const areaPopup = makePopup();
    const move = (e: MapLayerMouseEvent) => {
      const props = e.features?.[0]?.properties as { label?: string; message?: string } | undefined;
      if (!props) return;
      map.getCanvas().style.cursor = 'help';
      areaPopup.setLngLat(e.lngLat).setDOMContent(textPopupContent(props.label ?? 'Data warning', props.message)).addTo(map);
    };
    const leave = () => {
      map.getCanvas().style.cursor = '';
      areaPopup.remove();
    };
    map.on('mousemove', 'warnings-fill', move);
    map.on('mouseleave', 'warnings-fill', leave);
    return () => {
      map.off('mousemove', 'warnings-fill', move);
      map.off('mouseleave', 'warnings-fill', leave);
      areaPopup.remove();
    };
  }, [map]);

  // Finding markers (rebuilt when the filtered set changes). High severity drawn last = on top.
  useEffect(() => {
    if (!map) return;
    const store = markers.current;
    const ordered = [...findings].sort((a, b) => severityMeta(a.severity).rank - severityMeta(b.severity).rank);
    for (const f of ordered) {
      const pos = findingPosition(f, origin);
      if (!pos) continue;
      const { marker, el } = createFindingMarker(f, pos, {
        onEnter: () => cb.current.onHover(f.finding_id, true),
        onLeave: () => cb.current.onHover(null, true),
        onClick: () => cb.current.onOpen(f.finding_id),
      });
      marker.addTo(map);
      store.set(f.finding_id, { marker, el, pos, f });
    }
    return () => {
      store.forEach(({ marker }) => marker.remove());
      store.clear();
    };
  }, [map, findings, origin]);

  // Hover highlight + tooltip, driven from either the map or the list.
  useEffect(() => {
    const p = popup.current;
    markers.current.forEach(({ el }, id) => {
      const on = id === hoveredId;
      el.classList.toggle('is-hovered', on);
      el.style.zIndex = on ? '5' : '';
    });
    const hit = hoveredId ? markers.current.get(hoveredId) : undefined;
    if (map && hit) {
      p.setLngLat([hit.pos.lon, hit.pos.lat]).setDOMContent(findingPopupContent(hit.f, hit.pos.approx)).addTo(map);
    } else {
      p.remove();
    }
  }, [hoveredId, map, findings]);

  const located = allFindings.filter((f) => findingPosition(f, origin)).length;
  const hasGeo = !!bounds;

  return (
    <Paper withBorder radius="md" style={{ overflow: 'hidden', position: 'relative', height }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} aria-label="Survey map" role="region" />
      <Group gap={6} style={{ position: 'absolute', top: 10, left: 10, zIndex: 2 }}>
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
          styles={{ root: { boxShadow: 'var(--mantine-shadow-sm)' } }}
        />
        <Tooltip label="Fit survey area" withArrow>
          <ActionIcon variant="default" size={30} onClick={() => fit()} aria-label="Fit survey area" style={{ boxShadow: 'var(--mantine-shadow-sm)' }}>
            <IconFocus2 size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {!hasGeo && (
        <Paper
          withBorder
          p="sm"
          style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', zIndex: 2 }}
        >
          <Text fz="sm">This survey has no location data to show on a map.</Text>
        </Paper>
      )}
      {hasGeo && located < allFindings.length && (
        <Text
          fz="xs"
          px={8}
          py={4}
          bg="var(--mantine-color-body)"
          style={{ position: 'absolute', bottom: 30, right: 10, zIndex: 2, borderRadius: 4, opacity: 0.92 }}
        >
          {allFindings.length - located} finding(s) have no location and are not shown
        </Text>
      )}
    </Paper>
  );
}

/** Legend: severity (colour + size + label), path, warning areas, approximate positions. */
export function MapLegend({ showApprox }: { showApprox: boolean }) {
  return (
    <Group gap="lg" mt="xs" fz="xs" c="dimmed" wrap="wrap" aria-label="Map legend" style={{ rowGap: 6 }}>
      {SEVERITIES.map((s) => (
        <Group key={s} gap={6} wrap="nowrap">
          <span className="pw-legend-dot" data-sev={s} />
          <span>{severityMeta(s).label} severity</span>
        </Group>
      ))}
      {showApprox && (
        <Group gap={6} wrap="nowrap">
          <span className="pw-legend-dot" data-sev="medium" data-approx="true" />
          <span>No GPS (approximate)</span>
        </Group>
      )}
      <Group gap={6} wrap="nowrap">
        <span className="pw-legend-line" />
        <span>Flight path</span>
      </Group>
      <Group gap={6} wrap="nowrap">
        <span className="pw-legend-area" />
        <span>Data warning area</span>
      </Group>
      <span>Letters: P pothole · C crack · D depression · R raised · S step · O other</span>
    </Group>
  );
}
