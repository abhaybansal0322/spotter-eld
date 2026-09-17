import { cycleMeterModel } from '../lib/cycle';
import { hoursFigure, terminalTime } from '../lib/format';
import type { RequiredLimits } from '../lib/limits';
import type { Stop, TripSummary } from '../types';
import './CycleMeter.css';

export interface CycleMeterProps {
  limits: RequiredLimits;
  summary: TripSummary;
  /** Cycle hours the driver submitted. */
  startHours: number;
  stops: Stop[];
  timezone: string;
}

const SEGMENT_LABEL = { prior: 'Used before trip', trip: 'Added by trip', remaining: 'Remaining' } as const;

/** The 70-hour, 8-day cycle as one bar: hours already used, hours this trip adds, and what is left. */
export function CycleMeter({ limits, summary, startHours, stops, timezone }: CycleMeterProps) {
  const model = cycleMeterModel(limits, summary, startHours, stops);

  return (
    <section className="panel cycle-meter" aria-label="Cycle hours">
      <header className="panel__header">
        <h2 className="panel__title">{hoursFigure(model.limitHours)}-hour cycle</h2>
        <span className="cycle-meter__end figure">
          {hoursFigure(model.endHours)} / {hoursFigure(model.limitHours)} h at dropoff
        </span>
      </header>
      <div className="cycle-meter__body">
        <div className="cycle-meter__bar" role="img" aria-label={`${hoursFigure(model.endHours)} of ${hoursFigure(model.limitHours)} cycle hours used at dropoff`}>
          {model.segments.map((segment) => (
            <span key={segment.key} className={`cycle-meter__segment cycle-meter__segment--${segment.key}`} data-segment={segment.key} style={{ width: segment.width }} />
          ))}
          <span className="cycle-meter__limit" data-limit style={{ left: model.limitMarkerLeft }}>
            <span className="cycle-meter__limit-label figure">{hoursFigure(model.limitHours)}h</span>
          </span>
        </div>
        <dl className="cycle-meter__legend">
          {model.segments.map((segment) => (
            <div key={segment.key} className="cycle-meter__legend-item">
              <dt>
                <span className={`cycle-meter__key cycle-meter__segment--${segment.key}`} aria-hidden="true" />
                {SEGMENT_LABEL[segment.key]}
              </dt>
              <dd className="figure" data-hours={segment.key}>
                {hoursFigure(segment.hours)} h
              </dd>
            </div>
          ))}
        </dl>
        {summary.restart_required && model.restart && (
          <p className="cycle-meter__restart" role="note">
            The cycle was exhausted, so a {hoursFigure(model.restart.duration_hours)}-hour restart was inserted at{' '}
            <strong>{model.restart.label}</strong>, starting{' '}
            <time className="figure" dateTime={model.restart.arrive}>
              {terminalTime(model.restart.arrive, timezone)}
            </time>
            . The cycle counts from zero after it.
          </p>
        )}
      </div>
    </section>
  );
}
