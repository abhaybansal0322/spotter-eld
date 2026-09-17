import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TripForm } from '../TripForm';

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('TripForm', () => {
  it('shows the four inputs from the brief', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} />);

    for (const label of ['Current location', 'Pickup location', 'Dropoff location', 'Current cycle used']) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.getByLabelText('Current cycle used, slider')).toBeTruthy();
  });

  it('keeps the advanced fields collapsed by default', () => {
    const { container } = render(<TripForm onSubmit={vi.fn()} loading={false} />);

    const advanced = container.querySelector('details');
    expect(advanced?.open).toBe(false);
    expect(advanced?.querySelector('input[name="start_time"]')).toBeTruthy();
    expect(advanced?.querySelector('select[name="timezone"]')).toBeTruthy();
  });

  it('binds the number and slider and shows the hours left', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} />);

    fireEvent.change(screen.getByLabelText('Current cycle used, slider'), { target: { value: '42.5' } });

    expect((screen.getByLabelText('Current cycle used') as HTMLInputElement).value).toBe('42.5');
    expect(screen.getByText('27.5').closest('p')?.textContent).toBe('27.5 h left in the cycle');
  });

  it('submits the request shape the API expects', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} />);

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
    render(<TripForm onSubmit={onSubmit} loading={false} />);

    fill('Pickup location', 'Denver, CO');
    fill('Dropoff location', ' denver,  co');
    fill('Current cycle used', '71');
    fireEvent.click(screen.getByRole('button', { name: 'Plan trip' }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Current location').getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Hours used must be between 0 and 70.')).toBeTruthy();
    expect(screen.getByText('Pickup and dropoff must be different locations.')).toBeTruthy();
  });

  it('renders a server field error against its own input', () => {
    render(<TripForm onSubmit={vi.fn()} loading={false} fieldErrors={{ pickup_location: ['This field may not be blank.'] }} />);

    const pickup = screen.getByLabelText('Pickup location');
    expect(pickup.getAttribute('aria-invalid')).toBe('true');
    const describedBy = pickup.getAttribute('aria-describedby') ?? '';
    expect(document.getElementById(describedBy)?.textContent).toBe('This field may not be blank.');
    expect(screen.getByLabelText('Dropoff location').getAttribute('aria-invalid')).toBe('false');
  });

  it('disables submit and says what it is doing while loading', () => {
    render(<TripForm onSubmit={vi.fn()} loading />);

    const button = screen.getByRole('button', { name: 'Planning trip…' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });
});
