import { cycleMeterModel, type CycleKey } from '../lib/cycle';
import { hoursFigure, terminalTime } from '../lib/format';
import type { RequiredLimits } from '../lib/limits';
import type { Stop, TripSummary } from '../types';
import './CycleMeter.css';

export interface CycleMeterProps {
  limits: RequiredLimits;
  summary: TripSummary;
  stops: Stop[];
  timezone: string;
}

const LEGEND: readonly { key: CycleKey; label: string }[] = [
  { key: 'prior', label: 'Used before trip' },
  { key: 'trip', label: 'Added by trip' },
  { key: 'remaining', label: 'Remaining' },
];

/** The cycle as one bar at dropoff: hours still counted from before the trip, from the trip, and what is left. */
export function CycleMeter({ limits, summary, stops, timezone }: CycleMeterProps) {
  const model = cycleMeterModel(limits, summary, stops);
  const limit = hoursFigure(model.limitHours);
  const end = hoursFigure(model.endHours);

  return (
    <section className="panel cycle-meter" aria-label="Cycle hours">
      <header className="panel__header">
        <h2 className="panel__title">{limit}-hour cycle</h2>
        <span className="cycle-meter__end figure">
          {end} / {limit} h at dropoff
        </span>
      </header>
      <div className="cycle-meter__body">
        <div className="cycle-meter__bar" role="img" aria-label={`${end} of ${limit} cycle hours used at dropoff`}>
          {model.segments.map((segment) => (
            <span
              key={segment.key}
              className={`cycle-meter__segment cycle-meter__segment--${segment.key}`}
              data-segment={segment.key}
              style={{ width: segment.width }}
            />
          ))}
          <span className="cycle-meter__limit" data-limit style={{ left: model.limitMarkerLeft }}>
            <span className="cycle-meter__limit-label figure">{limit}h</span>
          </span>
        </div>
        <dl className="cycle-meter__legend">
          {LEGEND.map(({ key, label }) => (
            <div key={key} className="cycle-meter__legend-item">
              <dt>
                <span className={`cycle-meter__key cycle-meter__segment--${key}`} aria-hidden="true" />
                {label}
              </dt>
              <dd className="figure" data-hours={key}>
                {hoursFigure(model.legend[key])} h
              </dd>
            </div>
          ))}
        </dl>
        {model.restart ? (
          <p className="cycle-meter__note" role="note">
            The cycle was exhausted, so a {hoursFigure(model.restart.duration_hours)}-hour restart was inserted at{' '}
            <strong>{model.restart.label}</strong>, starting{' '}
            <time className="figure" dateTime={model.restart.arrive}>
              {terminalTime(model.restart.arrive, timezone)}
            </time>
            . The cycle counts from zero after it, so the bar shows only the hours worked since.
          </p>
        ) : (
          model.shedHours > 0 && (
            <p className="cycle-meter__note" role="note">
              <span className="figure">{hoursFigure(model.shedHours)}</span> h rolled out of the {model.cycleDays}-day
              window before dropoff, so the bar shows fewer hours than were used before and during the trip.
            </p>
          )
        )}
      </div>
    </section>
  );
}
