import './states.css';

/** Shown before any trip is planned: what the tool does and what it needs. */
export function EmptyState() {
  return (
    <div className="state state--empty">
      <div>
        <p className="state__title">Plan a trip and get its logs</p>
        <p className="state__detail">
          Enter where the truck is now, the pickup, the dropoff, and the hours already used in the current 70-hour
          cycle. The planner routes the trip for a truck, schedules the required 30-minute breaks, 10-hour rests and fuel
          stops under the FMCSA hours-of-service rules, and fills out a Driver&rsquo;s Daily Log for every day of the trip.
        </p>
      </div>
    </div>
  );
}
