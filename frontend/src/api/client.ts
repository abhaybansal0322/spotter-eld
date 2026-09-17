import axios, { AxiosError } from 'axios';

import type { ApiErrorBody, Limits, LimitsResponse, TripPlan, TripPlanRequest } from '../types';

/** What every failed request rejects with, whatever went wrong. */
export interface ApiError {
  message: string;
  fieldErrors?: Record<string, string[]>;
}

// Generous on purpose: a sleeping Render instance takes 30 to 60 seconds to wake, and a plan can then spend up to
// about 25 seconds on routing retries. A shorter timeout would report a slow start as a failure.
export const REQUEST_TIMEOUT_MS = 90_000;

const MESSAGES = {
  cancelled: 'The request was cancelled.',
  timeout: 'The server took too long to respond. It may be waking up; please try again in a moment.',
  network: 'Could not reach the server. Check your connection and try again.',
  throttled: 'Too many trip plans in a short time. Please wait a minute and try again.',
  unavailable: 'The server is starting up or unavailable. Please try again in a moment.',
  server: 'Something went wrong on the server. Please try again.',
  unexpected: 'Something unexpected went wrong. Please try again.',
} as const;

/** The one configured HTTP client. Components use the hook, never this or axios directly. */
export const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
);

export async function planTrip(request: TripPlanRequest, signal?: AbortSignal): Promise<TripPlan> {
  const response = await client.post<TripPlan>('/api/trips/plan/', request, { signal });
  return response.data;
}

export async function getTrip(id: string, signal?: AbortSignal): Promise<TripPlan> {
  const response = await client.get<TripPlan>(`/api/trips/${encodeURIComponent(id)}/`, { signal });
  return response.data;
}

export async function getLimits(signal?: AbortSignal): Promise<Limits> {
  const response = await client.get<LimitsResponse>('/api/limits/', { signal });
  return response.data.limits;
}

/** Normalise any failure into `{ message, fieldErrors? }`, reading the API's `detail` and optional `errors`. */
export function toApiError(error: unknown): ApiError {
  if (!axios.isAxiosError(error)) {
    return { message: MESSAGES.unexpected };
  }
  if (error.code === AxiosError.ERR_CANCELED) {
    return { message: MESSAGES.cancelled };
  }
  if (error.code === AxiosError.ECONNABORTED || error.code === AxiosError.ETIMEDOUT) {
    return { message: MESSAGES.timeout };
  }
  if (!error.response) {
    return { message: MESSAGES.network };
  }

  const body: unknown = error.response.data;
  if (isApiErrorBody(body)) {
    const fieldErrors = body.errors && toFieldErrors(body.errors);
    return fieldErrors ? { message: body.detail, fieldErrors } : { message: body.detail };
  }
  return { message: messageForStatus(error.response.status) };
}

function isApiErrorBody(body: unknown): body is ApiErrorBody {
  return typeof body === 'object' && body !== null && typeof (body as { detail?: unknown }).detail === 'string';
}

/** Keep only well-formed `field: string[]` entries; anything else is dropped rather than trusted. */
function toFieldErrors(errors: unknown): Record<string, string[]> | undefined {
  if (typeof errors !== 'object' || errors === null) {
    return undefined;
  }
  const entries = Object.entries(errors).flatMap(([field, messages]) =>
    Array.isArray(messages) ? [[field, messages.map(String)] as const] : [],
  );
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}

function messageForStatus(status: number): string {
  if (status === 429) {
    return MESSAGES.throttled;
  }
  if (status === 502 || status === 503 || status === 504) {
    return MESSAGES.unavailable;
  }
  if (status >= 500) {
    return MESSAGES.server;
  }
  return `The request failed (HTTP ${status}).`;
}
