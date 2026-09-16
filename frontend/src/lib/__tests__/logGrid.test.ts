import { describe, expect, it } from 'vitest';

import type { Limits, Segment } from '../../types';
import {
  buildPolylinePoints,
  GRID_H,
  GRID_W,
  GRID_X,
  GRID_Y,
  minutesToX,
  REMARKS_H,
  remarkAnchor,
  ROW_H,
  statusToY,
  tickMarks,
} from '../logGrid';

// The limits object exactly as the API returns it (spec §25).
const LIMITS: Limits = {
  avg_speed_mph: 55,
  drive_limit_min: 660,
  window_limit_min: 840,
  qualifying_rest_min: 600,
  break_after_drive_min: 480,
  break_qualify_min: 30,
  cycle_limit_min: 4200,
  cycle_days: 8,
  restart_min: 2040,
  fuel_interval_mi: 1000,
  fuel_duration_min: 30,
  pickup_duration_min: 60,
  dropoff_duration_min: 60,
  break_duration_min: 30,
  grid_resolution_min: 15,
  minutes_per_day: 1440,
  minutes_per_hour: 60,
  recap_a_days: 7,
  recap_c_days: 5,
};

function parsePoints(points: string): [number, number][] {
  return points.split(' ').map((pair) => {
    const [x, y] = pair.split(',').map(Number);
    return [x as number, y as number];
  });
}

describe('minutesToX', () => {
  it('maps midnight, noon and the next midnight to the left edge, midpoint and right edge', () => {
    expect(minutesToX(0, LIMITS)).toBe(GRID_X);
    expect(minutesToX(1440, LIMITS)).toBe(GRID_X + GRID_W);
    expect(minutesToX(720, LIMITS)).toBe(GRID_X + GRID_W / 2);
    expect(minutesToX(15, LIMITS)).toBe(GRID_X + 10); // 10 px per 15 minutes
  });
});

describe('statusToY', () => {
  it('returns the four row centres in form order', () => {
    expect(statusToY('OFF_DUTY')).toBe(GRID_Y + ROW_H / 2);
    expect(statusToY('SLEEPER_BERTH')).toBe(GRID_Y + ROW_H * 1.5);
    expect(statusToY('DRIVING')).toBe(GRID_Y + ROW_H * 2.5);
    expect(statusToY('ON_DUTY_NOT_DRIVING')).toBe(GRID_Y + ROW_H * 3.5);
    expect(statusToY('ON_DUTY_NOT_DRIVING')).toBeLessThan(GRID_Y + GRID_H);
  });
});

describe('buildPolylinePoints', () => {
  it('draws a single-status day as one horizontal run', () => {
    const day: Segment[] = [{ status: 'OFF_DUTY', start_min: 0, end_min: 1440 }];

    const y = statusToY('OFF_DUTY');
    expect(buildPolylinePoints(day, LIMITS)).toBe(`${GRID_X},${y} ${GRID_X + GRID_W},${y}`);
  });

  it('adds a vertical connector at each status change', () => {
    const day: Segment[] = [
      { status: 'OFF_DUTY', start_min: 0, end_min: 360 },
      { status: 'DRIVING', start_min: 360, end_min: 900 },
      { status: 'SLEEPER_BERTH', start_min: 900, end_min: 1440 },
    ];

    const points = parsePoints(buildPolylinePoints(day, LIMITS));

    // Two points per horizontal run; each change starts a run at the previous run's end x on a new row.
    expect(points).toEqual([
      [GRID_X, statusToY('OFF_DUTY')],
      [minutesToX(360, LIMITS), statusToY('OFF_DUTY')],
      [minutesToX(360, LIMITS), statusToY('DRIVING')],
      [minutesToX(900, LIMITS), statusToY('DRIVING')],
      [minutesToX(900, LIMITS), statusToY('SLEEPER_BERTH')],
      [GRID_X + GRID_W, statusToY('SLEEPER_BERTH')],
    ]);
    const verticals = points.slice(1).filter(([x, y], i) => x === points[i]?.[0] && y !== points[i]?.[1]);
    expect(verticals).toHaveLength(2);
  });

  it('never moves left', () => {
    const day: Segment[] = [
      { status: 'OFF_DUTY', start_min: 0, end_min: 360 },
      { status: 'DRIVING', start_min: 360, end_min: 420 },
      { status: 'ON_DUTY_NOT_DRIVING', start_min: 420, end_min: 480 },
      { status: 'DRIVING', start_min: 480, end_min: 960 },
      { status: 'OFF_DUTY', start_min: 960, end_min: 990 },
      { status: 'DRIVING', start_min: 990, end_min: 1110 },
      { status: 'SLEEPER_BERTH', start_min: 1110, end_min: 1440 },
    ];

    const xs = parsePoints(buildPolylinePoints(day, LIMITS)).map(([x]) => x);

    expect(xs).toEqual([...xs].sort((a, b) => a - b));
    expect(xs[0]).toBe(GRID_X);
    expect(xs.at(-1)).toBe(GRID_X + GRID_W);
  });

  it('returns an empty string for no segments', () => {
    expect(buildPolylinePoints([], LIMITS)).toBe('');
  });
});

describe('tickMarks', () => {
  it('gives a labelled major tick every hour and a minor tick at every other 15-minute mark', () => {
    const ticks = tickMarks(LIMITS);
    const majors = ticks.filter((tick) => tick.major);
    const minors = ticks.filter((tick) => !tick.major);

    expect(ticks).toHaveLength(97); // every 15-minute boundary from 0 to 1440 inclusive
    expect(majors).toHaveLength(25);
    expect(minors).toHaveLength(72); // three per hour; the fourth quarter mark of each hour is the major tick
    expect(majors.map((tick) => tick.label)).toEqual([
      'Midnight', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11',
      'Noon', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', 'Midnight',
    ]);
    expect(minors.every((tick) => tick.label === undefined)).toBe(true);
    expect(new Set(ticks.map((tick) => tick.x)).size).toBe(ticks.length);
  });
});

describe('remarkAnchor', () => {
  it('rotates the label about its own anchor at the remark minute', () => {
    const anchor = remarkAnchor(540, LIMITS);

    expect(anchor.x).toBe(GRID_X + 360);
    expect(anchor.y).toBe(GRID_Y + GRID_H + REMARKS_H);
    expect(anchor.transform).toBe(`rotate(-90 ${anchor.x} ${anchor.y})`);
  });
});

describe('limits drive the grid', () => {
  it('follows a different minutes_per_day instead of a hardcoded 1440', () => {
    const halfDay: Limits = { ...LIMITS, minutes_per_day: 720 };

    expect(minutesToX(720, halfDay)).toBe(GRID_X + GRID_W);
    expect(minutesToX(720, halfDay)).not.toBe(minutesToX(720, LIMITS));
    expect(tickMarks(halfDay).filter((tick) => tick.major)).toHaveLength(13);
    expect(remarkAnchor(360, halfDay).x).toBe(GRID_X + GRID_W / 2);
    expect(buildPolylinePoints([{ status: 'DRIVING', start_min: 0, end_min: 720 }], halfDay)).toBe(
      `${GRID_X},${statusToY('DRIVING')} ${GRID_X + GRID_W},${statusToY('DRIVING')}`,
    );
  });

  it('follows grid_resolution_min and refuses a missing limit', () => {
    expect(tickMarks({ ...LIMITS, grid_resolution_min: 30 })).toHaveLength(49);

    const { minutes_per_day: _omitted, ...incomplete } = LIMITS;
    expect(() => minutesToX(0, incomplete)).toThrow('limits.minutes_per_day');
  });
});
