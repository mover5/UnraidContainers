import type { Flight } from './types';
import {
  airTime,
  arrivalDelay,
  blockTime,
  departureDelay,
  isComplete,
  taxiIn,
  taxiOut,
} from './time';

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const nums = (xs: (number | null)[]) => xs.filter((x): x is number => x !== null);

/** Sorted, de-duplicated list of every person who appears on any flight. */
export function allPeople(flights: Flight[]): string[] {
  return [...new Set(flights.flatMap((f) => f.passengers))].sort((a, b) => a.localeCompare(b));
}

export interface Summary {
  total: number;
  completed: number;
  upcoming: number;
  avgTaxiOut: number | null;
  avgDepDelay: number | null;
  onTimeRate: number | null; // share with dep delay <= 15m
  totalAir: number | null; // minutes
  uniqueAirports: number;
  longest: Flight | null;
}

export function summary(flights: Flight[]): Summary {
  const done = flights.filter(isComplete);
  const depDelays = nums(done.map(departureDelay));
  const airs = done.map((f) => ({ f, a: airTime(f) }));
  const longest = airs.reduce<{ f: Flight; a: number | null } | null>(
    (best, cur) => (cur.a !== null && (!best || (best.a ?? -1) < cur.a) ? cur : best),
    null
  );
  return {
    total: flights.length,
    completed: done.length,
    upcoming: flights.length - done.length,
    avgTaxiOut: avg(nums(done.map(taxiOut))),
    avgDepDelay: avg(depDelays),
    onTimeRate: depDelays.length ? depDelays.filter((d) => d <= 15).length / depDelays.length : null,
    totalAir: nums(done.map(airTime)).reduce((a, b) => a + b, 0) || null,
    uniqueAirports: new Set(flights.flatMap((f) => [f.origin, f.destination])).size,
    longest: longest?.f ?? null,
  };
}

export interface AirportTaxi {
  airport: string;
  taxiOut: number | null;
  taxiIn: number | null;
  n: number;
}

/** Average taxi-out (as origin) and taxi-in (as destination) per airport. */
export function taxiByAirport(flights: Flight[], minSamples = 1): AirportTaxi[] {
  const out = new Map<string, number[]>();
  const inn = new Map<string, number[]>();
  const push = (m: Map<string, number[]>, k: string, v: number | null) => {
    if (v === null) return;
    m.set(k, [...(m.get(k) ?? []), v]);
  };
  for (const f of flights) {
    push(out, f.origin, taxiOut(f));
    push(inn, f.destination, taxiIn(f));
  }
  const airports = new Set([...out.keys(), ...inn.keys()]);
  return [...airports]
    .map((airport) => ({
      airport,
      taxiOut: avg(out.get(airport) ?? []),
      taxiIn: avg(inn.get(airport) ?? []),
      n: (out.get(airport)?.length ?? 0) + (inn.get(airport)?.length ?? 0),
    }))
    .filter((a) => a.n >= minSamples)
    .sort((a, b) => (b.taxiOut ?? 0) - (a.taxiOut ?? 0));
}

export interface CarrierStat {
  carrier: string;
  n: number;
  avgDepDelay: number | null;
  avgArrDelay: number | null;
  onTimeRate: number | null;
}

export function byCarrier(flights: Flight[]): CarrierStat[] {
  const groups = new Map<string, Flight[]>();
  for (const f of flights) groups.set(f.carrier, [...(groups.get(f.carrier) ?? []), f]);
  return [...groups.entries()]
    .map(([carrier, fs]) => {
      const dep = nums(fs.map(departureDelay));
      return {
        carrier,
        n: fs.length,
        avgDepDelay: avg(dep),
        avgArrDelay: avg(nums(fs.map(arrivalDelay))),
        onTimeRate: dep.length ? dep.filter((d) => d <= 15).length / dep.length : null,
      };
    })
    .sort((a, b) => b.n - a.n);
}

/** Per-completed-flight series for the delay-over-time chart. */
export function delayTrend(flights: Flight[]) {
  return flights
    .filter(isComplete)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((f) => ({
      date: f.date,
      label: `${f.origin}→${f.destination}`,
      depDelay: departureDelay(f),
      arrDelay: arrivalDelay(f),
    }));
}

export interface RouteStat {
  route: string;
  n: number;
  avgAir: number | null;
  avgBlock: number | null;
}

export function byRoute(flights: Flight[]): RouteStat[] {
  const groups = new Map<string, Flight[]>();
  for (const f of flights) {
    const key = `${f.origin}→${f.destination}`;
    groups.set(key, [...(groups.get(key) ?? []), f]);
  }
  return [...groups.entries()]
    .map(([route, fs]) => ({
      route,
      n: fs.length,
      avgAir: avg(nums(fs.map(airTime))),
      avgBlock: avg(nums(fs.map(blockTime))),
    }))
    .sort((a, b) => b.n - a.n);
}
