// Pure display formatting. The 60 below is a unit conversion, not an HOS limit; limits arrive from the API.

const MINUTES_PER_HOUR = 60;

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/** 7.75 -> "7:45", 0.5 -> "0:30", -1.25 -> "-1:15". Rounds to the nearest minute. */
export function hoursToHHMM(hours: number): string {
  const totalMinutes = Math.round(Math.abs(hours) * MINUTES_PER_HOUR);
  const sign = hours < 0 && totalMinutes > 0 ? '-' : '';
  return `${sign}${Math.floor(totalMinutes / MINUTES_PER_HOUR)}:${pad2(totalMinutes % MINUTES_PER_HOUR)}`;
}

/** Minutes from midnight to a 24-hour clock: 390 -> "06:30". The end of the day, 1440, is "24:00". */
export function minutesToClock(minutes: number): string {
  const whole = Math.round(minutes);
  return `${pad2(Math.floor(whole / MINUTES_PER_HOUR))}:${pad2(whole % MINUTES_PER_HOUR)}`;
}

/** 605 -> "605 mi", 1234.4 -> "1,234 mi", 7.25 -> "7.3 mi". One decimal only under ten miles. */
export function milesLabel(miles: number): string {
  const digits = Math.abs(miles) < 10 ? 1 : 0;
  const formatted = new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(miles);
  return `${formatted} mi`;
}

/** 0.5 -> "30 min", 1 -> "1 h", 10.5 -> "10 h 30 min", 34 -> "34 h". Rounds to the nearest minute. */
export function durationLabel(hours: number): string {
  const totalMinutes = Math.round(hours * MINUTES_PER_HOUR);
  const wholeHours = Math.floor(totalMinutes / MINUTES_PER_HOUR);
  const minutes = totalMinutes % MINUTES_PER_HOUR;
  if (wholeHours === 0) {
    return `${minutes} min`;
  }
  return minutes === 0 ? `${wholeHours} h` : `${wholeHours} h ${minutes} min`;
}
