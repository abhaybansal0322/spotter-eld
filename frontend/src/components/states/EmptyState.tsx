import { hoursFigure } from '../../lib/format';
import type { RequiredLimits } from '../../lib/limits';
import './states.css';

/** Shown before any trip is planned: what the tool does and what it needs. Figures come from the backend's limits. */
export function EmptyState({ limits }: { limits: RequiredLimits | null }) {
  const hours = (minutes: number) => (limits ? hoursFigure(minutes / limits.minutes_per_hour) : '');

  return (
    <div className="state state--empty">
      <div>
        <p className="state__title">Plan a trip and get its logs</p>
        {limits ? (
          <p className="state__detail">
            Enter where the truck is now, the pickup, the dropoff, and the hours already used in the current{' '}
            {hours(limits.cycle_limit_min)}-hour cycle. The planner routes the trip for a truck, schedules the required{' '}
            {limits.break_duration_min}-minute breaks, {hours(limits.qualifying_rest_min)}-hour rests and fuel stops
            under the FMCSA hours-of-service rules, and fills out a Driver&rsquo;s Daily Log for every day of the trip.
          </p>
        ) : (
          <p className="state__detail">
            Enter where the truck is now, the pickup, the dropoff, and the hours already used in the current cycle. The
            planner routes the trip for a truck, schedules the required breaks, rests and fuel stops under the FMCSA
            hours-of-service rules, and fills out a Driver&rsquo;s Daily Log for every day of the trip.
          </p>
        )}
      </div>
    </div>
  );
}
