import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { TripPlanState } from '../../hooks/useTripPlan';
import { LIMITS, TRIP_PLAN } from '../../test/fixtures';
import type { RequiredLimits } from '../../lib/limits';
import { PlanPage } from '../PlanPage';
import { mockMap } from './leafletMock';

vi.mock('react-leaflet', async () => (await import('./leafletMock')).reactLeafletMock);

const hook = vi.hoisted(() => ({
  state: { status: 'idle' } as TripPlanState,
  plan: vi.fn(),
  open: vi.fn(),
  reset: vi.fn(),
}));

vi.mock('../../hooks/useTripPlan', () => ({
  useTripPlan: () => ({ state: hook.state, plan: hook.plan, open: hook.open, reset: hook.reset }),
}));

const fetched = vi.hoisted(() => ({ limits: null as RequiredLimits | null }));
vi.mock('../../hooks/useLimits', () => ({ useLimits: () => fetched.limits }));

const skeletonBlocks = (container: HTMLElement) =>
  [...container.querySelectorAll('[data-skeleton]')].map((block) => block.getAttribute('data-skeleton'));

beforeEach(() => {
  hook.state = { status: 'idle' };
  fetched.limits = LIMITS;
  mockMap.flyTo.mockClear();
  hook.plan.mockReset();
  hook.open.mockReset();
  window.history.replaceState(null, '', '/');
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

  it('reads the header, empty-state copy and form cap from the fetched limits', () => {
    render(<PlanPage />);

    expect(screen.getByText('Property-carrying, 70 hours / 8 days, 49 CFR Part 395')).toBeTruthy();
    expect(screen.getByText(/current 70-hour cycle.*30-minute breaks, 10-hour rests/)).toBeTruthy();
    expect(screen.getByLabelText('Current cycle used').getAttribute('max')).toBe('70');
  });

  it('keeps the form usable and the copy number-free when the limits fetch fails', () => {
    fetched.limits = null;
    render(<PlanPage />);

    expect(screen.getByText('Property-carrying, 49 CFR Part 395')).toBeTruthy();
    expect(screen.queryByText(/70/)).toBeNull();
    expect(screen.getByLabelText('Current cycle used').getAttribute('max')).toBeNull();
    submitTrip();
    expect(hook.plan).toHaveBeenCalledTimes(1);
  });

  it('shows the loading state, skeleton results and a busy form while loading', () => {
    hook.state = { status: 'loading' };
    const { container } = render(<PlanPage />);

    expect(screen.getByRole('status').textContent).toContain('Planning your trip');
    expect(skeletonBlocks(container)).toEqual(['summary', 'cycle', 'timeline', 'map', 'sheet']);
    expect(container.querySelector('.skeleton')?.classList.contains('skeleton--animated')).toBe(true);
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
    expect(skeletonBlocks(document.body)).toEqual(['summary', 'cycle', 'timeline', 'map', 'sheet']);
    expect(document.querySelector('.skeleton')?.classList.contains('skeleton--animated')).toBe(false);
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
    expect(skeletonBlocks(document.body)).toEqual([]);
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

  it('highlights and scrolls to the timeline row for a hovered map marker', () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    hook.state = { status: 'success', data: TRIP_PLAN, limits: LIMITS };
    render(<PlanPage />);

    const marker = screen.getAllByTestId('marker')[3] as HTMLElement;
    fireEvent.mouseEnter(marker);

    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.findIndex((row) => row.hasAttribute('data-map-hover'))).toBe(3);
    expect(scrollIntoView.mock.contexts).toEqual([rows[3]]);
    expect(marker.className).toContain('stop-marker--active');

    fireEvent.mouseLeave(marker);
    expect(rows.some((row) => row.hasAttribute('data-map-hover'))).toBe(false);
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  });

  it('pans and zooms the map to a stop selected from either side', () => {
    hook.state = { status: 'success', data: TRIP_PLAN, limits: LIMITS };
    render(<PlanPage />);
    const at = (index: number) => [TRIP_PLAN.stops[index]!.lat, TRIP_PLAN.stops[index]!.lng];

    fireEvent.click(screen.getAllByRole('row')[3] as HTMLElement); // timeline row for stop 2
    expect(mockMap.flyTo).toHaveBeenLastCalledWith(at(2), expect.any(Number));

    fireEvent.click(screen.getAllByTestId('marker')[4] as HTMLElement);
    expect(mockMap.flyTo).toHaveBeenLastCalledWith(at(4), expect.any(Number));
    expect(screen.getAllByRole('row')[5]?.getAttribute('aria-selected')).toBe('true');
  });

  it('shows the results skeleton behind the empty-state copy when idle', () => {
    const { container } = render(<PlanPage />);

    expect(screen.getByText('Plan a trip and get its logs')).toBeTruthy();
    expect(skeletonBlocks(container)).toEqual(['summary', 'cycle', 'timeline', 'map', 'sheet']);
    expect(container.querySelector('.skeleton')?.classList.contains('skeleton--animated')).toBe(false);
  });

  it('opens the trip named in a /trip/:id address, with its own loading and error copy and retry', () => {
    window.history.replaceState(null, '', '/trip/3f2b8c1e');
    hook.state = { status: 'loading' };
    const { rerender } = render(<PlanPage />);

    expect(hook.open).toHaveBeenCalledWith('3f2b8c1e');
    expect(screen.getByRole('status').textContent).toContain('Opening saved trip');

    hook.state = { status: 'error', message: 'Not found.' };
    rerender(<PlanPage />);
    expect(screen.getByRole('alert').textContent).toContain('We couldn\u2019t open this trip');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(hook.open).toHaveBeenLastCalledWith('3f2b8c1e');
    expect(hook.plan).not.toHaveBeenCalled();
  });

  it('gives a loaded plan a shareable address with a copy button, and New trip returns to /', async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    hook.state = { status: 'success', data: TRIP_PLAN, limits: LIMITS };
    render(<PlanPage />);

    const url = `${window.location.origin}/trip/${TRIP_PLAN.id}`;
    expect(window.location.pathname).toBe(`/trip/${TRIP_PLAN.id}`);
    expect((screen.getByLabelText('Trip link') as HTMLInputElement).value).toBe(url);
    expect(hook.open).not.toHaveBeenCalled(); // the address was pushed after loading, not followed

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    expect(writeText).toHaveBeenCalledWith(url);
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'New trip' }));
    expect(window.location.pathname).toBe('/');
    expect(hook.reset).toHaveBeenCalled();
    Reflect.deleteProperty(navigator, 'clipboard');
  });

  it('follows back and forward between a trip address and the planner', () => {
    render(<PlanPage />);

    window.history.pushState(null, '', '/trip/abc');
    fireEvent.popState(window);
    expect(hook.open).toHaveBeenCalledWith('abc');

    window.history.pushState(null, '', '/');
    fireEvent.popState(window);
    expect(hook.reset).toHaveBeenCalled();
  });
});
