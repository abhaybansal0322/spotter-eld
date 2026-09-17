import { useState } from 'react';

import { useTripPlan } from '../hooks/useTripPlan';
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

/** Layout and the trip plan state switch. Everything else lives in the components it renders. */
export function PlanPage() {
  const { state, plan, reset } = useTripPlan();
  const [lastRequest, setLastRequest] = useState<TripPlanRequest | null>(null);
  const [selectedStop, setSelectedStop] = useState<number | null>(null);
  const [hoveredStop, setHoveredStop] = useState<number | null>(null);

  const submit = (request: TripPlanRequest) => {
    setLastRequest(request);
    setSelectedStop(null);
    setHoveredStop(null);
    void plan(request);
  };

  return (
    <>
      <header className="app-header" data-print="hide">
        <h1 className="app-header__title">Spotter ELD Trip Planner</h1>
        <span className="app-header__rule-set">Property-carrying, 70 hours / 8 days, 49 CFR Part 395</span>
      </header>

      <main className="plan-page">
        <aside className="plan-page__form" data-print="hide">
          <TripForm
            onSubmit={submit}
            loading={state.status === 'loading'}
            fieldErrors={state.status === 'error' ? state.fieldErrors : undefined}
          />
        </aside>

        <div className="plan-page__content" aria-live="polite">
          {state.status === 'idle' && <EmptyState />}

          {state.status === 'loading' && <LoadingState />}

          {state.status === 'error' && (
            <ErrorState message={state.message} onRetry={lastRequest ? () => submit(lastRequest) : undefined} />
          )}

          {state.status === 'success' && (
            <>
              <div className="plan-page__overview" data-print="hide">
                <div className="plan-page__column">
                  <TripSummary summary={state.data.summary} onNewTrip={reset} />
                  <CycleMeter
                    limits={state.limits}
                    summary={state.data.summary}
                    startHours={lastRequest?.current_cycle_used ?? 0}
                    stops={state.data.stops}
                    timezone={state.data.timezone}
                  />
                  <StopTimeline
                    stops={state.data.stops}
                    timezone={state.data.timezone}
                    selectedIndex={selectedStop}
                    onSelect={setSelectedStop}
                    onHover={setHoveredStop}
                  />
                </div>
                <RouteMap
                  route={state.data.route}
                  stops={state.data.stops}
                  timezone={state.data.timezone}
                  highlightedIndex={hoveredStop ?? selectedStop}
                  onSelectStop={setSelectedStop}
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
