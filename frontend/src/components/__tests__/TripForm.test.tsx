import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LIMITS } from '../../test/fixtures';
import { TripForm } from '../TripForm';

const CYCLE_HOURS = LIMITS.cycle_limit_min / LIMITS.minutes_per_hour;

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('TripForm', () => {
  it('shows the four inputs from the brief', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    for (const label of ['Current location', 'Pickup location', 'Dropoff location', 'Current cycle used']) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.getByLabelText('Current cycle used, slider')).toBeTruthy();
  });

  it('keeps the advanced fields collapsed by default', () => {
    const { container } = render(<TripForm onSubmit={vi.fn()} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    const advanced = container.querySelector('details');
    expect(advanced?.open).toBe(false);
    expect(advanced?.querySelector('input[name="start_time"]')).toBeTruthy();
    expect(advanced?.querySelector('select[name="timezone"]')).toBeTruthy();
  });

  it('binds the number and slider and shows the hours left', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    fireEvent.change(screen.getByLabelText('Current cycle used, slider'), { target: { value: '42.5' } });

    expect((screen.getByLabelText('Current cycle used') as HTMLInputElement).value).toBe('42.5');
    expect(screen.getByText('27.5').closest('p')?.textContent).toBe('27.5 h left in the cycle');
  });

  it('submits the request shape the API expects', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    fill('Current location', '  Chicago, IL ');
    fill('Pickup location', 'Des Moines, IA');
    fill('Dropoff location', 'Denver, CO');
    fill('Current cycle used', '12.5');
    fireEvent.click(screen.getByRole('button', { name: 'Plan trip' }));

    expect(onSubmit).toHaveBeenCalledWith({
      current_location: 'Chicago, IL',
      pickup_location: 'Des Moines, IA',
      dropoff_location: 'Denver, CO',
      current_cycle_used: 12.5,
      timezone: 'America/New_York',
    });
  });

  it('checks obvious mistakes locally and does not submit', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    fill('Pickup location', 'Denver, CO');
    fill('Dropoff location', ' denver,  co');
    fill('Current cycle used', '71');
    fireEvent.click(screen.getByRole('button', { name: 'Plan trip' }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Current location').getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Hours used must be between 0 and 70.')).toBeTruthy();
    expect(screen.getByText('Pickup and dropoff must be different locations.')).toBeTruthy();
  });

  it('falls back to permitting any non-negative hours when the limits could not be fetched', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} cycleLimitHours={null} />);

    expect(screen.queryByLabelText('Current cycle used, slider')).toBeNull();
    expect(screen.getByLabelText('Current cycle used').getAttribute('max')).toBeNull();
    fill('Current location', 'Chicago, IL');
    fill('Pickup location', 'Des Moines, IA');
    fill('Dropoff location', 'Denver, CO');
    fill('Current cycle used', '90');
    fireEvent.click(screen.getByRole('button', { name: 'Plan trip' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ current_cycle_used: 90 }));
  });

  it('offers both demo routes above the location fields', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} cycleLimitHours={CYCLE_HOURS} />);

    const group = screen.getByRole('group', { name: 'Or fill in a demo route' });
    expect(within(group).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Amarillo → Denver 1 day',
      'Los Angeles → Boston multi-day',
    ]);
    const order = Array.from(document.querySelectorAll('[role=group], input[name=current_location]'));
    expect(order[0]).toBe(group); // before the fields, so it reads as a shortcut
  });

  it.each([
    ['Amarillo → Denver 1 day', 'Amarillo, TX', 'Dumas, TX', 'Denver, CO'],
    ['Los Angeles → Boston multi-day', 'Los Angeles, CA', 'Las Vegas, NV', 'Boston, MA'],
  ])('fills the three locations from the %s preset without submitting or touching cycle hours', (name, current, pickup, dropoff) => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} cycleLimitHours={CYCLE_HOURS} />);
    fill('Current cycle used', '33.5');

    fireEvent.click(screen.getByRole('button', { name }));

    const value = (label: string) => (screen.getByLabelText(label) as HTMLInputElement).value;
    expect([value('Current location'), value('Pickup location'), value('Dropoff location')]).toEqual([current, pickup, dropoff]);
    expect(value('Current cycle used')).toBe('33.5');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('renders a server field error against its own input', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} cycleLimitHours={CYCLE_HOURS} fieldErrors={{ pickup_location: ['This field may not be blank.'] }} />);

    const pickup = screen.getByLabelText('Pickup location');
    expect(pickup.getAttribute('aria-invalid')).toBe('true');
    const describedBy = pickup.getAttribute('aria-describedby') ?? '';
    expect(document.getElementById(describedBy)?.textContent).toBe('This field may not be blank.');
    expect(screen.getByLabelText('Dropoff location').getAttribute('aria-invalid')).toBe('false');
  });

  it('disables submit and says what it is doing while loading', () => {
    render(<TripForm onSubmit={vi.fn()} loading cycleLimitHours={CYCLE_HOURS} />);

    const button = screen.getByRole('button', { name: 'Planning trip…' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });
});
