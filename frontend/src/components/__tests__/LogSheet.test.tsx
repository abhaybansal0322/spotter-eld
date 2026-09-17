import { render, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { JOHN_DOE_DAY, LIMITS } from '../../test/fixtures';
import { LogSheet } from '../LogSheet';

function renderSheet() {
  return render(<LogSheet day={JOHN_DOE_DAY} timezone="America/New_York" limits={LIMITS} />);
}

describe('LogSheet', () => {
  it('splits the date into month, day and year', () => {
    const { container } = renderSheet();

    const part = (name: string) => container.querySelector(`[data-date-part="${name}"]`)?.textContent;
    expect([part('month'), part('day'), part('year')]).toEqual(['04', '09', '2021']);
  });

  it('renders null header fields as blank lines, never as "null"', () => {
    const { container } = renderSheet();

    expect(container.textContent).not.toMatch(/null|undefined/i);
    const carrier = within(container).getByText('Name of Carrier or Carriers').parentElement;
    expect(carrier?.querySelector('.log-sheet__line')?.textContent).toBe('');
    expect(container.querySelector('[data-field="vehicle-numbers"]')?.textContent).toBe('');
    expect(within(container).getByText('Richmond, VA', { selector: '.log-sheet__line' })).toBeTruthy();
  });

  it('renders recap A, B and C with their printed captions', () => {
    const { container } = renderSheet();

    const cycle = container.querySelector('[data-cycle="70-8"]') as HTMLElement;
    const value = (field: string) => cycle.querySelector(`[data-recap="${field}"]`)?.textContent;
    expect([value('a'), value('b'), value('c')]).toEqual(['12.25', '57.75', '12.25']);
    expect(within(cycle).getByText('A. Total hours on duty last 7 days including today.')).toBeTruthy();
    expect(within(cycle).getByText('B. Total hours available tomorrow 70 hr. minus A*')).toBeTruthy();
    expect(within(cycle).getByText('C. Total hours on duty last 5 days including today.')).toBeTruthy();
    expect(container.querySelector('[data-recap="on-duty-today"]')?.textContent).toBe('12.25');
  });

  it('renders the 60 hour / 7 day columns present but empty', () => {
    const { container } = renderSheet();

    const cycle = container.querySelector('[data-cycle="60-7"]') as HTMLElement;
    expect(within(cycle).getByText('60 Hour/ 7 Day Drivers')).toBeTruthy();
    const values = [...cycle.querySelectorAll('[data-recap]')].map((box) => box.textContent);
    expect(values).toEqual(['', '', '']);
  });

  it('says the empty 60 hour / 7 day column is unused, naming the cycle from the limits', () => {
    const { container, rerender } = renderSheet();

    const note = () => container.querySelector('[data-cycle="60-7"] [data-cycle-note]')?.textContent;
    expect(note()).toBe('Not used: this log follows the 70 hour / 8 day cycle.');

    rerender(<LogSheet day={JOHN_DOE_DAY} timezone="America/New_York" limits={{ ...LIMITS, cycle_limit_min: 3600, cycle_days: 7 }} />);
    expect(note()).toBe('Not used: this log follows the 60 hour / 7 day cycle.');
  });

  it('shows the John Doe totals from page 18: 10, 1.75, 7.75 and 4.5', () => {
    const { container } = renderSheet();

    const totals = [...container.querySelectorAll('[data-total] text')].map((text) => text.textContent);
    expect(totals).toEqual(['10', '1.75', '7.75', '4.5', '=24']);
    expect(container.querySelector('[data-field="total-miles-driving"]')?.textContent).toBe('426 mi');
  });
});
