// REST client for the Flight Tracker backend. The base URL is set at build
// time via VITE_API_URL (the Docker image bakes in "/api"). When it's unset,
// the app runs in local-only mode (browser storage, no backend).
import type { Flight, FlightNote } from './types';

export const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
export const isRemote = Boolean(import.meta.env.VITE_API_URL);

interface HttpError extends Error {
  status?: number;
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(API_URL + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    // 4xx is permanent (bad data); 5xx / network failures are retryable.
    const err: HttpError = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  listFlights: () => req<Flight[]>('/flights'),
  listNotes: () => req<FlightNote[]>('/notes'),
  upsertFlight: (f: Flight) => req<Flight>(`/flights/${f.id}`, { method: 'PUT', body: JSON.stringify(f) }),
  deleteFlight: (id: string) => req<void>(`/flights/${id}`, { method: 'DELETE' }),
  upsertNote: (n: FlightNote) => req<FlightNote>(`/notes/${n.id}`, { method: 'PUT', body: JSON.stringify(n) }),
  deleteNote: (id: string) => req<void>(`/notes/${id}`, { method: 'DELETE' }),
};
