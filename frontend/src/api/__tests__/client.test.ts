import { AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, describe, expect, it } from 'vitest';

import type { TripPlanRequest } from '../../types';
import { client, getTrip, planTrip, toApiError } from '../client';

const REQUEST: TripPlanRequest = {
  current_location: 'Richmond, VA',
  pickup_location: 'Baltimore, MD',
  dropoff_location: 'Newark, NJ',
  current_cycle_used: 12.5,
};

const originalAdapter = client.defaults.adapter;

afterEach(() => {
  client.defaults.adapter = originalAdapter;
});

/** Swap the transport so requests go through the real instance and its interceptor without a network. */
function respondWith(adapter: AxiosAdapter) {
  client.defaults.adapter = adapter;
}

function httpError(status: number, data: unknown): AxiosAdapter {
  return (config: InternalAxiosRequestConfig) =>
    Promise.reject(
      new AxiosError(`HTTP ${status}`, AxiosError.ERR_BAD_RESPONSE, config, {}, {
        data,
        status,
        statusText: '',
        headers: new AxiosHeaders(),
        config,
      }),
    );
}

describe('response interceptor', () => {
  it('flattens a validation body into message and field errors', async () => {
    respondWith(
      httpError(400, {
        detail: 'Current cycle used: Ensure this value is less than or equal to 70.',
        errors: { current_cycle_used: ['Ensure this value is less than or equal to 70.'] },
      }),
    );

    await expect(planTrip(REQUEST)).rejects.toEqual({
      message: 'Current cycle used: Ensure this value is less than or equal to 70.',
      fieldErrors: { current_cycle_used: ['Ensure this value is less than or equal to 70.'] },
    });
  });

  it('flattens a detail-only body into a message with no field errors', async () => {
    respondWith(httpError(422, { detail: 'No truck-accessible road was found near the dropoff location (Newark, NJ).' }));

    const error = await planTrip(REQUEST).catch((reason: unknown) => reason);

    expect(error).toEqual({ message: 'No truck-accessible road was found near the dropoff location (Newark, NJ).' });
    expect(error).not.toHaveProperty('fieldErrors');
  });

  it('gives a network failure a readable message', async () => {
    respondWith((config) => Promise.reject(new AxiosError('Network Error', AxiosError.ERR_NETWORK, config, {})));

    await expect(getTrip('3f2b8c1e-7d4a-4e21-9b6f-2a1c5e8d9f00')).rejects.toEqual({
      message: 'Could not reach the server. Check your connection and try again.',
    });
  });

  it('gives a timeout a message that mentions a waking server', async () => {
    respondWith((config) => Promise.reject(new AxiosError('timeout of 90000ms exceeded', AxiosError.ECONNABORTED, config, {})));

    const error = await planTrip(REQUEST).catch((reason: unknown) => reason);

    expect(error).toEqual({ message: expect.stringContaining('waking up') });
  });

  it('falls back to a status message when the body is not the API shape', async () => {
    respondWith(httpError(502, '<html><body>Bad Gateway</body></html>'));

    await expect(planTrip(REQUEST)).rejects.toEqual({
      message: 'The server is starting up or unavailable. Please try again in a moment.',
    });
  });

  it('uses the throttle message for a 429 without a body', async () => {
    respondWith(httpError(429, undefined));

    await expect(planTrip(REQUEST)).rejects.toEqual({
      message: 'Too many trip plans in a short time. Please wait a minute and try again.',
    });
  });
});

describe('toApiError', () => {
  it('drops malformed field errors rather than trusting them', () => {
    const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
    const error = new AxiosError('HTTP 400', AxiosError.ERR_BAD_REQUEST, config, {}, {
      data: { detail: 'Bad request.', errors: { start_time: 'not a list', timezone: ['Unknown timezone.'] } },
      status: 400,
      statusText: '',
      headers: new AxiosHeaders(),
      config,
    });

    expect(toApiError(error)).toEqual({ message: 'Bad request.', fieldErrors: { timezone: ['Unknown timezone.'] } });
  });

  it('handles errors that did not come from axios', () => {
    expect(toApiError(new TypeError('boom'))).toEqual({ message: 'Something unexpected went wrong. Please try again.' });
  });
});

describe('requests', () => {
  it('posts the plan request and resolves with the payload', async () => {
    let seen: InternalAxiosRequestConfig | undefined;
    respondWith(async (config) => {
      seen = config;
      return { data: { id: 'abc' }, status: 201, statusText: 'Created', headers: new AxiosHeaders(), config };
    });

    await expect(planTrip(REQUEST)).resolves.toEqual({ id: 'abc' });
    expect(seen?.method).toBe('post');
    expect(seen?.url).toBe('/api/trips/plan/');
    expect(JSON.parse(seen?.data as string)).toEqual(REQUEST);
  });

  it('encodes the trip id into the detail path', async () => {
    let seen: InternalAxiosRequestConfig | undefined;
    respondWith(async (config) => {
      seen = config;
      return { data: {}, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config };
    });

    await getTrip('a/b');

    expect(seen?.url).toBe('/api/trips/a%2Fb/');
  });
});
