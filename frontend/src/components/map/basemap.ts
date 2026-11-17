import type { MapOptions, Map as MapLibreMap } from 'maplibre-gl';

/**
 * Base maps. Everything map-provider specific lives in this file, so moving to
 * Google Maps (or another provider) later means replacing this module and the
 * MapLibre hook, not the pages.
 *
 *  - "map": OpenStreetMap standard tiles (no API key). Dark mode re-tones the same
 *    tiles with raster filters instead of needing a second provider.
 *  - "satellite": Esri World Imagery.
 *
 * Both are fine for local development and demos. Before a public deployment,
 * switch to a provider with a usage plan (e.g. Google Maps, MapTiler, Stadia):
 * the OSM tile servers do not allow heavy production traffic.
 */

export type BaseLayer = 'map' | 'satellite';
type Style = Exclude<MapOptions['style'], string | undefined>;

export function baseStyle(): Style {
  return {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      },
      satellite: {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        maxzoom: 19,
        attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
      },
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#e8e7e3' } },
      { id: 'base-osm', type: 'raster', source: 'osm', layout: { visibility: 'visible' } },
      { id: 'base-satellite', type: 'raster', source: 'satellite', layout: { visibility: 'none' } },
    ],
  };
}

export function applyBase(map: MapLibreMap, base: BaseLayer, scheme: 'light' | 'dark') {
  if (!map.getLayer('base-osm')) return;
  map.setLayoutProperty('base-osm', 'visibility', base === 'map' ? 'visible' : 'none');
  map.setLayoutProperty('base-satellite', 'visibility', base === 'satellite' ? 'visible' : 'none');
  const dark = scheme === 'dark';
  // Light: slightly muted so markers stand out. Dark: invert + rotate hue back + desaturate.
  map.setPaintProperty('base-osm', 'raster-brightness-min', dark ? 0.9 : 0);
  map.setPaintProperty('base-osm', 'raster-brightness-max', dark ? 0.08 : 1);
  map.setPaintProperty('base-osm', 'raster-hue-rotate', dark ? 180 : 0);
  map.setPaintProperty('base-osm', 'raster-saturation', dark ? -0.75 : -0.35);
  map.setPaintProperty('base-osm', 'raster-contrast', dark ? -0.05 : -0.05);
  map.setPaintProperty('background', 'background-color', dark ? '#1d1d1b' : '#e8e7e3');
}

/** Overlay colours. MapLibre cannot read CSS variables, so the tokens are mirrored here. */
export function overlayPalette(base: BaseLayer, scheme: 'light' | 'dark') {
  const dark = base === 'satellite' || scheme === 'dark';
  return {
    flight: dark ? '#6da7ec' : '#2a78d6',
    flightCasing: dark ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.9)',
    warnFill: dark ? '#f0efec' : '#52514e',
    warnFillOpacity: dark ? 0.16 : 0.14,
    warnLine: dark ? '#f0efec' : '#52514e',
    accuracy: dark ? '#86b6ef' : '#2a78d6',
  };
}

export const EMPTY_FC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
