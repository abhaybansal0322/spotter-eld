import { useEffect, useRef, type KeyboardEvent } from 'react';

import { hoursToHHMM, mileMarker, terminalTime, zoneAbbreviation } from '../lib/format';
import { KIND_LABEL, KIND_STATUS } from '../lib/stops';
import type { Stop } from '../types';
import { ScrollX } from './ScrollX';
import './StopTimeline.css';

export interface StopTimelineProps {
  stops: Stop[];
  timezone: string;
  selectedIndex: number | null;
  /** A stop hovered on the map: its row is highlighted and scrolled into view. */
  mapHoverIndex: number | null;
  onSelect: (index: number) => void;
  onHover: (index: number | null) => void;
}

/** Every stop in order, dispatch-board style. Hovering or selecting a row highlights its marker on the map, and
 * hovering a marker highlights its row here. */
export function StopTimeline({ stops, timezone, selectedIndex, mapHoverIndex, onSelect, onHover }: StopTimelineProps) {
  const body = useRef<HTMLTableSectionElement>(null);

  useEffect(() => {
    if (mapHoverIndex === null) return;
    // 'nearest' leaves a row that is already visible where it is, so the page only moves when it has to.
    body.current?.children[mapHoverIndex]?.scrollIntoView?.({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }, [mapHoverIndex]);

  const zone = stops[0] ? zoneAbbreviation(stops[0].arrive, timezone) : timezone;

  const onKeyDown = (index: number) => (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(index);
    }
  };

  return (
    <section className="panel stop-timeline" aria-label="Stops">
      <header className="panel__header">
        <h2 className="panel__title">Stops</h2>
        <span className="stop-timeline__zone">Home terminal time, {zone}</span>
      </header>
      <ScrollX className="stop-timeline__scroll" label="Stops table" hint="Scroll for more columns" hintKey="stops">
        <table className="stop-timeline__table">
          <thead>
            <tr>
              <th scope="col">Stop</th>
              <th scope="col">Location</th>
              <th scope="col" className="numeric">Arrive</th>
              <th scope="col" className="numeric">Depart</th>
              <th scope="col" className="numeric">Hours</th>
              <th scope="col" className="numeric">Mile</th>
            </tr>
          </thead>
          <tbody ref={body} onMouseLeave={() => onHover(null)}>
            {stops.map((stop, index) => (
              <tr
                key={`${stop.kind}-${stop.arrive}`}
                data-kind={stop.kind}
                aria-selected={index === selectedIndex}
                data-map-hover={index === mapHoverIndex || undefined}
                tabIndex={0}
                onClick={() => onSelect(index)}
                onKeyDown={onKeyDown(index)}
                onMouseEnter={() => onHover(index)}
                onFocus={() => onHover(index)}
                onBlur={() => onHover(null)}
              >
                <td>
                  <span className="kind-chip" data-status={KIND_STATUS[stop.kind] ?? 'START'}>
                    <span className="kind-chip__swatch" aria-hidden="true" />
                    {KIND_LABEL[stop.kind]}
                  </span>
                </td>
                <td className="stop-timeline__label">{stop.label}</td>
                <td className="numeric figure">{terminalTime(stop.arrive, timezone)}</td>
                <td className="numeric figure">{terminalTime(stop.depart, timezone)}</td>
                <td className="numeric figure">{hoursToHHMM(stop.duration_hours)}</td>
                <td className="numeric figure">{mileMarker(stop.at_mile)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollX>
    </section>
  );
}
