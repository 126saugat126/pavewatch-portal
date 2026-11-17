import { useComputedColorScheme } from '@mantine/core';
import { Map as MapLibreMap, NavigationControl, ScaleControl, setWorkerUrl, type MapOptions } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { useEffect, useRef, useState, type RefObject } from 'react';
import { applyBase, baseStyle, type BaseLayer } from './basemap';

// MapLibre 6 finds its worker relative to its own module URL, which breaks once
// Vite pre-bundles/fingerprints it. Point it at the bundled worker file explicitly.
setWorkerUrl(workerUrl);

/**
 * Creates a MapLibre map in `container` once, keeps the base layer in sync with
 * the colour scheme / chosen base, and resizes with its container.
 * Returns the map only after its style has loaded (safe to add layers).
 */
export function useMapLibre(
  container: RefObject<HTMLDivElement | null>,
  options: Partial<MapOptions> & { base: BaseLayer },
) {
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const scheme = useComputedColorScheme('light');
  const initial = useRef(options);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    const { base: _base, ...rest } = initial.current;
    void _base;
    const m = new MapLibreMap({
      container: el,
      style: baseStyle(),
      // Fallback view only; callers pass `bounds` or `center`/`zoom` so the first tiles
      // requested are already the survey area.
      center: [0, 20],
      zoom: 1.5,
      maxZoom: 21,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      ...rest,
    });
    m.touchZoomRotate.disableRotation();
    m.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    m.addControl(new ScaleControl({ unit: 'metric', maxWidth: 100 }), 'bottom-left');
    // Ready as soon as the style is parsed - NOT on 'load', which waits for every base
    // tile and would delay overlays/markers on a slow tile server.
    let ready = false;
    const markReady = () => {
      if (ready) return;
      ready = true;
      setMap(m);
    };
    if (m.isStyleLoaded()) markReady();
    else m.once('style.load', markReady);
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      setMap(null);
      m.remove();
    };
  }, [container]);

  useEffect(() => {
    if (map) applyBase(map, options.base, scheme);
  }, [map, options.base, scheme]);

  return { map, scheme };
}
