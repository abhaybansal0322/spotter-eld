import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TRIP_PLAN } from '../../test/fixtures';
import { StopTimeline } from '../StopTimeline';

describe('StopTimeline', () => {
  it('lists every stop in order with terminal times and mile markers', () => {
    render(<StopTimeline stops={TRIP_PLAN.stops} timezone={TRIP_PLAN.timezone} selectedIndex={null} mapHoverIndex={null} onSelect={vi.fn()} onHover={vi.fn()} />);

    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => row.getAttribute('data-kind'))).toEqual(['START', 'PICKUP', 'REST', 'FUEL', 'DROPOFF']);
    expect(rows[2]?.textContent).toContain('Grand Island, NE');
    expect(rows[2]?.textContent).toContain('10:00');
    expect(rows[4]?.textContent).toContain('1,007.0');
    expect(screen.getByText('Home terminal time, CDT')).toBeTruthy();
  });

  it('fires the callbacks when a row is selected or hovered', () => {
    const onSelect = vi.fn();
    const onHover = vi.fn();
    render(<StopTimeline stops={TRIP_PLAN.stops} timezone={TRIP_PLAN.timezone} selectedIndex={1} mapHoverIndex={null} onSelect={onSelect} onHover={onHover} />);

    const rows = screen.getAllByRole('row').slice(1);
    fireEvent.click(rows[3] as HTMLElement);
    fireEvent.keyDown(rows[2] as HTMLElement, { key: 'Enter' });
    fireEvent.mouseEnter(rows[4] as HTMLElement);

    expect(onSelect.mock.calls).toEqual([[3], [2]]);
    expect(onHover).toHaveBeenCalledWith(4);
    expect(rows[1]?.getAttribute('aria-selected')).toBe('true');
  });

  it('highlights the row for a marker hovered on the map and scrolls it into view', () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const props = { stops: TRIP_PLAN.stops, timezone: TRIP_PLAN.timezone, selectedIndex: null, onSelect: vi.fn(), onHover: vi.fn() };
    const { rerender } = render(<StopTimeline {...props} mapHoverIndex={null} />);
    expect(scrollIntoView).not.toHaveBeenCalled();

    rerender(<StopTimeline {...props} mapHoverIndex={3} />);

    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => row.hasAttribute('data-map-hover'))).toEqual([false, false, false, true, false]);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView.mock.contexts[0]).toBe(rows[3]);
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  });
});
