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
