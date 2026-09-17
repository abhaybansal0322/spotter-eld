import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';

import { durationLabel, mileMarker, terminalTime, zoneAbbreviation } from '../lib/format';
import { KIND_GLYPH, KIND_LABEL, KIND_STATUS, kindsPresent } from '../lib/stops';
import type { LatLng, Route, Stop, StopKind } from '../types';
import './RouteMap.css';

export interface RouteMapProps {
  route: Route;
  stops: Stop[];
  timezone: string;
  /** Index into stops of the stop to emphasise, from the timeline's hover or selection. */
  highlightedIndex: number | null;
  onSelectStop: (index: number) => void;
}

const OSM_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const FIT_PADDING: [number, number] = [28, 28];

// Built as divIcons with inline SVG: Leaflet's default marker images resolve to broken URLs under Vite.
const iconCache = new Map<string, L.DivIcon>();

export function stopIcon(kind: StopKind, highlighted: boolean): L.DivIcon {
  const key = `${kind}:${highlighted}`;
  const cached = iconCache.get(key);
  if (cached) {
    return cached;
  }
  const status = KIND_STATUS[kind] ?? 'START';
  const icon = L.divIcon({
    className: `stop-marker stop-marker--${kind}${highlighted ? ' stop-marker--active' : ''}`,
    html:
      `<svg viewBox="0 0 28 36" width="28" height="36" data-status="${status}" aria-hidden="true">` +
      '<path class="stop-marker__pin" d="M14 35C14 35 26 21.6 26 13A12 12 0 0 0 2 13c0 8.6 12 22 12 22Z"/>' +
      `<text class="stop-marker__glyph" x="14" y="17.5" text-anchor="middle">${KIND_GLYPH[kind]}</text>` +
      '</svg>',
    iconSize: [28, 36],
    iconAnchor: [14, 35],
    popupAnchor: [0, -30],
  });
  iconCache.set(key, icon);
  return icon;
}

function FitToRoute({ bbox }: { bbox: [LatLng, LatLng] }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(bbox, { padding: FIT_PADDING });
  }, [map, bbox]);
  return null;
}

export function RouteMap({ route, stops, timezone, highlightedIndex, onSelectStop }: RouteMapProps) {
  return (
    <section className="panel route-map" aria-label="Route map">
      <header className="panel__header">
        <h2 className="panel__title">Route</h2>
        <MapLegend kinds={kindsPresent(stops)} />
      </header>
      <MapContainer className="route-map__canvas" bounds={route.bbox} boundsOptions={{ padding: FIT_PADDING }} scrollWheelZoom={false}>
        <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} />
        <FitToRoute bbox={route.bbox} />
        <Polyline positions={route.geometry} pathOptions={{ className: 'route-map__line' }} />
        {stops.map((stop, index) => (
          <Marker
            key={`${stop.kind}-${stop.arrive}`}
            position={[stop.lat, stop.lng]}
            icon={stopIcon(stop.kind, index === highlightedIndex)}
            title={`${KIND_LABEL[stop.kind]}: ${stop.label}`}
            zIndexOffset={index === highlightedIndex ? 1000 : 0}
            eventHandlers={{ click: () => onSelectStop(index) }}
          >
            <Popup>
              <StopPopup stop={stop} timezone={timezone} />
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </section>
  );
}

function StopPopup({ stop, timezone }: { stop: Stop; timezone: string }) {
  return (
    <div className="stop-popup">
      <p className="stop-popup__kind" data-status={KIND_STATUS[stop.kind] ?? 'START'}>
        <span className="kind-chip__swatch" aria-hidden="true" /> {KIND_LABEL[stop.kind]}
      </p>
      <p className="stop-popup__label">{stop.label}</p>
      <dl className="stop-popup__facts">
        <dt>Arrive</dt>
        <dd className="figure">{terminalTime(stop.arrive, timezone)}</dd>
        <dt>Depart</dt>
        <dd className="figure">{terminalTime(stop.depart, timezone)}</dd>
        <dt>Duration</dt>
        <dd className="figure">{durationLabel(stop.duration_hours)}</dd>
        <dt>Mile</dt>
        <dd className="figure">{mileMarker(stop.at_mile)}</dd>
      </dl>
      <p className="stop-popup__zone">Times in {zoneAbbreviation(stop.arrive, timezone)}, home terminal</p>
    </div>
  );
}

function MapLegend({ kinds }: { kinds: StopKind[] }) {
  return (
    <ul className="route-map__legend" aria-label="Map legend">
      {kinds.map((kind) => (
        <li key={kind} className="kind-chip" data-status={KIND_STATUS[kind] ?? 'START'} data-kind={kind}>
          <span className="route-map__legend-glyph" aria-hidden="true">
            {KIND_GLYPH[kind]}
          </span>
          {KIND_LABEL[kind]}
        </li>
      ))}
    </ul>
  );
}
