import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TRIP_PLAN } from '../../test/fixtures';
import { RouteMap } from '../RouteMap';

// Real Leaflet and react-leaflet, not the mock: the class must reach the <path> Leaflet draws. Passing it through
// pathOptions compiled and rendered, but left the line in Leaflet's default blue on every screen.
describe('RouteMap with real Leaflet', () => {
  it('draws the route as an SVG path carrying the route-map__line class', () => {
    const { container } = render(
      <RouteMap
        route={TRIP_PLAN.route}
        stops={TRIP_PLAN.stops}
        timezone={TRIP_PLAN.timezone}
        highlightedIndex={null}
        selectedIndex={null}
        onSelectStop={vi.fn()}
        onHoverStop={vi.fn()}
      />,
    );

    const paths = container.querySelectorAll('.leaflet-overlay-pane path');
    expect(paths).toHaveLength(1);
    expect(paths[0]?.classList.contains('route-map__line')).toBe(true);
  });
});
