// Mirrors the API contract in spec §25. Field names are the wire names; nothing here is derived or invented.

/** Duty statuses in paper-form row order, top to bottom. The order is part of the contract. */
export const DUTY_STATUSES = ['OFF_DUTY', 'SLEEPER_BERTH', 'DRIVING', 'ON_DUTY_NOT_DRIVING'] as const;
export type DutyStatus = (typeof DUTY_STATUSES)[number];

export type StopKind = 'START' | 'PICKUP' | 'DROPOFF' | 'FUEL' | 'BREAK' | 'REST' | 'RESTART';

/** Every public integer constant from the backend's constants.py, keyed in lower case, e.g. `minutes_per_day`. */
export type Limits = Record<string, number>;

/** A [lat, lng] pair. */
export type LatLng = [number, number];

// Request (spec §12)

export interface TripPlanRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  /** Hours already used in the 70-hour/8-day cycle, 0 to 70. */
  current_cycle_used: number;
  /** ISO 8601. Defaults to now in `timezone`; rounded down to the 15-minute grid by the server. */
  start_time?: string;
  /** IANA zone of the home terminal. Defaults to America/New_York. */
  timezone?: string;
}

// Response (spec §25)

export interface TripSummary {
  total_miles: number;
  driving_hours: number;
  elapsed_hours: number;
  days: number;
  /** The prior-cycle hours the plan started from. */
  cycle_used_at_start_hours: number;
  /** Every on-duty hour the trip adds. Exact, unlike end minus start, which loses hours rolling off the 8-day window. */
  on_duty_added_hours: number;
  /** The live 8-day cycle at dropoff. */
  cycle_used_at_end: number;
  restart_required: boolean;
}

export interface Route {
  geometry: LatLng[];
  /** [[south, west], [north, east]] */
  bbox: [LatLng, LatLng];
}

export interface Stop {
  kind: StopKind;
  at_mile: number;
  lat: number;
  lng: number;
  label: string;
  /** ISO 8601 in the home terminal zone. */
  arrive: string;
  /** ISO 8601 in the home terminal zone. */
  depart: string;
  duration_hours: number;
}

export interface DayHeader {
  from: string | null;
  to: string | null;
  total_mileage_today: number;
  home_terminal_timezone: string;
  carrier_name: string | null;
  main_office_address: string | null;
  home_terminal_address: string | null;
  vehicle_numbers: string | null;
  driver_name: string | null;
  co_driver: string | null;
  shipping_document: string | null;
}

export interface Segment {
  status: DutyStatus;
  /** Minutes from midnight, 0 to 1440. */
  start_min: number;
  /** Minutes from midnight, 0 to 1440. */
  end_min: number;
}

/** Hours per duty status; the four always sum to 24. */
export type DayTotals = Record<DutyStatus, number>;

export interface Remark {
  /** Minutes from midnight. */
  at_min: number;
  location: string | null;
}

export interface Recap {
  on_duty_today_hours: number;
  a_on_duty_last_7_days_hours: number;
  b_available_tomorrow_hours: number;
  c_on_duty_last_5_days_hours: number;
}

export interface DaySheet {
  /** YYYY-MM-DD */
  date: string;
  date_index: number;
  header: DayHeader;
  segments: Segment[];
  totals: DayTotals;
  total_miles_driving: number;
  remarks: Remark[];
  recap: Recap;
}

export interface TripPlan {
  id: string;
  /** IANA zone of the home terminal, e.g. "America/Chicago". Every time in the plan is in this zone. */
  timezone: string;
  limits: Limits;
  summary: TripSummary;
  route: Route;
  stops: Stop[];
  days: DaySheet[];
  /** Always empty: the planner is violation-free by construction. Present for ELD parity. */
  violations: [];
}

/** GET /api/limits/ */
export interface LimitsResponse {
  limits: Limits;
}

// Error bodies (spec §25). Every error carries `detail`; only request validation adds per-field `errors`.

/** 400 from request validation. */
export interface ValidationErrorBody {
  detail: string;
  errors: Record<string, string[]>;
}

/** 400 from InputError, 404, 422, 429, 500 and 502. */
export interface DetailErrorBody {
  detail: string;
  errors?: undefined;
}

export type ApiErrorBody = ValidationErrorBody | DetailErrorBody;
