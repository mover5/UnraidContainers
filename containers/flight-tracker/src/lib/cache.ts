// Local-first cache. The single source of truth the UI reads from; it works
// fully offline. In remote mode the sync layer reconciles it with the backend.
import seed from '../data/seedFlights.json';
import type { Flight, FlightNote } from './types';
import { isRemote } from './api';

const FLIGHTS_KEY = 'ft.flights.v1';
const NOTES_KEY = 'ft.notes.v1';

type Listener = () => void;
const listeners = new Set<Listener>();

/** Subscribe to cache changes (writes and pulls). Returns an unsubscribe fn. */
export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function notify() {
  listeners.forEach((l) => l());
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

/** Split a free-text passenger value ("Janelle + Mark") into individual names. */
export function splitPeople(v: string): string[] {
  return v.split(/\s*[+,&/]\s*/).map((s) => s.trim()).filter(Boolean);
}

// Older caches/records stored passengers as a single string. Coerce to string[]
// on read so the rest of the app can treat it uniformly.
function normalizeFlight(f: Flight): Flight {
  if (Array.isArray(f.passengers)) return f;
  return { ...f, passengers: splitPeople((f as unknown as { passengers?: string }).passengers ?? '') };
}

let seeded = false;
function ensureSeed() {
  if (seeded) return;
  seeded = true;
  // Only seed locally when there's no backend. In remote mode the cache is
  // filled by the first pull(); the Postgres DB is the source of truth.
  if (!isRemote && localStorage.getItem(FLIGHTS_KEY) === null) {
    localStorage.setItem(FLIGHTS_KEY, JSON.stringify(seed as Flight[]));
  }
}

export function getFlights(): Flight[] {
  ensureSeed();
  return read<Flight[]>(FLIGHTS_KEY, []).map(normalizeFlight);
}
export function setFlights(flights: Flight[]) {
  localStorage.setItem(FLIGHTS_KEY, JSON.stringify(flights));
  notify();
}

export function getNotes(): FlightNote[] {
  return read<FlightNote[]>(NOTES_KEY, []);
}
export function setNotes(notes: FlightNote[]) {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
  notify();
}
