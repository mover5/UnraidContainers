import type { Flight, ClockTime, EventKey } from './types';

/** Parse "HH:MM" -> minutes since midnight, or null. */
export function toMinutes(t: ClockTime): number | null {
  if (!t) return null;
  const m = /^(\d{1,2}):(\d{2})$/.exec(t.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h > 23 || min > 59) return null;
  return h * 60 + min;
}

/** Current local time as "HH:MM". */
export function nowClock(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/**
 * Elapsed minutes from start to end, assuming end is the same or next day.
 * Wraps past midnight (end < start => +24h). Both times share one timezone.
 */
export function elapsed(start: ClockTime, end: ClockTime): number | null {
  const a = toMinutes(start);
  const b = toMinutes(end);
  if (a === null || b === null) return null;
  let diff = b - a;
  if (diff < 0) diff += 1440;
  return diff;
}

/**
 * Signed difference for delays (end - start) where a small negative means
 * "early". Wraps only for clear midnight crossings (> 12h apart).
 */
export function signedDiff(start: ClockTime, end: ClockTime): number | null {
  const a = toMinutes(start);
  const b = toMinutes(end);
  if (a === null || b === null) return null;
  let diff = b - a;
  if (diff < -720) diff += 1440;
  if (diff > 720) diff -= 1440;
  return diff;
}

// ---- Derived per-flight metrics (all in minutes unless noted) ----

/** Taxi-out: gate push -> takeoff (same airport, same tz). */
export const taxiOut = (f: Flight) => elapsed(f.gate_push, f.takeoff);

/** Taxi-in: land -> gate arrive (same airport, same tz). */
export const taxiIn = (f: Flight) => elapsed(f.land, f.gate_arrive);

/** Air time: takeoff -> land, corrected for the timezone change. */
export function airTime(f: Flight): number | null {
  const raw = elapsed(f.takeoff, f.land);
  if (raw === null) return null;
  return raw - f.tz_change * 60;
}

/** Block time (gate to gate): gate push -> gate arrive, tz-corrected. */
export function blockTime(f: Flight): number | null {
  const raw = elapsed(f.gate_push, f.gate_arrive);
  if (raw === null) return null;
  return raw - f.tz_change * 60;
}

/** Actual time the plane left the gate (delayed push if present). */
export const actualDeparture = (f: Flight): ClockTime => f.gate_push ?? f.delayed_departure ?? null;

/** Departure delay vs schedule (positive = late leaving the gate). */
export const departureDelay = (f: Flight) => signedDiff(f.scheduled_departure, actualDeparture(f));

/** Arrival delay vs schedule (positive = late to the gate). */
export const arrivalDelay = (f: Flight) => signedDiff(f.scheduled_arrival, f.gate_arrive);

/**
 * Parse a free-text duration estimate ("2h8m", "40m", "3h", "1h28m", and the
 * odd un-suffixed "4h11") into minutes, or null for blanks / "n/a" / garbage.
 */
export function parseDuration(s: string | null | undefined): number | null {
  if (!s) return null;
  const t = s.toLowerCase().replace(/\s+/g, '');
  const m = /^(?:(\d+)h)?(\d+)?m?$/.exec(t);
  if (!m || (m[1] === undefined && m[2] === undefined)) return null;
  return (m[1] ? Number(m[1]) : 0) * 60 + (m[2] ? Number(m[2]) : 0);
}

/** Airline/pilot projected air time, in minutes. */
export const projectedMinutes = (f: Flight) => parseDuration(f.projected_flying_time);

/**
 * Actual air time minus the projected estimate (positive = the flight took
 * longer than projected). null if either the estimate or air time is missing.
 */
export function vsProjected(f: Flight): number | null {
  const actual = airTime(f);
  const proj = projectedMinutes(f);
  if (actual === null || proj === null) return null;
  return actual - proj;
}

/** Format minutes -> "1h42m" / "42m" / "-12m". */
export function fmtDuration(min: number | null | undefined): string {
  if (min === null || min === undefined || Number.isNaN(min)) return '—';
  const sign = min < 0 ? '-' : '';
  const a = Math.abs(Math.round(min));
  const h = Math.floor(a / 60);
  const m = a % 60;
  if (h === 0) return `${sign}${m}m`;
  return `${sign}${h}h${String(m).padStart(2, '0')}m`;
}

/** Format a signed delay with an explicit + for late. */
export function fmtDelay(min: number | null | undefined): string {
  if (min === null || min === undefined || Number.isNaN(min)) return '—';
  if (min === 0) return 'on time';
  return (min > 0 ? '+' : '') + fmtDuration(min);
}

/** A flight is "complete" once it has reached the gate at destination. */
export const isComplete = (f: Flight) => Boolean(f.gate_arrive);

// ---- Timezone-aware stamping ----

const fromMinutes = (m: number): string => {
  const w = ((Math.round(m) % 1440) + 1440) % 1440;
  return `${String(Math.floor(w / 60)).padStart(2, '0')}:${String(w % 60).padStart(2, '0')}`;
};

/** Typical taxi allowances used only to estimate when an event "should" happen. */
const TAXI_OUT_EST = 15;
const TAXI_IN_EST = 8;

/**
 * Best guess at when an event should happen, in that event's local time
 * (origin for push/takeoff, destination for land/arrive). Prefers anchoring
 * on the previous logged event, falling back to the schedule. null if unknown.
 */
export function expectedClock(f: Flight, key: EventKey): number | null {
  const dep = toMinutes(f.delayed_departure ?? f.scheduled_departure);
  const arr = toMinutes(f.delayed_arrival ?? f.scheduled_arrival);
  const push = toMinutes(f.gate_push);
  const off = toMinutes(f.takeoff);
  const land = toMinutes(f.land);
  const proj = projectedMinutes(f);
  switch (key) {
    case 'gate_push':
      return dep;
    case 'takeoff':
      if (push !== null) return push + TAXI_OUT_EST;
      return dep !== null ? dep + TAXI_OUT_EST : null;
    case 'land':
      if (off !== null && proj !== null) return off + proj + f.tz_change * 60;
      return arr !== null ? arr - TAXI_IN_EST : null;
    case 'gate_arrive':
      if (land !== null) return land + TAXI_IN_EST;
      return arr;
  }
}

/**
 * Pick the clock time to stamp for an event, correcting for a phone that
 * hasn't switched timezones yet (landing / reaching the gate while it still
 * shows origin time). Push and takeoff happen at the origin, where the phone
 * is already right, so they're never shifted — that also keeps an unlogged
 * departure delay from being mistaken for a TZ error. For destination events
 * the only shift considered is +tz_change rounded to whole hours (minutes never
 * change), and it's applied only when it lands clearly closer (>30m) to the
 * expected time than the raw clock does. Returns the clock and hours shifted.
 */
export function smartStamp(f: Flight, key: EventKey, now: string = nowClock()): { value: string; shiftHours: number } {
  const keep = { value: now, shiftHours: 0 };
  if (key !== 'land' && key !== 'gate_arrive') return keep;
  const raw = toMinutes(now);
  const expected = expectedClock(f, key);
  const tz = Math.round(f.tz_change);
  if (raw === null || expected === null || tz === 0) return keep;

  const dist = (m: number) => Math.abs(signedDiff(fromMinutes(expected), fromMinutes(m))!);
  const shifted = raw + tz * 60;
  if (dist(shifted) < dist(raw) - 30) return { value: fromMinutes(shifted), shiftHours: tz };
  return keep;
}
