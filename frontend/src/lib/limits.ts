// Narrows the API's open limits record to the keys the frontend draws with (spec §26). Called once, at the boundary.

import type { Limits } from '../types';

export interface RequiredLimits {
  minutes_per_day: number;
  minutes_per_hour: number;
  grid_resolution_min: number;
  cycle_limit_min: number;
  drive_limit_min: number;
  window_limit_min: number;
  break_after_drive_min: number;
  break_duration_min: number;
  qualifying_rest_min: number;
  cycle_days: number;
}

const REQUIRED_KEYS = [
  'minutes_per_day',
  'minutes_per_hour',
  'grid_resolution_min',
  'cycle_limit_min',
  'drive_limit_min',
  'window_limit_min',
  'break_after_drive_min',
  'break_duration_min',
  'qualifying_rest_min',
  'cycle_days',
] as const satisfies readonly (keyof RequiredLimits)[];

export class InvalidLimitsError extends Error {
  constructor(key: string, problem: string) {
    super(`The server sent an incomplete trip plan: limit "${key}" ${problem}. Please try again.`);
    this.name = 'InvalidLimitsError';
  }
}

/** Returns only the required limits, each a positive finite number, or throws InvalidLimitsError naming the key. */
export function parseLimits(limits: Limits): RequiredLimits {
  const entries = REQUIRED_KEYS.map((key) => {
    const value: unknown = limits[key];
    if (value === undefined) {
      throw new InvalidLimitsError(key, 'is missing');
    }
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
      throw new InvalidLimitsError(key, `must be a positive number, got ${JSON.stringify(value)}`);
    }
    return [key, value] as const;
  });
  return Object.fromEntries(entries) as unknown as RequiredLimits;
}
