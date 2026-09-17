import './states.css';

const TIMELINE_ROWS = 5;

/**
 * Placeholder blocks in the shape of a finished plan: summary, cycle meter and stops beside the map, the log sheet
 * below. Shown under the loading and error messages so the page never sits half empty. Decorative only.
 */
export function ResultsSkeleton({ animated }: { animated: boolean }) {
  return (
    <div className={animated ? 'skeleton skeleton--animated' : 'skeleton'} aria-hidden="true" data-print="hide">
      <div className="plan-page__overview">
        <div className="plan-page__column">
          <div className="panel skeleton__block skeleton__summary" data-skeleton="summary">
            {[0, 1, 2, 3].map((fact) => (
              <span key={fact} className="skeleton__fact">
                <span className="skeleton__line skeleton__line--short" />
                <span className="skeleton__line skeleton__line--figure" />
              </span>
            ))}
          </div>
          <div className="panel skeleton__block skeleton__cycle" data-skeleton="cycle">
            <span className="skeleton__line skeleton__line--short" />
            <span className="skeleton__bar" />
          </div>
          <div className="panel skeleton__block skeleton__timeline" data-skeleton="timeline">
            <span className="skeleton__line skeleton__line--short" />
            {Array.from({ length: TIMELINE_ROWS }, (_, row) => (
              <span key={row} className="skeleton__line" />
            ))}
          </div>
        </div>
        <div className="panel skeleton__block" data-skeleton="map">
          <span className="skeleton__map" />
        </div>
      </div>
      <div className="panel skeleton__block skeleton__sheet" data-skeleton="sheet">
        <span className="skeleton__line skeleton__line--short" />
        <span className="skeleton__paper" />
      </div>
    </div>
  );
}
