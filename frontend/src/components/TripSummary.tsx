import { useState } from 'react';

import { hoursToHHMM, milesLabel } from '../lib/format';
import type { TripSummary as Summary } from '../types';
import './TripSummary.css';

export interface TripSummaryProps {
  summary: Summary;
  onNewTrip: () => void;
  /** Address that reopens this plan, or null when the plan was not stored and no link would resolve. */
  shareUrl: string | null;
}

/** The trip in one line of figures. */
export function TripSummary({ summary, onNewTrip, shareUrl }: TripSummaryProps) {
  const [copied, setCopied] = useState(false);
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
      {shareUrl !== null && (
        <div className="trip-summary__share" data-print="hide">
          <label className="eyebrow" htmlFor="trip-share-url">
            Trip link
          </label>
          <input
            id="trip-share-url"
            className="trip-summary__url figure"
            readOnly
            value={shareUrl}
            onFocus={(event) => event.currentTarget.select()}
          />
          <button
            type="button"
            className="trip-summary__copy"
            onClick={(event) => {
              const input = event.currentTarget.previousElementSibling as HTMLInputElement;
              // The clipboard API needs a secure context; without it, select the link so the viewer can copy it by hand.
              navigator.clipboard?.writeText(shareUrl).then(() => setCopied(true), () => input.select()) ?? input.select();
            }}
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      )}
    </section>
  );
}
