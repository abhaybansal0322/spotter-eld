// Pure geometry for the paper log grid (spec §13). No React. Every time-based number comes from RequiredLimits;
// the only numbers written here are pixel layout. LogGrid.tsx renders these values without doing any arithmetic.

import { DUTY_STATUSES, type DayTotals, type DutyStatus, type Segment } from '../types';
import type { RequiredLimits } from './limits';

// Spec §13 grid placement.
export const GRID_X = 60;
export const GRID_W = 960; // 40 px per hour, 10 px per 15 minutes on a 24-hour day
export const GRID_Y = 200;
export const ROW_H = 30;
export const GRID_H = ROW_H * DUTY_STATUSES.length;

// Surroundings, measured against blank-paper-log.png.
export const LABEL_W = 130; // row labels left of the grid
export const HOUR_BAND_H = 34; // solid black band carrying the hour labels
export const TOTALS_W = 90; // "Total Hours" column right of the grid
export const LEADER_H = 12; // leader line from the grid's bottom edge down to a remark label
export const REMARKS_H = 150; // band beneath the grid holding the rotated remark labels
export const DUTY_LINE_WIDTH = 3;

const HALF_TICK = ROW_H * 0.55;
const QUARTER_TICK = ROW_H * 0.3;
const LABEL_LINE_H = 13;
const HOUR_LABEL_BASELINE = GRID_Y - 6;
const TOTALS_RULE_INSET = 12;

// Rows 1 and 2 hang their half and quarter ticks from the row's top edge; rows 3 and 4 raise them from the bottom.
const TICKS_HANG_FROM_TOP: Record<DutyStatus, boolean> = {
  OFF_DUTY: true,
  SLEEPER_BERTH: true,
  DRIVING: false,
  ON_DUTY_NOT_DRIVING: false,
};

const ROW_LABELS: Record<DutyStatus, readonly string[]> = {
  OFF_DUTY: ['Off Duty'],
  SLEEPER_BERTH: ['Sleeper', 'Berth'],
  DRIVING: ['Driving'],
  ON_DUTY_NOT_DRIVING: ['On Duty', '(not driving)'],
};

export type TickSize = 'hour' | 'half' | 'quarter';

export interface TickMark {
  x: number;
  size: TickSize;
  label?: string;
}

export interface Line {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface TextLine {
  text: string;
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GridFrame {
  viewBox: string;
  width: number;
  height: number;
  grid: Rect;
  hourBand: Rect;
  remarksHeading: TextLine;
}

export interface RowLayout {
  status: DutyStatus;
  labelLines: TextLine[];
  /** The rule along the row's bottom edge. */
  rule: Line;
  total: { x: number; y: number; rule: Line };
}

export interface TotalsColumn {
  heading: TextLine[];
  sum: { x: number; y: number; rule: Line };
}

export interface HourLabel {
  lines: TextLine[];
  anchor: 'start' | 'middle' | 'end';
}

export interface RemarkAnchor {
  x: number;
  y: number;
  transform: string;
}

export function minutesToX(min: number, limits: RequiredLimits): number {
  return GRID_X + (min * GRID_W) / limits.minutes_per_day;
}

/** Vertical centre of a status row. Rows follow the contract's order: off duty, sleeper, driving, on duty. */
export function statusToY(status: DutyStatus): number {
  return rowTop(status) + ROW_H / 2;
}

function rowTop(status: DutyStatus): number {
  return GRID_Y + DUTY_STATUSES.indexOf(status) * ROW_H;
}

/**
 * Points for one continuous <polyline> covering the day. Each segment adds its horizontal run; where the status
 * changes, the run starts at the previous run's end x on the new row, so consecutive points draw the vertical
 * connector. The pen never leaves the paper.
 */
export function buildPolylinePoints(segments: Segment[], limits: RequiredLimits): string {
  const points: string[] = [];
  let previousY: number | undefined;
  for (const segment of segments) {
    const y = statusToY(segment.status);
    if (y !== previousY) {
      points.push(`${minutesToX(segment.start_min, limits)},${y}`);
    }
    points.push(`${minutesToX(segment.end_min, limits)},${y}`);
    previousY = y;
  }
  return points.join(' ');
}

/** One tick per grid step across the day, sized as printed: hour tallest and labelled, then half, then quarter. */
export function tickMarks(limits: RequiredLimits): TickMark[] {
  const { minutes_per_day: minutesPerDay, minutes_per_hour: minutesPerHour, grid_resolution_min: step } = limits;
  const hoursPerDay = minutesPerDay / minutesPerHour;

  const ticks: TickMark[] = [];
  for (let minute = 0; minute <= minutesPerDay; minute += step) {
    const x = minutesToX(minute, limits);
    if (minute % minutesPerHour === 0) {
      ticks.push({ x, size: 'hour', label: hourLabel(minute / minutesPerHour, hoursPerDay) });
    } else if (minute % (minutesPerHour / 2) === 0) {
      ticks.push({ x, size: 'half' });
    } else {
      ticks.push({ x, size: 'quarter' });
    }
  }
  return ticks;
}

function hourLabel(hour: number, hoursPerDay: number): string {
  if (hour % hoursPerDay === 0) {
    return 'Midnight';
  }
  if (hour === hoursPerDay / 2) {
    return 'Noon';
  }
  return String(hour % (hoursPerDay / 2));
}

/** The strokes for one tick: an hour is a full-height rule; half and quarter ticks repeat in every row. */
export function tickLines(tick: TickMark): Line[] {
  if (tick.size === 'hour') {
    return [{ x1: tick.x, y1: GRID_Y, x2: tick.x, y2: GRID_Y + GRID_H }];
  }
  const length = tick.size === 'half' ? HALF_TICK : QUARTER_TICK;
  return DUTY_STATUSES.map((status) => {
    const top = rowTop(status);
    const bottom = top + ROW_H;
    return TICKS_HANG_FROM_TOP[status]
      ? { x1: tick.x, y1: top, x2: tick.x, y2: top + length }
      : { x1: tick.x, y1: bottom - length, x2: tick.x, y2: bottom };
  });
}

/** Hour label text in the black band. Midnight is printed as "Mid-" over "night", flush with the grid's edges. */
export function hourLabelLayout(tick: TickMark): HourLabel {
  if (tick.label !== 'Midnight') {
    return { lines: [{ text: tick.label ?? '', x: tick.x, y: HOUR_LABEL_BASELINE }], anchor: 'middle' };
  }
  const anchor = tick.x === GRID_X ? 'start' : 'end';
  return {
    anchor,
    lines: [
      { text: 'Mid-', x: tick.x, y: HOUR_LABEL_BASELINE - LABEL_LINE_H },
      { text: 'night', x: tick.x, y: HOUR_LABEL_BASELINE },
    ],
  };
}

export function gridFrame(): GridFrame {
  const x = GRID_X - LABEL_W;
  const y = GRID_Y - HOUR_BAND_H;
  const width = LABEL_W + GRID_W + TOTALS_W;
  const height = HOUR_BAND_H + GRID_H + REMARKS_H;
  return {
    viewBox: `${x} ${y} ${width} ${height}`,
    width,
    height,
    grid: { x: GRID_X, y: GRID_Y, width: GRID_W, height: GRID_H },
    hourBand: { x: GRID_X, y, width: GRID_W + TOTALS_W, height: HOUR_BAND_H },
    remarksHeading: { text: 'Remarks', x, y: GRID_Y + GRID_H + LEADER_H + LABEL_LINE_H },
  };
}

/** Row labels ("1. Off Duty", two lines where the form wraps), the row's bottom rule, and its totals slot. */
export function rowLayout(): RowLayout[] {
  const labelX = GRID_X - LABEL_W;
  const totalX = GRID_X + GRID_W + TOTALS_W / 2;
  return DUTY_STATUSES.map((status, index) => {
    const top = rowTop(status);
    const bottom = top + ROW_H;
    const [first = '', ...rest] = ROW_LABELS[status];
    const lines = [`${index + 1}. ${first}`, ...rest];
    const firstBaseline = statusToY(status) + LABEL_LINE_H / 3 - ((lines.length - 1) * LABEL_LINE_H) / 2;
    return {
      status,
      labelLines: lines.map((text, line) => ({ text, x: labelX, y: firstBaseline + line * LABEL_LINE_H })),
      rule: { x1: GRID_X, y1: bottom, x2: GRID_X + GRID_W, y2: bottom },
      total: {
        x: totalX,
        y: bottom - 4,
        rule: { x1: GRID_X + GRID_W + TOTALS_RULE_INSET, y1: bottom, x2: GRID_X + GRID_W + TOTALS_W, y2: bottom },
      },
    };
  });
}

/** "Total Hours" heading in the band, and the summed figure below the last row, over a double rule on the form. */
export function totalsColumn(): TotalsColumn {
  const x = GRID_X + GRID_W + TOTALS_W / 2;
  const sumBaseline = GRID_Y + GRID_H + ROW_H - 8;
  return {
    heading: [
      { text: 'Total', x, y: HOUR_LABEL_BASELINE - LABEL_LINE_H },
      { text: 'Hours', x, y: HOUR_LABEL_BASELINE },
    ],
    sum: {
      x,
      y: sumBaseline,
      rule: { x1: GRID_X + GRID_W + TOTALS_RULE_INSET, y1: sumBaseline + 4, x2: GRID_X + GRID_W + TOTALS_W, y2: sumBaseline + 4 },
    },
  };
}

/** The four daily totals added up; always 24 hours on a valid sheet. */
export function totalHours(totals: DayTotals): number {
  return DUTY_STATUSES.reduce((sum, status) => sum + totals[status], 0);
}

/** Anchor for a remark's rotated label, just below its leader line. Draw with text-anchor="end" so the text
 * hangs down into the remarks band, reading bottom to top, with its last letter at the leader. */
export function remarkAnchor(atMin: number, limits: RequiredLimits): RemarkAnchor {
  const x = minutesToX(atMin, limits);
  const y = GRID_Y + GRID_H + LEADER_H;
  return { x, y, transform: `rotate(-90 ${x} ${y})` };
}

/** Thin leader from a remark's minute on the grid's bottom edge down to its label. */
export function remarkLeader(atMin: number, limits: RequiredLimits): Line {
  const x = minutesToX(atMin, limits);
  return { x1: x, y1: GRID_Y + GRID_H, x2: x, y2: GRID_Y + GRID_H + LEADER_H };
}
