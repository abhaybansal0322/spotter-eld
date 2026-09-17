import { describe, expect, it } from 'vitest';

import { spreadOverlapping } from '../stops';

describe('spreadOverlapping', () => {
  it('leaves pins that do not overlap where they are', () => {
    expect(spreadOverlapping([{ x: 0, y: 0 }, { x: 100, y: 0 }], 22, 18)).toEqual([{ dx: 0, dy: 0 }, { dx: 0, dy: 0 }]);
  });

  it('fans overlapping pins out on a circle, first one straight up, leaving others alone', () => {
    const offsets = spreadOverlapping([{ x: 0, y: 0 }, { x: 500, y: 500 }, { x: 5, y: 0 }], 22, 18);

    expect(offsets[0]).toEqual({ dx: 0, dy: -18 });
    expect(offsets[1]).toEqual({ dx: 0, dy: 0 });
    expect(offsets[2]).toEqual({ dx: 0, dy: 18 });
  });

  it('gives every member of a larger group its own position', () => {
    const offsets = spreadOverlapping([0, 1, 2, 3].map(() => ({ x: 10, y: 10 })), 22, 18);

    expect(new Set(offsets.map(({ dx, dy }) => `${dx},${dy}`)).size).toBe(4);
    expect(offsets.every(({ dx, dy }) => Math.round(Math.hypot(dx, dy)) === 18)).toBe(true);
  });
});
