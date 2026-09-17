import { useCallback, useEffect, useRef, useState } from 'react';

import { planTrip, type ApiError } from '../api/client';
import { parseLimits, type RequiredLimits } from '../lib/limits';
import type { TripPlan, TripPlanRequest } from '../types';

export type TripPlanState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string; fieldErrors?: Record<string, string[]> }
  | { status: 'success'; data: TripPlan; limits: RequiredLimits };

export interface UseTripPlan {
  state: TripPlanState;
  plan: (request: TripPlanRequest) => Promise<void>;
  reset: () => void;
}

/**
 * Owns the trip plan request lifecycle. Starting a new plan aborts the one in flight, and a response that
 * arrives after its request was superseded, reset or unmounted is ignored rather than overwriting newer state.
 * A successful response is narrowed with parseLimits, so a plan missing a limit fails here, not as a blank grid.
 */
export function useTripPlan(): UseTripPlan {
  const [state, setState] = useState<TripPlanState>({ status: 'idle' });
  const inFlight = useRef<AbortController | null>(null);

  const plan = useCallback(async (request: TripPlanRequest) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setState({ status: 'loading' });

    try {
      const data = await planTrip(request, controller.signal);
      const limits = parseLimits(data.limits);
      if (!controller.signal.aborted) {
        setState({ status: 'success', data, limits });
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      // An Error here is InvalidLimitsError from parseLimits; the API client rejects with plain ApiError objects.
      const { message, fieldErrors } = error instanceof Error ? { message: error.message, fieldErrors: undefined } : (error as ApiError);
      setState(fieldErrors ? { status: 'error', message, fieldErrors } : { status: 'error', message });
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
      }
    }
  }, []);

  const reset = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = null;
    setState({ status: 'idle' });
  }, []);

  useEffect(() => () => inFlight.current?.abort(), []);

  return { state, plan, reset };
}
