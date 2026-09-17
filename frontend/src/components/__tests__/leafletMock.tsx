import type { ReactNode } from 'react';
import { vi } from 'vitest';

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
    icon: { options: { className?: string } };
    title?: string;
    eventHandlers?: { click?: () => void };
  }) => (
    <div data-testid="marker" className={icon.options.className} title={title} onClick={eventHandlers?.click}>
      {children}
    </div>
  ),
  Popup: ({ children }: { children: ReactNode }) => <div data-testid="popup">{children}</div>,
  useMap: () => ({ fitBounds: vi.fn() }),
};
