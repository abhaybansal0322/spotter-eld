// The 70-hour cycle meter's model: every figure the component shows, already computed from the plan alone.

import type { Stop, TripSummary } from '../types';
import type { RequiredLimits } from './limits';

export type CycleKey = 'prior' | 'trip' | 'remaining';

export interface CycleSegment {
  key: CycleKey;
  /** Hours this segment of the bar stands for. */
  hours: number;
  /** CSS width of the segment within the bar. */
  width: string;
}

export interface CycleMeterModel {
  limitHours: number;
  cycleDays: number;
  endHours: number;
  /** The legend's exact figures from the summary: hours before the trip, hours the trip added, hours left at dropoff. */
  legend: Record<CycleKey, number>;
  /** The bar: the live cycle at dropoff, split into what still counts from before the trip and from the trip. */
  segments: CycleSegment[];
  /** Hours that left the live cycle before dropoff, through a restart or the rolling window. Zero on most trips. */
  shedHours: number;
  /** CSS left offset of the limit marker. It sits at the bar's end unless on-duty work ran past the limit. */
  limitMarkerLeft: string;
  restart: Stop | null;
}

function percent(part: number, whole: number): string {
  return `${whole > 0 ? (part / whole) * 100 : 0}%`;
}

/**
 * Built from the summary, never the submitted request, so a plan reopened by id draws the same meter.
 * start + added equals the end figure unless hours left the cycle before dropoff. A restart flattens the cycle, and the
 * prior-hours lump rolls off whole, so whatever survives at the end is the trip's own work first and prior hours second.
 * On-duty work past the limit is legal (only driving is not), so the bar rescales rather than overflowing.
 */
export function cycleMeterModel(limits: RequiredLimits, summary: TripSummary, stops: Stop[]): CycleMeterModel {
  const limitHours = limits.cycle_limit_min / limits.minutes_per_hour;
  const {
    cycle_used_at_start_hours: startHours,
    on_duty_added_hours: addedHours,
    cycle_used_at_end: endHours,
  } = summary;
  const priorCounted = Math.min(startHours, Math.max(0, endHours - addedHours));
  const tripCounted = endHours - priorCounted;
  const remainingHours = Math.max(0, limitHours - endHours);
  const scale = Math.max(limitHours, endHours);

  return {
    limitHours,
    cycleDays: limits.cycle_days,
    endHours,
    legend: { prior: startHours, trip: addedHours, remaining: remainingHours },
    segments: [
      { key: 'prior', hours: priorCounted, width: percent(priorCounted, scale) },
      { key: 'trip', hours: tripCounted, width: percent(tripCounted, scale) },
      { key: 'remaining', hours: remainingHours, width: percent(remainingHours, scale) },
    ],
    shedHours: Math.max(0, startHours + addedHours - endHours),
    limitMarkerLeft: percent(limitHours, scale),
    restart: stops.find((stop) => stop.kind === 'RESTART') ?? null,
  };
}
