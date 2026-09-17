import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { buildPolylinePoints, remarkLayout } from '../../lib/logGrid';
import { JOHN_DOE_DAY, LIMITS } from '../../test/fixtures';
import type { DayTotals, Segment } from '../../types';
import { LogGrid } from '../LogGrid';

const THREE_STATUS_DAY: Segment[] = [
  { status: 'OFF_DUTY', start_min: 0, end_min: 360 },
  { status: 'DRIVING', start_min: 360, end_min: 900 },
  { status: 'SLEEPER_BERTH', start_min: 900, end_min: 1440 },
];
const THREE_STATUS_TOTALS: DayTotals = { OFF_DUTY: 6, SLEEPER_BERTH: 9, DRIVING: 9, ON_DUTY_NOT_DRIVING: 0 };

function renderGrid(props: Partial<Parameters<typeof LogGrid>[0]> = {}) {
  return render(
    <LogGrid
      segments={JOHN_DOE_DAY.segments}
      totals={JOHN_DOE_DAY.totals}
      remarks={JOHN_DOE_DAY.remarks}
      limits={LIMITS}
      {...props}
    />,
  );
}

describe('LogGrid', () => {
  it('renders the four row labels in form order', () => {
    const { container } = renderGrid();

    const labels = [...container.querySelectorAll('[data-row] .log-grid__row-label')].map((label) =>
      [...label.querySelectorAll('tspan')].map((line) => line.textContent).join(' '),
    );
    expect(labels).toEqual(['1. Off Duty', '2. Sleeper Berth', '3. Driving', '4. On Duty (not driving)']);
  });

  it('draws one polyline with the expected points for a three-status day', () => {
    const { container } = renderGrid({ segments: THREE_STATUS_DAY, totals: THREE_STATUS_TOTALS, remarks: [] });

    const polylines = container.querySelectorAll('polyline');
    expect(polylines).toHaveLength(1);
    const points = polylines[0]?.getAttribute('points') ?? '';
    expect(points.split(' ')).toHaveLength(6);
    expect(points).toBe(buildPolylinePoints(THREE_STATUS_DAY, LIMITS));
  });

  it('renders 97 ticks, 25 of them hour height', () => {
    const { container } = renderGrid();

    expect(container.querySelectorAll('[data-tick]')).toHaveLength(97);
    expect(container.querySelectorAll('[data-tick="hour"]')).toHaveLength(25);
    expect(container.querySelectorAll('[data-tick="half"]')).toHaveLength(24);
    expect(container.querySelectorAll('[data-tick="quarter"]')).toHaveLength(48);
    const hourLabels = [...container.querySelectorAll('[data-hour-label]')].map((label) => label.textContent);
    expect(hourLabels[0]).toBe('Mid-night');
    expect(hourLabels[12]).toBe('Noon');
    expect(hourLabels.at(-1)).toBe('Mid-night');
  });

  it('renders each remark as rotated text with a leader line', () => {
    const { container } = renderGrid();

    const remark = container.querySelector('[data-remark="540"]');
    const text = remark?.querySelector('text');
    expect(text?.textContent).toBe('Fredericksburg, VA');
    expect(text?.getAttribute('transform')).toBe(remarkLayout(JOHN_DOE_DAY.remarks, LIMITS)[1]?.transform);
    expect(text?.getAttribute('text-anchor')).toBe('end');
    expect(text?.getAttribute('transform')).toMatch(/^rotate\(-90 /);
    expect(remark?.querySelector('line.log-grid__leader')).not.toBeNull();
    expect(container.querySelectorAll('[data-remark]')).toHaveLength(6);
  });

  it('renders one total per row and their sum', () => {
    const { container } = renderGrid();

    const total = (key: string) => container.querySelector(`[data-total="${key}"] text`)?.textContent;
    expect(['OFF_DUTY', 'SLEEPER_BERTH', 'DRIVING', 'ON_DUTY_NOT_DRIVING'].map(total)).toEqual(['10', '1.75', '7.75', '4.5']);
    expect(total('sum')).toBe('=24');
  });

  it('renders a single-status day', () => {
    const { container } = renderGrid({
      segments: [{ status: 'SLEEPER_BERTH', start_min: 0, end_min: 1440 }],
      totals: { OFF_DUTY: 0, SLEEPER_BERTH: 24, DRIVING: 0, ON_DUTY_NOT_DRIVING: 0 },
      remarks: [{ at_min: 0, location: 'Cheyenne, WY' }],
    });

    expect(container.querySelector('polyline')?.getAttribute('points')?.split(' ')).toHaveLength(2);
    expect(container.querySelector('[data-total="sum"] text')?.textContent).toBe('=24');
  });

  it('truncates a long remark and carries the full location in a title', () => {
    const { container } = renderGrid({ remarks: [{ at_min: 600, location: 'US-287 N near Dropoff, CC' }] });

    const text = container.querySelector('[data-remark="600"] text');
    expect(text?.querySelector('title')?.textContent).toBe('US-287 N near Dropoff, CC');
    expect(text?.lastChild?.textContent).toBe('US-287 N near Dropoff…');
  });

  it('staggers remarks 15 minutes apart', () => {
    const { container } = renderGrid({
      remarks: [
        { at_min: 900, location: 'Philadelphia, PA' },
        { at_min: 915, location: 'Camden, NJ' },
      ],
    });

    expect([...container.querySelectorAll('[data-remark]')].map((remark) => remark.getAttribute('data-depth'))).toEqual(['shallow', 'deep']);
  });

  it('draws a leader but no text for a remark without a location', () => {
    const { container } = renderGrid({ remarks: [{ at_min: 600, location: null }] });

    const remark = container.querySelector('[data-remark="600"]');
    expect(remark?.querySelector('line')).not.toBeNull();
    expect(remark?.querySelector('text')).toBeNull();
  });
});
