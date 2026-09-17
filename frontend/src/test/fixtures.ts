import johnDoeDay from '../components/__tests__/johnDoeDay.json';
import { parseLimits } from '../lib/limits';
import type { DaySheet, Limits } from '../types';

/** The limits object exactly as the API returns it (spec §25). */
export const API_LIMITS: Limits = {
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

export const LIMITS = parseLimits(API_LIMITS);

/** Page 18 of the FMCSA guide, serialized by the backend's own DaySerializer. */
export const JOHN_DOE_DAY = johnDoeDay as DaySheet;
