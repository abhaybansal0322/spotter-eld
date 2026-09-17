// How each stop kind is shown. One duty-status colour per kind, used by the map markers, legend and timeline (spec §27).

import type { DutyStatus, Stop, StopKind } from '../types';

export const STOP_KINDS: readonly StopKind[] = ['START', 'PICKUP', 'FUEL', 'BREAK', 'REST', 'RESTART', 'DROPOFF'];

/** The duty status a stop is logged under. START has none: it is a place, not time. */
export const KIND_STATUS: Record<StopKind, DutyStatus | null> = {
  START: null,
  PICKUP: 'ON_DUTY_NOT_DRIVING',
  DROPOFF: 'ON_DUTY_NOT_DRIVING',
  FUEL: 'ON_DUTY_NOT_DRIVING',
  BREAK: 'OFF_DUTY',
  REST: 'SLEEPER_BERTH',
  RESTART: 'OFF_DUTY',
};

export const KIND_LABEL: Record<StopKind, string> = {
  START: 'Start',
  PICKUP: 'Pickup',
  DROPOFF: 'Dropoff',
  FUEL: 'Fuel',
  BREAK: 'Break',
  REST: 'Rest',
  RESTART: 'Restart',
};

/** One character drawn inside the map marker, so kinds sharing a duty colour stay distinguishable. */
export const KIND_GLYPH: Record<StopKind, string> = {
  START: 'S',
  PICKUP: 'P',
  DROPOFF: 'D',
  FUEL: 'F',
  BREAK: 'B',
  REST: 'R',
  RESTART: 'X',
};

export const STATUS_LABEL: Record<DutyStatus, string> = {
  OFF_DUTY: 'Off duty',
  SLEEPER_BERTH: 'Sleeper berth',
  DRIVING: 'Driving',
  ON_DUTY_NOT_DRIVING: 'On duty, not driving',
};

/** The kinds that occur in a trip, in legend order. */
export function kindsPresent(stops: Stop[]): StopKind[] {
  const present = new Set(stops.map((stop) => stop.kind));
  return STOP_KINDS.filter((kind) => present.has(kind));
}

export interface PixelPoint {
  x: number;
  y: number;
}

export interface PixelOffset {
  dx: number;
  dy: number;
}

/**
 * Screen offsets that keep every pin clickable. Points closer than thresholdPx to the first point of a group join it,
 * and a group of two or more fans out on a circle of radiusPx, starting straight up. Lone points stay put.
 * Groups are anchored on their first member, not chained, which is plenty for a trip's dozen or so stops.
 */
export function spreadOverlapping(points: PixelPoint[], thresholdPx: number, radiusPx: number): PixelOffset[] {
  const groups: number[][] = [];
  const groupOf = points.map((point, index) => {
    const group = groups.find((members) => {
      const anchor = points[members[0] ?? index] ?? point;
      return Math.hypot(anchor.x - point.x, anchor.y - point.y) < thresholdPx;
    });
    if (group) {
      group.push(index);
      return group;
    }
    const created = [index];
    groups.push(created);
    return created;
  });

  return points.map((_, index) => {
    const group = groupOf[index] ?? [index];
    if (group.length < 2) {
      return { dx: 0, dy: 0 };
    }
    const angle = (2 * Math.PI * group.indexOf(index)) / group.length - Math.PI / 2;
    return { dx: Math.round(radiusPx * Math.cos(angle)), dy: Math.round(radiusPx * Math.sin(angle)) };
  });
}
