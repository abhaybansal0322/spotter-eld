import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TRIP_PLAN } from '../../test/fixtures';
import { RouteMap } from '../RouteMap';

vi.mock('react-leaflet', async () => (await import('./leafletMock')).reactLeafletMock);

function renderMap(highlightedIndex: number | null = null, onSelectStop = vi.fn()) {
  render(
    <RouteMap
      route={TRIP_PLAN.route}
      stops={TRIP_PLAN.stops}
      timezone={TRIP_PLAN.timezone}
      highlightedIndex={highlightedIndex}
      onSelectStop={onSelectStop}
    />,
  );
  return onSelectStop;
}

describe('RouteMap', () => {
  it('renders one marker per stop with an icon for its kind', () => {
    renderMap();

    const markers = screen.getAllByTestId('marker');
    expect(markers).toHaveLength(TRIP_PLAN.stops.length);
    expect(markers.map((marker) => marker.className.match(/stop-marker--([A-Z]+)/)?.[1])).toEqual(
      TRIP_PLAN.stops.map((stop) => stop.kind),
    );
    expect(markers[1]?.title).toBe('Pickup: Des Moines, IA');
  });

  it('lists exactly the kinds present in the legend', () => {
    renderMap();

    const legend = screen.getByRole('list', { name: 'Map legend' });
    expect(within(legend).getAllByRole('listitem').map((item) => item.getAttribute('data-kind'))).toEqual([
      'START', 'PICKUP', 'FUEL', 'REST', 'DROPOFF',
    ]);
  });

  it('shows popups in home terminal time and keeps OSM attribution', () => {
    renderMap();

    const popup = screen.getAllByTestId('popup')[2] as HTMLElement;
    expect(within(popup).getByText('Grand Island, NE')).toBeTruthy();
    expect(within(popup).getByText('Times in CDT, home terminal')).toBeTruthy();
    expect(screen.getByTestId('tiles').getAttribute('data-attribution')).toContain('OpenStreetMap');
  });

  it('marks the highlighted stop and reports clicks', () => {
    const onSelectStop = renderMap(2);

    const markers = screen.getAllByTestId('marker');
    expect(markers[2]?.className).toContain('stop-marker--active');
    expect(markers.filter((marker) => marker.className.includes('stop-marker--active'))).toHaveLength(1);
    fireEvent.click(markers[3] as HTMLElement);
    expect(onSelectStop).toHaveBeenCalledWith(3);
  });
});
