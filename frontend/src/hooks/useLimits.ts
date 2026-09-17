import { useEffect, useState } from 'react';

import { getLimits } from '../api/client';
import { parseLimits, type RequiredLimits } from '../lib/limits';

/**
 * The backend's limits, fetched once on mount so the form and page copy repeat none of its numbers.
 * Null until they arrive, and null for good if the fetch fails: callers fall back to limit-free behaviour and the
 * server, which validates every plan request, stays the authority.
 */
export function useLimits(): RequiredLimits | null {
  const [limits, setLimits] = useState<RequiredLimits | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getLimits(controller.signal)
      .then((raw) => setLimits(parseLimits(raw)))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  return limits;
}
