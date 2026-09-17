import { useId, useState, type KeyboardEvent } from 'react';

import { calendarLabel } from '../lib/format';
import type { RequiredLimits } from '../lib/limits';
import type { DaySheet } from '../types';
import { LogSheet } from './LogSheet';
import { ScrollX } from './ScrollX';
import './DayTabs.css';

export interface DayTabsProps {
  days: DaySheet[];
  timezone: string;
  limits: RequiredLimits;
}

/** One tab per daily log. Only the selected sheet shows on screen; printing produces every sheet. */
export function DayTabs({ days, timezone, limits }: DayTabsProps) {
  const id = useId();
  const [selected, setSelected] = useState(0);
  const day = days[Math.min(selected, days.length - 1)];

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (step !== 0) {
      event.preventDefault();
      const next = (selected + step + days.length) % days.length;
      setSelected(next);
      document.getElementById(`${id}-tab-${next}`)?.focus();
    }
  };

  if (!day) {
    return null;
  }

  return (
    <section className="panel day-tabs" aria-label="Daily log sheets">
      <header className="panel__header day-tabs__header" data-print="hide">
        <ScrollX className="day-tabs__tabs" label="Days">
          <div role="tablist" aria-label="Log sheet by day" className="day-tabs__list" onKeyDown={onKeyDown}>
            {days.map((sheet, index) => {
              const label = calendarLabel(sheet.date);
              return (
                <button
                  key={sheet.date}
                  id={`${id}-tab-${index}`}
                  type="button"
                  role="tab"
                  className="day-tabs__tab"
                  aria-selected={index === selected}
                  aria-controls={`${id}-panel`}
                  tabIndex={index === selected ? 0 : -1}
                  onClick={() => setSelected(index)}
                >
                  <span className="day-tabs__weekday">{label.weekday}</span>
                  <span className="day-tabs__date figure">{label.date}</span>
                </button>
              );
            })}
          </div>
        </ScrollX>
        <button type="button" className="button button--quiet" onClick={() => window.print()}>
          Print all {days.length} sheets
        </button>
      </header>

      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-tab-${selected}`}
        className="day-tabs__panel"
        data-print="hide"
      >
        <ScrollX className="day-tabs__sheet" label="Log sheet" hint="Scroll to see the whole sheet" hintKey="log-sheet">
          <div className="day-tabs__paper">
            <LogSheet day={day} timezone={timezone} limits={limits} />
          </div>
        </ScrollX>
      </div>

      <div className="day-tabs__print" aria-hidden="true">
        {days.map((sheet) => (
          <LogSheet key={sheet.date} day={sheet} timezone={timezone} limits={limits} />
        ))}
      </div>
    </section>
  );
}
