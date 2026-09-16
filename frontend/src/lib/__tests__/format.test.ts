import { describe, expect, it } from 'vitest';

import { durationLabel, hoursToHHMM, milesLabel, minutesToClock } from '../format';

describe('hoursToHHMM', () => {
  it.each([
    [0, '0:00'],
    [0.25, '0:15'],
    [7.75, '7:45'],
    [10, '10:00'],
    [24, '24:00'],
    [70, '70:00'],
    [1.9999, '2:00'], // rounds to the nearest minute, carrying into the hour
    [-1.25, '-1:15'],
    [-0.001, '0:00'], // no negative zero
  ])('%s hours -> %s', (hours, expected) => {
    expect(hoursToHHMM(hours)).toBe(expected);
  });

  it('round-trips every 15-minute value of a day', () => {
    for (let minutes = 0; minutes <= 1440; minutes += 15) {
      const [h, m] = hoursToHHMM(minutes / 60).split(':').map(Number);
      expect((h as number) * 60 + (m as number)).toBe(minutes);
    }
  });
});

describe('minutesToClock', () => {
  it.each([
    [0, '00:00'],
    [15, '00:15'],
    [390, '06:30'],
    [720, '12:00'],
    [1425, '23:45'],
    [1440, '24:00'], // the end of the log day, not the next midnight
  ])('%s -> %s', (minutes, expected) => {
    expect(minutesToClock(minutes)).toBe(expected);
  });

  it('round-trips every minute of a day', () => {
    for (let minutes = 0; minutes <= 1440; minutes += 1) {
      const [h, m] = minutesToClock(minutes).split(':').map(Number);
      expect((h as number) * 60 + (m as number)).toBe(minutes);
    }
  });
});

describe('milesLabel', () => {
  it.each([
    [0, '0 mi'],
    [0.5, '0.5 mi'],
    [7.25, '7.3 mi'],
    [9.96, '10 mi'],
    [10.4, '10 mi'],
    [605, '605 mi'],
    [1234.6, '1,235 mi'],
  ])('%s -> %s', (miles, expected) => {
    expect(milesLabel(miles)).toBe(expected);
  });
});

describe('durationLabel', () => {
  it.each([
    [0, '0 min'],
    [0.25, '15 min'],
    [0.5, '30 min'],
    [1, '1 h'],
    [10, '10 h'],
    [10.5, '10 h 30 min'],
    [34, '34 h'],
    [0.9999, '1 h'],
  ])('%s hours -> %s', (hours, expected) => {
    expect(durationLabel(hours)).toBe(expected);
  });

  it('agrees with hoursToHHMM on every quarter hour up to a 34-hour restart', () => {
    for (let minutes = 0; minutes <= 2040; minutes += 15) {
      const [h, m] = hoursToHHMM(minutes / 60).split(':').map(Number);
      const expected = h === 0 ? `${m} min` : m === 0 ? `${h} h` : `${h} h ${m} min`;
      expect(durationLabel(minutes / 60)).toBe(expected);
    }
  });
});
