import { hoursToHHMM, milesLabel } from '../lib/format';
import type { TripSummary as Summary } from '../types';
import './TripSummary.css';

export interface TripSummaryProps {
  summary: Summary;
  onNewTrip: () => void;
}

/** The trip in one line of figures. */
export function TripSummary({ summary, onNewTrip }: TripSummaryProps) {
  const facts = [
    ['Distance', milesLabel(summary.total_miles)],
    ['Driving', `${hoursToHHMM(summary.driving_hours)} h`],
    ['Door to door', `${hoursToHHMM(summary.elapsed_hours)} h`],
    ['Log sheets', String(summary.days)],
  ] as const;

  return (
    <section className="panel trip-summary" aria-label="Trip summary">
      <dl className="trip-summary__facts">
        {facts.map(([label, value]) => (
          <div key={label} className="trip-summary__fact">
            <dt className="eyebrow">{label}</dt>
            <dd className="figure">{value}</dd>
          </div>
        ))}
      </dl>
      <button type="button" className="button button--quiet trip-summary__new" onClick={onNewTrip} data-print="hide">
        New trip
      </button>
    </section>
  );
}
