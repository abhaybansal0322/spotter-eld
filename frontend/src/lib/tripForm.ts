// Trip form rules: the same checks the server makes, so an obvious mistake doesn't cost a round trip.
// The server stays authoritative; its field errors replace these after every submission.

import type { TripPlanRequest } from '../types';

export interface TripFormValues {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  /** Kept as typed, so a half-entered number is not coerced away. */
  current_cycle_used: string;
  /** datetime-local value in the home terminal zone; empty means start now. */
  start_time: string;
  timezone: string;
}

export type FieldErrors = Record<string, string[]>;

export const DEFAULT_TIMEZONE = 'America/New_York';

export const HOME_TERMINAL_ZONES: readonly { value: string; label: string }[] = [
  { value: 'America/New_York', label: 'Eastern (America/New_York)' },
  { value: 'America/Chicago', label: 'Central (America/Chicago)' },
  { value: 'America/Denver', label: 'Mountain (America/Denver)' },
  { value: 'America/Phoenix', label: 'Mountain, no DST (America/Phoenix)' },
  { value: 'America/Los_Angeles', label: 'Pacific (America/Los_Angeles)' },
  { value: 'America/Anchorage', label: 'Alaska (America/Anchorage)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii (Pacific/Honolulu)' },
];

export const EMPTY_TRIP_FORM: TripFormValues = {
  current_location: '',
  pickup_location: '',
  dropoff_location: '',
  current_cycle_used: '0',
  start_time: '',
  timezone: DEFAULT_TIMEZONE,
};

function normalize(address: string): string {
  return address.trim().toLowerCase().split(/\s+/).join(' ');
}

export function parseCycleHours(text: string): number | null {
  if (text.trim() === '') {
    return null;
  }
  const hours = Number(text);
  return Number.isFinite(hours) ? hours : null;
}

/** Hours left in the cycle for what has been typed, or null while the field isn't a number. */
export function remainingCycleHours(text: string, limitHours: number): number | null {
  const used = parseCycleHours(text);
  return used === null ? null : Math.max(0, limitHours - used);
}

/** limitHours is null when the limits could not be fetched; the upper bound is then left to the server. */
export function validateTripForm(values: TripFormValues, limitHours: number | null): FieldErrors {
  const errors: FieldErrors = {};
  const require = (field: keyof TripFormValues, label: string) => {
    if (values[field].trim() === '') {
      errors[field] = [`Enter the ${label}.`];
    }
  };
  require('current_location', 'current location');
  require('pickup_location', 'pickup location');
  require('dropoff_location', 'dropoff location');

  const used = parseCycleHours(values.current_cycle_used);
  if (used === null) {
    errors.current_cycle_used = ['Enter the hours already used, as a number.'];
  } else if (used < 0) {
    errors.current_cycle_used = ['Hours used cannot be negative.'];
  } else if (limitHours !== null && used > limitHours) {
    errors.current_cycle_used = [`Hours used must be between 0 and ${limitHours}.`];
  }

  if (!errors.pickup_location && !errors.dropoff_location && normalize(values.pickup_location) === normalize(values.dropoff_location)) {
    errors.dropoff_location = ['Pickup and dropoff must be different locations.'];
  }
  return errors;
}

export function toTripPlanRequest(values: TripFormValues): TripPlanRequest {
  const request: TripPlanRequest = {
    current_location: values.current_location.trim(),
    pickup_location: values.pickup_location.trim(),
    dropoff_location: values.dropoff_location.trim(),
    current_cycle_used: parseCycleHours(values.current_cycle_used) ?? 0,
    timezone: values.timezone,
  };
  if (values.start_time !== '') {
    request.start_time = values.start_time;
  }
  return request;
}
