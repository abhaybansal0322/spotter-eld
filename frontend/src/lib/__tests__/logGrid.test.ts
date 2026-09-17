import { describe, expect, it } from 'vitest';

import { LIMITS } from '../../test/fixtures';
import type { Segment } from '../../types';
import type { RequiredLimits } from '../limits';
import {
  buildPolylinePoints,
  gridFrame,
  HOUR_BAND_H,
  LEADER_H,
  REMARK_DEEP_OFFSET,
  REMARK_MAX_CHARS,
  remarkLayout,
  remarksBandHeight,
  rowLayout,
  tickLines,
  totalHours,
  GRID_H,
  GRID_W,
  GRID_X,
  GRID_Y,
  minutesToX,
  ROW_H,
  statusToY,
  tickMarks,
  type TickMark,
} from '../logGrid';

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
  it('gives 97 ticks at three printed heights, never two at one x', () => {
    const ticks = tickMarks(LIMITS);
    const sizes = (size: string) => ticks.filter((tick) => tick.size === size);

    expect(ticks).toHaveLength(97); // every 15-minute boundary from 0 to 1440 inclusive
    expect(sizes('hour')).toHaveLength(25);
    expect(sizes('half')).toHaveLength(24);
    expect(sizes('quarter')).toHaveLength(48);
    expect(new Set(ticks.map((tick) => tick.x)).size).toBe(ticks.length);
    expect(sizes('hour').map((tick) => tick.label)).toEqual([
      'Midnight', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11',
      'Noon', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', 'Midnight',
    ]);
    expect(ticks.filter((tick) => tick.size !== 'hour').every((tick) => tick.label === undefined)).toBe(true);
    expect(ticks.slice(0, 5).map((tick) => tick.size)).toEqual(['hour', 'quarter', 'half', 'quarter', 'hour']);
  });

  it('draws an hour as one full-height rule and half and quarter ticks in every row, hanging as printed', () => {
    const [hour, quarter, half] = tickMarks(LIMITS) as [TickMark, TickMark, TickMark];
    const frame = gridFrame([]);

    expect(tickLines(hour)).toEqual([{ x1: GRID_X, y1: GRID_Y, x2: GRID_X, y2: GRID_Y + GRID_H }]);

    const halfLines = tickLines(half);
    const quarterLines = tickLines(quarter);
    expect(halfLines).toHaveLength(4);
    const length = (line: { y1: number; y2: number }) => line.y2 - line.y1;
    expect(halfLines.every((line, row) => length(line) > length(quarterLines[row] as typeof line))).toBe(true);
    expect(halfLines.every((line) => length(line) < ROW_H)).toBe(true);
    // Rows 1 and 2 hang from their top edge; rows 3 and 4 rise from their bottom edge.
    expect(halfLines.map((line) => line.y1)).toEqual([GRID_Y, GRID_Y + ROW_H, expect.any(Number), expect.any(Number)]);
    expect(halfLines.slice(2).map((line) => line.y2)).toEqual([GRID_Y + 3 * ROW_H, GRID_Y + 4 * ROW_H]);
    expect(frame.grid).toEqual({ x: GRID_X, y: GRID_Y, width: GRID_W, height: GRID_H });
  });
});

describe('tick direction', () => {
  it('hangs row 1 ticks from the top edge and raises row 4 ticks from the bottom edge', () => {
    const half = tickMarks(LIMITS).find((tick) => tick.size === 'half') as TickMark;
    const lines = tickLines(half);
    const row1 = lines[0] as (typeof lines)[number];
    const row4 = lines[3] as (typeof lines)[number];
    const row1Top = GRID_Y;
    const row4Bottom = GRID_Y + GRID_H;

    expect(row1.y1).toBe(row1Top);
    expect(row1.y2).toBeLessThan(row1Top + ROW_H);
    expect(row4.y2).toBe(row4Bottom);
    expect(row4.y1).toBeGreaterThan(row4Bottom - ROW_H);
  });
});

describe('rowLayout and totals', () => {
  it('numbers the row labels as printed and wraps the two long ones', () => {
    expect(rowLayout().map((row) => row.labelLines.map((line) => line.text))).toEqual([
      ['1. Off Duty'],
      ['2. Sleeper', 'Berth'],
      ['3. Driving'],
      ['4. On Duty', '(not driving)'],
    ]);
  });

  it('adds the four daily totals', () => {
    expect(totalHours({ OFF_DUTY: 10, SLEEPER_BERTH: 1.75, DRIVING: 7.75, ON_DUTY_NOT_DRIVING: 4.5 })).toBe(24);
  });
});

describe('remarkLayout', () => {
  it('anchors each label at the end of its leader, rotated to hang down into the band', () => {
    const [remark] = remarkLayout([{ at_min: 540, location: 'Fredericksburg, VA' }], LIMITS);

    expect(remark?.x).toBe(GRID_X + 360);
    expect(remark?.y).toBe(GRID_Y + GRID_H + LEADER_H);
    expect(remark?.leader).toEqual({ x1: GRID_X + 360, y1: GRID_Y + GRID_H, x2: GRID_X + 360, y2: GRID_Y + GRID_H + LEADER_H });
    expect(remark?.transform).toBe(`rotate(-90 ${remark?.x} ${remark?.y})`);
    expect(remark?.text).toBe('Fredericksburg, VA');
    expect(remark?.title).toBeNull();
  });

  it('truncates a long label with an ellipsis and keeps the full text for its title', () => {
    const location = 'US-287 N near Dropoff, CC';
    const [remark] = remarkLayout([{ at_min: 600, location }], LIMITS);

    expect(remark?.text).toBe('US-287 N near Dropoff…');
    expect(remark?.text?.length).toBeLessThanOrEqual(REMARK_MAX_CHARS);
    expect(remark?.title).toBe(location);
  });

  it('puts remarks 15 minutes apart at different depths, and returns to shallow once there is room', () => {
    const layouts = remarkLayout(
      [
        { at_min: 900, location: 'Philadelphia, PA' },
        { at_min: 915, location: 'Camden, NJ' },
        { at_min: 930, location: 'Cherry Hill, NJ' },
        { at_min: 1140, location: 'Newark, NJ' },
      ],
      LIMITS,
    );

    expect(layouts.map((layout) => layout.depth)).toEqual(['shallow', 'deep', 'shallow', 'shallow']);
    expect(layouts[1]?.y).toBe((layouts[0]?.y ?? 0) + REMARK_DEEP_OFFSET);
    expect(layouts[1]?.leader.y2).toBe(layouts[1]?.y);
    // The band grows to hold a deep label only when one exists.
    expect(remarksBandHeight(layouts)).toBe(LEADER_H + 2 * REMARK_DEEP_OFFSET);
    expect(remarksBandHeight(layouts.slice(3))).toBe(LEADER_H + REMARK_DEEP_OFFSET);
  });

  it('keeps a leader but no text for a remark without a location', () => {
    expect(remarkLayout([{ at_min: 60, location: null }], LIMITS)[0]).toMatchObject({ text: null, title: null });
  });
});

describe('gridFrame', () => {
  it('starts the viewBox at the top of the hour band, with no dead space above it', () => {
    const frame = gridFrame([]);

    expect(GRID_Y).toBe(HOUR_BAND_H);
    expect(frame.viewBox.split(' ')[1]).toBe('0');
    expect(frame.hourBand.y).toBe(0);
  });
});

describe('limits drive the grid', () => {
  it('follows a different minutes_per_day instead of a hardcoded 1440', () => {
    const halfDay: RequiredLimits = { ...LIMITS, minutes_per_day: 720 };

    expect(minutesToX(720, halfDay)).toBe(GRID_X + GRID_W);
    expect(minutesToX(720, halfDay)).not.toBe(minutesToX(720, LIMITS));
    expect(tickMarks(halfDay).filter((tick) => tick.size === 'hour')).toHaveLength(13);
    expect(remarkLayout([{ at_min: 360, location: 'Midway' }], halfDay)[0]?.x).toBe(GRID_X + GRID_W / 2);
    expect(buildPolylinePoints([{ status: 'DRIVING', start_min: 0, end_min: 720 }], halfDay)).toBe(
      `${GRID_X},${statusToY('DRIVING')} ${GRID_X + GRID_W},${statusToY('DRIVING')}`,
    );
  });

  it('follows grid_resolution_min', () => {
    const halfHourGrid: RequiredLimits = { ...LIMITS, grid_resolution_min: 30 };

    expect(tickMarks(halfHourGrid)).toHaveLength(49);
    expect(tickMarks(halfHourGrid).filter((tick) => tick.size === 'quarter')).toHaveLength(0);
  });
});
