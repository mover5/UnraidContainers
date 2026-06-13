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
  return read<Flight[]>(FLIGHTS_KEY, []);
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
