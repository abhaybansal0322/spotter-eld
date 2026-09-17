import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_LIMITS, LIMITS } from '../../test/fixtures';
import type { TripPlan, TripPlanRequest } from '../../types';
import { useTripPlan } from '../useTripPlan';

vi.mock('../../api/client', () => ({ planTrip: vi.fn() }));
const { planTrip } = await import('../../api/client');
const planTripMock = vi.mocked(planTrip);

const REQUEST: TripPlanRequest = {
  current_location: 'Richmond, VA',
  pickup_location: 'Baltimore, MD',
  dropoff_location: 'Newark, NJ',
  current_cycle_used: 0,
};

function plan(id: string, limits = API_LIMITS): TripPlan {
  return { id, limits } as TripPlan;
}

/** A planTrip call the test resolves or rejects by hand, exposing the signal the hook passed in. */
function deferred() {
  let resolve!: (value: TripPlan) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<TripPlan>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  planTripMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useTripPlan', () => {
  it('moves from loading to success with narrowed limits', async () => {
    planTripMock.mockResolvedValue(plan('only'));
    const { result } = renderHook(() => useTripPlan());

    expect(result.current.state).toEqual({ status: 'idle' });
    await act(() => result.current.plan(REQUEST));

    expect(result.current.state).toEqual({ status: 'success', data: plan('only'), limits: LIMITS });
  });

  it('never lets a superseded request overwrite newer state', async () => {
    const first = deferred();
    const second = deferred();
    planTripMock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useTripPlan());

    let firstDone!: Promise<void>;
    let secondDone!: Promise<void>;
    act(() => {
      firstDone = result.current.plan(REQUEST);
    });
    act(() => {
      secondDone = result.current.plan({ ...REQUEST, dropoff_location: 'Trenton, NJ' });
    });
    const firstSignal = planTripMock.mock.calls[0]?.[1];
    expect(firstSignal?.aborted).toBe(true);

    await act(async () => {
      second.resolve(plan('newer'));
      await secondDone;
    });
    await act(async () => {
      first.resolve(plan('stale'));
      await firstDone;
    });

    expect(result.current.state).toMatchObject({ status: 'success', data: { id: 'newer' } });
  });

  it('ignores a failure from a superseded request', async () => {
    const first = deferred();
    planTripMock.mockReturnValueOnce(first.promise).mockResolvedValueOnce(plan('newer'));
    const { result } = renderHook(() => useTripPlan());

    let firstDone!: Promise<void>;
    act(() => {
      firstDone = result.current.plan(REQUEST);
    });
    await act(() => result.current.plan(REQUEST));
    await act(async () => {
      first.reject({ message: 'The request was cancelled.' });
      await firstDone;
    });

    expect(result.current.state).toMatchObject({ status: 'success', data: { id: 'newer' } });
  });

  it('reset returns to idle and aborts the request in flight', async () => {
    const pending = deferred();
    planTripMock.mockReturnValueOnce(pending.promise);
    const { result } = renderHook(() => useTripPlan());

    let done!: Promise<void>;
    act(() => {
      done = result.current.plan(REQUEST);
    });
    expect(result.current.state).toEqual({ status: 'loading' });

    act(() => result.current.reset());
    expect(result.current.state).toEqual({ status: 'idle' });
    expect(planTripMock.mock.calls[0]?.[1]?.aborted).toBe(true);

    await act(async () => {
      pending.resolve(plan('too late'));
      await done;
    });
    expect(result.current.state).toEqual({ status: 'idle' });
  });

  it('aborts the request in flight on unmount', () => {
    planTripMock.mockReturnValueOnce(deferred().promise);
    const { result, unmount } = renderHook(() => useTripPlan());

    act(() => {
      void result.current.plan(REQUEST);
    });
    unmount();

    expect(planTripMock.mock.calls[0]?.[1]?.aborted).toBe(true);
  });

  it('surfaces API errors with their field errors', async () => {
    planTripMock.mockRejectedValue({ message: 'Current cycle used: too high.', fieldErrors: { current_cycle_used: ['too high'] } });
    const { result } = renderHook(() => useTripPlan());

    await act(() => result.current.plan(REQUEST));

    expect(result.current.state).toEqual({
      status: 'error',
      message: 'Current cycle used: too high.',
      fieldErrors: { current_cycle_used: ['too high'] },
    });
  });

  it('fails readably when the plan is missing a required limit', async () => {
    const { minutes_per_day: _missing, ...incomplete } = API_LIMITS;
    planTripMock.mockResolvedValue(plan('incomplete', incomplete));
    const { result } = renderHook(() => useTripPlan());

    await act(() => result.current.plan(REQUEST));

    expect(result.current.state).toEqual({
      status: 'error',
      message: 'The server sent an incomplete trip plan: limit "minutes_per_day" is missing. Please try again.',
    });
  });
});
