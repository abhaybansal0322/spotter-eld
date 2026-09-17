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

/** Hours as the paper form writes them: 10 -> "10", 1.75 -> "1.75", 4.5 -> "4.5". Two decimals at most. */
export function hoursFigure(hours: number): string {
  return String(Number(hours.toFixed(2)));
}

/** "2021-04-09" -> { month: "04", day: "09", year: "2021" }. Split as text, so no time zone can shift the day. */
export function dateParts(isoDate: string): { month: string; day: string; year: string } {
  const [year = '', month = '', day = ''] = isoDate.split('-');
  return { month, day, year };
}

function terminalParts(iso: string, timeZone: string): Record<string, string> {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'short',
  }).formatToParts(new Date(iso));
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

/** An instant in the home terminal zone, dispatch style: "Wed 09/16 06:00". */
export function terminalTime(iso: string, timeZone: string): string {
  const p = terminalParts(iso, timeZone);
  return `${p.weekday} ${p.month}/${p.day} ${p.hour}:${p.minute}`;
}

/** The zone's abbreviation at that instant, e.g. "CDT". */
export function zoneAbbreviation(iso: string, timeZone: string): string {
  return terminalParts(iso, timeZone).timeZoneName ?? timeZone;
}

/** A calendar date for a tab: { weekday: "Wed", date: "Sep 16" }. Read as a date, so no zone can move it. */
export function calendarLabel(isoDate: string): { weekday: string; date: string } {
  const [year = 0, month = 1, day = 1] = isoDate.split('-').map(Number);
  const utc = new Date(Date.UTC(year, month - 1, day));
  return {
    weekday: new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short' }).format(utc),
    date: new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' }).format(utc),
  };
}

/** A mile marker with one decimal, so a column of them aligns on the point: 0 -> "0.0", 1234.56 -> "1,234.6". */
export function mileMarker(miles: number): string {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(miles);
}

/** Hours with two decimals for aligned columns, exact on the quarter hour: 7.75 -> "7.75", 70 -> "70.00". */
export function hoursFixed(hours: number): string {
  return hours.toFixed(2);
}
