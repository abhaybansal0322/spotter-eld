// The 70-hour cycle meter's model: every figure the component shows, already computed.

import type { Stop, TripSummary } from '../types';
import type { RequiredLimits } from './limits';

export interface CycleSegment {
  key: 'prior' | 'trip' | 'remaining';
  hours: number;
  /** CSS width of the segment within the bar. */
  width: string;
}

export interface CycleMeterModel {
  limitHours: number;
  priorHours: number;
  tripHours: number;
  remainingHours: number;
  endHours: number;
  segments: CycleSegment[];
  /** CSS left offset of the limit marker. It sits at the bar's end unless the trip ran past the limit. */
  limitMarkerLeft: string;
  restart: Stop | null;
}

function percent(part: number, whole: number): string {
  return `${whole > 0 ? (part / whole) * 100 : 0}%`;
}

/**
 * startHours is the cycle the driver submitted. Without a restart, the trip added the difference to the end figure.
 * A 34-hour restart resets the cycle, so everything at the end was worked after it and none of the prior hours remain.
 * On-duty work past the limit is legal (only driving is not), so the bar rescales rather than overflowing.
 */
export function cycleMeterModel(limits: RequiredLimits, summary: TripSummary, startHours: number, stops: Stop[]): CycleMeterModel {
  const limitHours = limits.cycle_limit_min / limits.minutes_per_hour;
  const endHours = summary.cycle_used_at_end;
  const priorHours = summary.restart_required ? 0 : Math.min(startHours, endHours);
  const tripHours = Math.max(0, endHours - priorHours);
  const remainingHours = Math.max(0, limitHours - endHours);
  const scale = Math.max(limitHours, priorHours + tripHours);

  return {
    limitHours,
    priorHours,
    tripHours,
    remainingHours,
    endHours,
    segments: [
      { key: 'prior', hours: priorHours, width: percent(priorHours, scale) },
      { key: 'trip', hours: tripHours, width: percent(tripHours, scale) },
      { key: 'remaining', hours: remainingHours, width: percent(remainingHours, scale) },
    ],
    limitMarkerLeft: percent(limitHours, scale),
    restart: stops.find((stop) => stop.kind === 'RESTART') ?? null,
  };
}
