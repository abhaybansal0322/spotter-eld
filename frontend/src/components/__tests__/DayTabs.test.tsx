import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { LIMITS, TRIP_PLAN } from '../../test/fixtures';
import { DayTabs } from '../DayTabs';

afterEach(() => {
  vi.restoreAllMocks();
});

function panelDate(container: HTMLElement) {
  const part = (name: string) => container.querySelector(`[role="tabpanel"] [data-date-part="${name}"]`)?.textContent;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

describe('DayTabs', () => {
  it('shows one tab per sheet, labelled with weekday and date', () => {
    render(<DayTabs days={TRIP_PLAN.days} timezone={TRIP_PLAN.timezone} limits={LIMITS} />);

    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(TRIP_PLAN.days.length);
    expect(tabs.map((tab) => tab.textContent)).toEqual(['WedSep 16', 'ThuSep 17']);
    expect(tabs[0]?.getAttribute('aria-selected')).toBe('true');
  });

  it('switches the rendered sheet when another tab is chosen', () => {
    const { container } = render(<DayTabs days={TRIP_PLAN.days} timezone={TRIP_PLAN.timezone} limits={LIMITS} />);

    expect(panelDate(container)).toBe('2026-09-16');
    fireEvent.click(screen.getAllByRole('tab')[1] as HTMLElement);
    expect(panelDate(container)).toBe('2026-09-17');
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowRight' });
    expect(panelDate(container)).toBe('2026-09-16');
  });

  it('renders every sheet for printing and prints on request', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const { container } = render(<DayTabs days={TRIP_PLAN.days} timezone={TRIP_PLAN.timezone} limits={LIMITS} />);

    expect(container.querySelectorAll('.day-tabs__print .log-sheet')).toHaveLength(TRIP_PLAN.days.length);
    fireEvent.click(screen.getByRole('button', { name: 'Print all 2 sheets' }));
    expect(print).toHaveBeenCalledOnce();
    expect(container.querySelector('.day-tabs__panel')?.className).toBe('day-tabs__panel');
  });
});
