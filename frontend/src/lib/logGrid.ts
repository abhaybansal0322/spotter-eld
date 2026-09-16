// Pure coordinate math for the paper log grid (spec §13). No React. Every time-based number comes from the API's
// limits object, so the grid follows the backend's constants rather than repeating them. Only pixel layout lives here.

import { DUTY_STATUSES, type DutyStatus, type Limits, type Segment } from '../types';

export const GRID_X = 60;
export const GRID_W = 960; // 40 px per hour, 10 px per 15 minutes on a 24-hour day
export const GRID_Y = 200;
export const ROW_H = 30;
export const GRID_H = ROW_H * DUTY_STATUSES.length;
export const REMARKS_H = 110; // band beneath the grid; rotated remark labels rise from its bottom edge

export interface TickMark {
  x: number;
  major: boolean;
  label?: string;
}

export interface RemarkAnchor {
  x: number;
  y: number;
  transform: string;
}

function limit(limits: Limits, name: string): number {
  const value = limits[name];
  if (value === undefined || !Number.isFinite(value) || value <= 0) {
    throw new Error(`limits.${name} must be a positive number`);
  }
  return value;
}

export function minutesToX(min: number, limits: Limits): number {
  return GRID_X + (min * GRID_W) / limit(limits, 'minutes_per_day');
}

/** Vertical centre of a status row. Rows follow the contract's order: off duty, sleeper, driving, on duty. */
export function statusToY(status: DutyStatus): number {
  return GRID_Y + DUTY_STATUSES.indexOf(status) * ROW_H + ROW_H / 2;
}

/**
 * Points for one continuous <polyline> covering the day. Each segment adds its horizontal run; where the status
 * changes, the run starts at the previous run's end x on the new row, so consecutive points draw the vertical
 * connector. The pen never leaves the paper.
 */
export function buildPolylinePoints(segments: Segment[], limits: Limits): string {
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

/** A tick at every grid step across the day. Hour ticks are major and labelled as on the form. */
export function tickMarks(limits: Limits): TickMark[] {
  const minutesPerDay = limit(limits, 'minutes_per_day');
  const minutesPerHour = limit(limits, 'minutes_per_hour');
  const step = limit(limits, 'grid_resolution_min');
  const hoursPerDay = minutesPerDay / minutesPerHour;

  const ticks: TickMark[] = [];
  for (let minute = 0; minute <= minutesPerDay; minute += step) {
    const x = minutesToX(minute, limits);
    if (minute % minutesPerHour === 0) {
      ticks.push({ x, major: true, label: hourLabel(minute / minutesPerHour, hoursPerDay) });
    } else {
      ticks.push({ x, major: false });
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

/** Where a remark's rotated label is drawn: at its minute's x, rising from the bottom of the remarks band. */
export function remarkAnchor(atMin: number, limits: Limits): RemarkAnchor {
  const x = minutesToX(atMin, limits);
  const y = GRID_Y + GRID_H + REMARKS_H;
  return { x, y, transform: `rotate(-90 ${x} ${y})` };
}
