import { useState } from 'react';

import { useLimits } from '../hooks/useLimits';
import { useTripPlan } from '../hooks/useTripPlan';
import { tripIdFromPath, tripPath, useTripUrl } from '../hooks/useTripUrl';
import { hoursFigure } from '../lib/format';
import type { TripPlanRequest } from '../types';
import { CycleMeter } from './CycleMeter';
import { DayTabs } from './DayTabs';
import { RouteMap } from './RouteMap';
import { StopTimeline } from './StopTimeline';
import { TripForm } from './TripForm';
import { TripSummary } from './TripSummary';
import { EmptyState } from './states/EmptyState';
import { ErrorState } from './states/ErrorState';
import { LoadingState } from './states/LoadingState';
import { ResultsSkeleton } from './states/ResultsSkeleton';

/** Layout and the trip plan state switch. Everything else lives in the components it renders. */
export function PlanPage() {
  const { state, plan, open, reset } = useTripPlan();
  const leaveTrip = useTripUrl(state, open, reset);
  // A plan carries its own limits, so a successful plan fills in for a limits fetch that failed.
  const limits = useLimits() ?? (state.status === 'success' ? state.limits : null);
  const [lastRequest, setLastRequest] = useState<TripPlanRequest | null>(null);
  const [selectedStop, setSelectedStop] = useState<number | null>(null);
  const [timelineHover, setTimelineHover] = useState<number | null>(null);
  const [mapHover, setMapHover] = useState<number | null>(null);

  const clearSelection = () => {
    setSelectedStop(null);
    setTimelineHover(null);
    setMapHover(null);
  };

  const submit = (request: TripPlanRequest) => {
    setLastRequest(request);
    clearSelection();
    leaveTrip();
    void plan(request);
  };

  const newTrip = () => {
    leaveTrip();
    reset();
  };

  // A new plan leaves /trip/:id before it starts, so an id in the address means a stored plan is being opened.
  const openingId = tripIdFromPath(window.location.pathname);
  const retry = openingId ? () => void open(openingId) : lastRequest ? () => submit(lastRequest) : undefined;

  const cycleHours = limits ? hoursFigure(limits.cycle_limit_min / limits.minutes_per_hour) : null;

  return (
    <>
      <header className="app-header" data-print="hide">
        <h1 className="app-header__title">Spotter ELD Trip Planner</h1>
        <span className="app-header__rule-set">
          {limits ? `Property-carrying, ${cycleHours} hours / ${limits.cycle_days} days, 49 CFR Part 395` : 'Property-carrying, 49 CFR Part 395'}
        </span>
      </header>

      <main className="plan-page">
        <aside className="plan-page__form" data-print="hide">
          <TripForm
            onSubmit={submit}
            loading={state.status === 'loading'}
            fieldErrors={state.status === 'error' ? state.fieldErrors : undefined}
            cycleLimitHours={limits ? limits.cycle_limit_min / limits.minutes_per_hour : null}
          />
        </aside>

        <div className="plan-page__content" aria-live="polite">
          {state.status === 'idle' && (
            <>
              <EmptyState limits={limits} />
              <ResultsSkeleton animated={false} />
            </>
          )}

          {state.status === 'loading' && (
            <>
              <LoadingState title={openingId ? 'Opening saved trip' : 'Planning your trip'} />
              <ResultsSkeleton animated />
            </>
          )}

          {state.status === 'error' && (
            <>
              <ErrorState
                title={openingId ? 'We couldn\u2019t open this trip' : undefined}
                message={state.message}
                onRetry={retry}
              />
              <ResultsSkeleton animated={false} />
            </>
          )}

          {state.status === 'success' && (
            <>
              <div className="plan-page__overview" data-print="hide">
                <div className="plan-page__column">
                  <TripSummary
                    summary={state.data.summary}
                    onNewTrip={newTrip}
                    shareUrl={state.data.stored ? `${window.location.origin}${tripPath(state.data.id)}` : null}
                  />
                  <CycleMeter limits={state.limits} summary={state.data.summary} stops={state.data.stops} timezone={state.data.timezone} />
                  <StopTimeline
                    stops={state.data.stops}
                    timezone={state.data.timezone}
                    selectedIndex={selectedStop}
                    mapHoverIndex={mapHover}
                    onSelect={setSelectedStop}
                    onHover={setTimelineHover}
                  />
                </div>
                <RouteMap
                  route={state.data.route}
                  stops={state.data.stops}
                  timezone={state.data.timezone}
                  highlightedIndex={timelineHover ?? mapHover ?? selectedStop}
                  selectedIndex={selectedStop}
                  onSelectStop={setSelectedStop}
                  onHoverStop={setMapHover}
                />
              </div>
              <DayTabs days={state.data.days} timezone={state.data.timezone} limits={state.limits} />
            </>
          )}
        </div>
      </main>
    </>
  );
}
