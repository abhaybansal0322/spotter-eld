import { useEffect, useState } from 'react';

import './states.css';

// Seconds after which the message changes. A sleeping Render instance takes 30 to 60 seconds to wake.
const SLOW_AFTER_S = 8;
const WAKING_AFTER_S = 20;

export interface LoadingStateProps {
  /** What is being loaded, e.g. "Planning your trip". */
  title?: string;
}

/** Says what is happening, and keeps saying it as time passes, so a cold server never looks like a hang. */
export function LoadingState({ title = 'Planning your trip' }: LoadingStateProps) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((elapsed) => elapsed + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  let detail = 'Finding the route, then scheduling driving, breaks, fuel and rests within the hours-of-service rules.';
  if (seconds >= WAKING_AFTER_S) {
    detail = 'The server was asleep and is starting up. This can take up to a minute on the first request; nothing is broken.';
  } else if (seconds >= SLOW_AFTER_S) {
    detail = 'Still working. Long trips and a server that has been idle both take a little longer.';
  }

  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="state__spinner" aria-hidden="true" />
      <div>
        <p className="state__title">{title}&hellip;</p>
        <p className="state__detail">{detail}</p>
        <p className="state__elapsed">{seconds}s</p>
      </div>
    </div>
  );
}
