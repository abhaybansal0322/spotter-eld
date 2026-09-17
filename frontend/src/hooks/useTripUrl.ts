import { useCallback, useEffect } from 'react';

import type { TripPlanState } from './useTripPlan';

const TRIP_PATH = /^\/trip\/([^/]+)\/?$/;

export function tripIdFromPath(pathname: string): string | null {
  const match = TRIP_PATH.exec(pathname);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

export function tripPath(id: string): string {
  return `/trip/${encodeURIComponent(id)}`;
}

/**
 * Keeps the address bar and the plan in step without a router: /trip/:id opens that stored plan (on load and on
 * back or forward), a plan that loads becomes /trip/:id so the address is shareable, and leaving a plan returns to /.
 */
export function useTripUrl(state: TripPlanState, open: (id: string) => Promise<void>, reset: () => void) {
  useEffect(() => {
    const follow = () => {
      const id = tripIdFromPath(window.location.pathname);
      if (id) {
        void open(id);
      } else {
        reset();
      }
    };
    const initial = tripIdFromPath(window.location.pathname);
    if (initial) {
      void open(initial);
    }
    window.addEventListener('popstate', follow);
    return () => window.removeEventListener('popstate', follow);
  }, [open, reset]);

  const loadedId = state.status === 'success' ? state.data.id : null;
  useEffect(() => {
    if (loadedId && tripIdFromPath(window.location.pathname) !== loadedId) {
      window.history.pushState(null, '', tripPath(loadedId));
    }
  }, [loadedId]);

  /** Leave /trip/:id for / before starting something that is not that trip. */
  return useCallback(() => {
    if (window.location.pathname !== '/') {
      window.history.pushState(null, '', '/');
    }
  }, []);
}
