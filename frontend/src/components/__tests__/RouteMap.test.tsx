import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TRIP_PLAN } from '../../test/fixtures';
import { RouteMap } from '../RouteMap';
import { mockMap } from './leafletMock';

vi.mock('react-leaflet', async () => (await import('./leafletMock')).reactLeafletMock);

beforeEach(() => {
  mockMap.flyTo.mockClear();
});

function mapElement(highlightedIndex: number | null, selectedIndex: number | null, onSelectStop = vi.fn(), onHoverStop = vi.fn()) {
  return (
    <RouteMap
      route={TRIP_PLAN.route}
      stops={TRIP_PLAN.stops}
      timezone={TRIP_PLAN.timezone}
      highlightedIndex={highlightedIndex}
      selectedIndex={selectedIndex}
      onSelectStop={onSelectStop}
      onHoverStop={onHoverStop}
    />
  );
}

function renderMap(highlightedIndex: number | null = null, onSelectStop = vi.fn()) {
  render(mapElement(highlightedIndex, null, onSelectStop));
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

  it('reports marker hover and hover end', () => {
    const onHoverStop = vi.fn();
    render(mapElement(null, null, vi.fn(), onHoverStop));

    const marker = screen.getAllByTestId('marker')[2] as HTMLElement;
    fireEvent.mouseEnter(marker);
    fireEvent.mouseLeave(marker);

    expect(onHoverStop.mock.calls).toEqual([[2], [null]]);
  });

  it('pans and zooms to the selected stop, and only when the selection changes', () => {
    const { rerender } = render(mapElement(null, null));
    expect(mockMap.flyTo).not.toHaveBeenCalled();

    rerender(mapElement(null, 2));
    const rest = TRIP_PLAN.stops[2]!;
    expect(mockMap.flyTo).toHaveBeenCalledWith([rest.lat, rest.lng], 9);

    rerender(mapElement(3, 2)); // a hover elsewhere does not move the map
    expect(mockMap.flyTo).toHaveBeenCalledTimes(1);
  });

  it('fans out stops that share a spot so each pin can still be clicked', () => {
    const [start, pickup, ...rest] = TRIP_PLAN.stops;
    const stops = [start!, { ...pickup!, lat: start!.lat, lng: start!.lng }, ...rest]; // already at the shipper
    const onSelectStop = vi.fn();
    render(
      <RouteMap route={TRIP_PLAN.route} stops={stops} timezone={TRIP_PLAN.timezone} highlightedIndex={null}
        selectedIndex={null} onSelectStop={onSelectStop} onHoverStop={vi.fn()} />,
    );

    const markers = screen.getAllByTestId('marker');
    const anchors = markers.map((marker) => marker.getAttribute('data-anchor'));
    expect(anchors[0]).not.toBe(anchors[1]);
    expect(anchors.slice(2).every((anchor) => anchor === '14,35')).toBe(true); // stops far apart keep the true anchor
    fireEvent.click(markers[0] as HTMLElement);
    fireEvent.click(markers[1] as HTMLElement);
    expect(onSelectStop.mock.calls).toEqual([[0], [1]]);
  });
});
