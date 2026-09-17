import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { TripPlanState } from '../../hooks/useTripPlan';
import { LIMITS, TRIP_PLAN } from '../../test/fixtures';
import { PlanPage } from '../PlanPage';

vi.mock('react-leaflet', async () => (await import('./leafletMock')).reactLeafletMock);

const hook = vi.hoisted(() => ({
  state: { status: 'idle' } as TripPlanState,
  plan: vi.fn(),
  reset: vi.fn(),
}));

vi.mock('../../hooks/useTripPlan', () => ({
  useTripPlan: () => ({ state: hook.state, plan: hook.plan, reset: hook.reset }),
}));

beforeEach(() => {
  hook.state = { status: 'idle' };
  hook.plan.mockReset();
  hook.reset.mockReset();
});

function submitTrip() {
  const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fill('Current location', 'Chicago, IL');
  fill('Pickup location', 'Des Moines, IA');
  fill('Dropoff location', 'Denver, CO');
  fill('Current cycle used', '20');
  fireEvent.click(screen.getByRole('button', { name: 'Plan trip' }));
}

describe('PlanPage', () => {
  it('shows the empty state beside the form when idle', () => {
    render(<PlanPage />);

    expect(screen.getByText('Plan a trip and get its logs')).toBeTruthy();
    expect(screen.getByRole('form', { name: 'Trip details' })).toBeTruthy();
  });

  it('shows the loading state and a busy form while loading', () => {
    hook.state = { status: 'loading' };
    render(<PlanPage />);

    expect(screen.getByRole('status').textContent).toContain('Planning your trip');
    expect((screen.getByRole('button', { name: 'Planning trip…' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows the error state, puts field errors on the form, and retries the last request', () => {
    const { rerender } = render(<PlanPage />);
    submitTrip();
    const request = hook.plan.mock.calls[0]?.[0];

    hook.state = {
      status: 'error',
      message: 'No truck-accessible road was found near the dropoff location (Denver, CO).',
      fieldErrors: { dropoff_location: ['Check this address.'] },
    };
    rerender(<PlanPage />);

    expect(screen.getByRole('alert').textContent).toContain('No truck-accessible road was found');
    expect(screen.getByLabelText('Dropoff location').getAttribute('aria-invalid')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(hook.plan).toHaveBeenCalledTimes(2);
    expect(hook.plan.mock.calls[1]?.[0]).toEqual(request);
  });

  it('shows summary, cycle meter, map, timeline and day tabs on success', () => {
    const { rerender } = render(<PlanPage />);
    submitTrip();
    hook.state = { status: 'success', data: TRIP_PLAN, limits: LIMITS };
    rerender(<PlanPage />);

    expect(screen.getByRole('region', { name: 'Trip summary' })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Cycle hours' }).textContent).toContain('20 h');
    expect(screen.getByRole('region', { name: 'Route map' })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Stops' })).toBeTruthy();
    expect(screen.getAllByRole('tab')).toHaveLength(2);
  });

  it('highlights the map marker for a hovered timeline row', () => {
    hook.state = { status: 'success', data: TRIP_PLAN, limits: LIMITS };
    render(<PlanPage />);

    fireEvent.mouseEnter(screen.getAllByRole('row')[3] as HTMLElement);
    const active = screen.getAllByTestId('marker').findIndex((marker) => marker.className.includes('stop-marker--active'));
    expect(active).toBe(2);
  });
});
