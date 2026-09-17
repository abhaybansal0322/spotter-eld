import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LIMITS, TRIP_PLAN } from '../../test/fixtures';
import type { Stop, TripSummary } from '../../types';
import { CycleMeter } from '../CycleMeter';

function renderMeter(summary: TripSummary, startHours: number, stops: Stop[] = TRIP_PLAN.stops) {
  return render(<CycleMeter limits={LIMITS} summary={summary} startHours={startHours} stops={stops} timezone="America/Chicago" />);
}

const width = (container: HTMLElement, key: string) =>
  (container.querySelector(`[data-segment="${key}"]`) as HTMLElement).style.width;
const hours = (container: HTMLElement, key: string) => container.querySelector(`[data-hours="${key}"]`)?.textContent;

describe('CycleMeter', () => {
  it('sizes prior, trip and remaining segments against the 70-hour limit', () => {
    const { container } = renderMeter(TRIP_PLAN.summary, 20);

    // 20 h before, 41 h at dropoff, so 21 h added and 29 h left, each a share of 70.
    expect([hours(container, 'prior'), hours(container, 'trip'), hours(container, 'remaining')]).toEqual(['20 h', '21 h', '29 h']);
    expect(parseFloat(width(container, 'prior'))).toBeCloseTo((20 / 70) * 100, 6);
    expect(parseFloat(width(container, 'trip'))).toBeCloseTo((21 / 70) * 100, 6);
    expect(parseFloat(width(container, 'remaining'))).toBeCloseTo((29 / 70) * 100, 6);
    expect((container.querySelector('[data-limit]') as HTMLElement).style.left).toBe('100%');
    expect(screen.getByText('70-hour cycle')).toBeTruthy();
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('rescales and moves the limit marker when on-duty work runs past 70 hours', () => {
    const { container } = renderMeter({ ...TRIP_PLAN.summary, cycle_used_at_end: 71 }, 69);

    expect(parseFloat((container.querySelector('[data-limit]') as HTMLElement).style.left)).toBeCloseTo((70 / 71) * 100, 6);
    expect(hours(container, 'remaining')).toBe('0 h');
  });

  it('explains an inserted restart only when the summary flags one', () => {
    const restart: Stop = {
      kind: 'RESTART', at_mile: 0, lat: 41.8781, lng: -87.6298, label: 'Chicago, IL',
      arrive: '2026-09-16T06:00:00-05:00', depart: '2026-09-17T16:00:00-05:00', duration_hours: 34,
    };
    const { container } = renderMeter({ ...TRIP_PLAN.summary, restart_required: true, cycle_used_at_end: 21 }, 70, [restart, ...TRIP_PLAN.stops.slice(1)]);

    const note = screen.getByRole('note');
    expect(note.textContent).toContain('34-hour restart was inserted at Chicago, IL');
    expect(note.textContent).toContain('Wed 09/16 06:00');
    expect(hours(container, 'prior')).toBe('0 h');
    expect(hours(container, 'trip')).toBe('21 h');
  });
});
