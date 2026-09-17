import type { ReactNode } from 'react';
import { vi } from 'vitest';

/** The one map instance every useMap call returns, so tests can assert on fitBounds and flyTo. */
export const mockMap = {
  fitBounds: vi.fn(),
  flyTo: vi.fn(),
  getZoom: vi.fn(() => 4),
  // A flat projection: 100 px per degree, enough for tests to reason about on-screen distance.
  project: vi.fn(([lat, lng]: [number, number]) => ({ x: lng * 100, y: -lat * 100 })),
  on: vi.fn(),
  off: vi.fn(),
};

/** react-leaflet stand-ins that render plain DOM, so tests can see markers, icons and attribution without a map. */
export const reactLeafletMock = {
  MapContainer: ({ children, className }: { children: ReactNode; className?: string }) => (
    <div data-testid="map" className={className}>
      {children}
    </div>
  ),
  TileLayer: ({ attribution }: { attribution: string }) => <div data-testid="tiles" data-attribution={attribution} />,
  Polyline: ({ positions }: { positions: unknown[] }) => <div data-testid="route-line" data-points={positions.length} />,
  Marker: ({
    children,
    icon,
    title,
    eventHandlers,
  }: {
    children: ReactNode;
    icon: { options: { className?: string; iconAnchor?: [number, number] } };
    title?: string;
    eventHandlers?: { click?: () => void; mouseover?: () => void; mouseout?: () => void };
  }) => (
    <div
      data-testid="marker"
      className={icon.options.className}
      data-anchor={icon.options.iconAnchor?.join(',')}
      title={title}
      onClick={eventHandlers?.click}
      onMouseEnter={eventHandlers?.mouseover}
      onMouseLeave={eventHandlers?.mouseout}
    >
      {children}
    </div>
  ),
  Popup: ({ children }: { children: ReactNode }) => <div data-testid="popup">{children}</div>,
  useMap: () => mockMap,
};
