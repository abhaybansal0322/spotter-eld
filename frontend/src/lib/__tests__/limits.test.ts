import { describe, expect, it } from 'vitest';

import { API_LIMITS } from '../../test/fixtures';
import { InvalidLimitsError, parseLimits } from '../limits';

describe('parseLimits', () => {
  it('narrows a valid API object to exactly the required keys', () => {
    expect(parseLimits(API_LIMITS)).toEqual({
      minutes_per_day: 1440,
      minutes_per_hour: 60,
      grid_resolution_min: 15,
      cycle_limit_min: 4200,
      drive_limit_min: 660,
      window_limit_min: 840,
      break_after_drive_min: 480,
      break_duration_min: 30,
      qualifying_rest_min: 600,
      cycle_days: 8,
    });
  });

  it('names a missing key', () => {
    const { grid_resolution_min: _missing, ...incomplete } = API_LIMITS;

    expect(() => parseLimits(incomplete)).toThrow(InvalidLimitsError);
    expect(() => parseLimits(incomplete)).toThrow('limit "grid_resolution_min" is missing');
  });

  it.each([
    ['a string', '1440'],
    ['null', null],
    ['NaN', Number.NaN],
    ['zero', 0],
  ])('rejects %s', (_case, value) => {
    const bad = { ...API_LIMITS, minutes_per_day: value } as unknown as typeof API_LIMITS;

    expect(() => parseLimits(bad)).toThrow('limit "minutes_per_day" must be a positive number');
  });
});
