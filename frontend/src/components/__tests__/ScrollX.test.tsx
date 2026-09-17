import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ScrollX } from '../ScrollX';

/** jsdom does no layout, so give every element the widths of a 300px viewport over 900px of content. */
function overflowing() {
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(900);
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(300);
}

function renderScroller() {
  return render(
    <ScrollX label="Stops table" hint="Scroll for more columns" hintKey="test">
      <table />
    </ScrollX>,
  );
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('ScrollX', () => {
  it('shows nothing extra when the content fits', () => {
    const { container } = renderScroller();

    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.hasAttribute('data-fade-left') || wrapper.hasAttribute('data-fade-right')).toBe(false);
    expect(screen.queryByText('Scroll for more columns')).toBeNull();
    expect(screen.queryByRole('region')).toBeNull();
  });

  it('fades the edges that have more content and hints once, until the first scroll', () => {
    overflowing();
    const { container, unmount } = renderScroller();
    const wrapper = container.firstElementChild as HTMLElement;
    const viewport = screen.getByRole('region', { name: 'Stops table' });

    expect(wrapper.hasAttribute('data-fade-left')).toBe(false);
    expect(wrapper.hasAttribute('data-fade-right')).toBe(true);
    expect(screen.getByText('Scroll for more columns')).toBeTruthy();
    expect(viewport.tabIndex).toBe(0);

    viewport.scrollLeft = 600;
    fireEvent.scroll(viewport);

    expect(wrapper.hasAttribute('data-fade-left')).toBe(true);
    expect(wrapper.hasAttribute('data-fade-right')).toBe(false);
    expect(screen.queryByText('Scroll for more columns')).toBeNull();

    unmount();
    renderScroller();
    expect(screen.queryByText('Scroll for more columns')).toBeNull(); // one time only, remembered across mounts
  });
});
