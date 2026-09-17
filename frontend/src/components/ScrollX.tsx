import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import './ScrollX.css';

export interface ScrollXProps {
  children: ReactNode;
  /** Classes for the scrolling viewport itself. */
  className?: string;
  /** Accessible name for the scroll region, so keyboard users can find and scroll it. */
  label: string;
  /** Shown once, until the viewer first scrolls this container, e.g. "Scroll for more columns". */
  hint?: string;
  /** Remembers that the hint was seen, per container kind. Required with hint. */
  hintKey?: string;
}

const HINT_STORAGE_PREFIX = 'spotter-eld:scroll-hint-seen:';
const EDGE_TOLERANCE_PX = 1; // sub-pixel scroll positions never quite reach the end

function hintSeen(key: string | undefined): boolean {
  try {
    return key !== undefined && window.localStorage.getItem(HINT_STORAGE_PREFIX + key) === '1';
  } catch {
    return false;
  }
}

function rememberHint(key: string | undefined) {
  try {
    if (key !== undefined) window.localStorage.setItem(HINT_STORAGE_PREFIX + key, '1');
  } catch {
    // Storage unavailable: the hint simply shows again next visit.
  }
}

/**
 * A container that scrolls sideways and shows it (spec §27): an edge fade on each side that has more content, and a
 * one-time hint until the viewer first scrolls. Nothing shows when the content fits.
 */
export function ScrollX({ children, className, label, hint, hintKey }: ScrollXProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const [showHint, setShowHint] = useState(() => hint !== undefined && !hintSeen(hintKey));

  const measure = useCallback(() => {
    const element = viewport.current;
    if (!element) return;
    const left = element.scrollLeft > EDGE_TOLERANCE_PX;
    const right = element.scrollLeft < element.scrollWidth - element.clientWidth - EDGE_TOLERANCE_PX;
    setEdges((current) => (current.left === left && current.right === right ? current : { left, right }));
  }, []);

  useEffect(() => {
    measure();
    const element = viewport.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, [measure]);

  const onScroll = () => {
    measure();
    if (showHint && (viewport.current?.scrollLeft ?? 0) > EDGE_TOLERANCE_PX) {
      setShowHint(false);
      rememberHint(hintKey);
    }
  };

  const scrollable = edges.left || edges.right;

  return (
    <div className="scroll-x" data-fade-left={edges.left || undefined} data-fade-right={edges.right || undefined}>
      <div
        ref={viewport}
        className={className ? `scroll-x__viewport ${className}` : 'scroll-x__viewport'}
        onScroll={onScroll}
        role={scrollable ? 'region' : undefined}
        aria-label={scrollable ? label : undefined}
        tabIndex={scrollable ? 0 : undefined}
      >
        {children}
      </div>
      {showHint && edges.right && (
        <p className="scroll-x__hint" aria-hidden="true">
          {hint} <span className="scroll-x__arrow">&rarr;</span>
        </p>
      )}
    </div>
  );
}
