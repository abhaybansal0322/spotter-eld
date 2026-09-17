import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LIMITS, TRIP_PLAN } from '../../test/fixtures';
import type { Stop, TripSummary } from '../../types';
import { CycleMeter } from '../CycleMeter';

function renderMeter(overrides: Partial<TripSummary>, stops: Stop[] = TRIP_PLAN.stops) {
  return render(<CycleMeter limits={LIMITS} summary={{ ...TRIP_PLAN.summary, ...overrides }} stops={stops} timezone="America/Chicago" />);
}

const width = (container: HTMLElement, key: string) =>
  parseFloat((container.querySelector(`[data-segment="${key}"]`) as HTMLElement).style.width);
const hours = (container: HTMLElement, key: string) => container.querySelector(`[data-hours="${key}"]`)?.textContent;

const RESTART: Stop = {
  kind: 'RESTART', at_mile: 0, lat: 41.8781, lng: -87.6298, label: 'Chicago, IL',
  arrive: '2026-09-16T06:00:00-05:00', depart: '2026-09-17T16:00:00-05:00', duration_hours: 34,
};

describe('CycleMeter', () => {
  it('draws the plan from its summary alone, with no request in hand', () => {
    // The fixture: 20 h before, 21 h added, 41 h at dropoff. The component takes no submitted cycle figure at all.
    const { container } = renderMeter({});

    expect([hours(container, 'prior'), hours(container, 'trip'), hours(container, 'remaining')]).toEqual(['20 h', '21 h', '29 h']);
    expect(width(container, 'prior')).toBeCloseTo((20 / 70) * 100, 6);
    expect(width(container, 'trip')).toBeCloseTo((21 / 70) * 100, 6);
    expect(width(container, 'remaining')).toBeCloseTo((29 / 70) * 100, 6);
    expect((container.querySelector('[data-limit]') as HTMLElement).style.left).toBe('100%');
    expect(screen.getByText('70-hour cycle')).toBeTruthy();
    expect(screen.getByText('41 / 70 h at dropoff')).toBeTruthy();
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('rescales and moves the limit marker when on-duty work runs past 70 hours', () => {
    const { container } = renderMeter({ cycle_used_at_start_hours: 69, on_duty_added_hours: 2, cycle_used_at_end: 71 });

    expect(parseFloat((container.querySelector('[data-limit]') as HTMLElement).style.left)).toBeCloseTo((70 / 71) * 100, 6);
    expect(hours(container, 'remaining')).toBe('0 h');
  });

  it('keeps the exact added hours in the legend but draws only what still counts after a restart', () => {
    const { container } = renderMeter(
      { cycle_used_at_start_hours: 70, on_duty_added_hours: 25, cycle_used_at_end: 21, restart_required: true },
      [RESTART, ...TRIP_PLAN.stops.slice(1)],
    );

    const note = screen.getByRole('note');
    expect(note.textContent).toContain('34-hour restart was inserted at Chicago, IL');
    expect(note.textContent).toContain('Wed 09/16 06:00');
    expect([hours(container, 'prior'), hours(container, 'trip'), hours(container, 'remaining')]).toEqual(['70 h', '25 h', '49 h']);
    expect(width(container, 'prior')).toBe(0);
    expect(width(container, 'trip')).toBeCloseTo((21 / 70) * 100, 6);
  });

  it('explains hours that rolled out of the 8-day window without a restart', () => {
    const { container } = renderMeter({ cycle_used_at_start_hours: 10, on_duty_added_hours: 50, cycle_used_at_end: 50 });

    expect(screen.getByRole('note').textContent).toContain('10 h rolled out of the 8-day window');
    expect(width(container, 'prior')).toBe(0);
    expect(width(container, 'trip')).toBeCloseTo((50 / 70) * 100, 6);
  });
});
