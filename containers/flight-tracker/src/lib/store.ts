// Local-first data API used by the UI. Every read and write goes to the local
// cache (instant, offline-capable); in cloud mode each write also enqueues an
// outbox op that the sync engine replays to the backend API when online.
import * as cache from './cache';
import { enqueue, purgeNoteOps } from './sync';
import type { Flight, FlightNote, NewFlight } from './types';

export { isRemote } from './api';
export { subscribe } from './cache';

// crypto.randomUUID() is only exposed in secure contexts (HTTPS or
// http://localhost). When the app is served over plain HTTP to a LAN/Tailscale
// IP it's undefined, so fall back to a v4 UUID built from getRandomValues
// (available in insecure contexts), then Math.random as a last resort.
function uuid(): string {
  const c = globalThis.crypto;
  if (c?.randomUUID) return c.randomUUID();
  const bytes = new Uint8Array(16);
  if (c?.getRandomValues) c.getRandomValues(bytes);
  else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant
  const h = [...bytes].map((b) => b.toString(16).padStart(2, '0'));
  return `${h[0]}${h[1]}${h[2]}${h[3]}-${h[4]}${h[5]}-${h[6]}${h[7]}-${h[8]}${h[9]}-${h[10]}${h[11]}${h[12]}${h[13]}${h[14]}${h[15]}`;
}

export const store = {
  async listFlights(): Promise<Flight[]> {
    return [...cache.getFlights()].sort((a, b) => a.date.localeCompare(b.date));
  },

  async getFlight(id: string): Promise<Flight | null> {
    return cache.getFlights().find((f) => f.id === id) ?? null;
  },

  async createFlight(data: NewFlight): Promise<Flight> {
    const flight: Flight = { ...data, id: uuid() };
    cache.setFlights([...cache.getFlights(), flight]);
    enqueue({ kind: 'flight.upsert', id: flight.id });
    return flight;
  },

  async updateFlight(id: string, patch: Partial<Flight>): Promise<Flight> {
    const next = cache.getFlights().map((f) => (f.id === id ? { ...f, ...patch, id } : f));
    cache.setFlights(next);
    enqueue({ kind: 'flight.upsert', id });
    return next.find((f) => f.id === id)!;
  },

  async deleteFlight(id: string): Promise<void> {
    const noteIds = cache.getNotes().filter((n) => n.flight_id === id).map((n) => n.id);
    cache.setFlights(cache.getFlights().filter((f) => f.id !== id));
    cache.setNotes(cache.getNotes().filter((n) => n.flight_id !== id));
    purgeNoteOps(noteIds); // server cascade handles their deletion
    enqueue({ kind: 'flight.delete', id });
  },

  async listNotes(flightId: string): Promise<FlightNote[]> {
    return cache
      .getNotes()
      .filter((n) => n.flight_id === flightId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  async addNote(flightId: string, body: string): Promise<FlightNote> {
    const note: FlightNote = {
      id: uuid(),
      flight_id: flightId,
      body,
      created_at: new Date().toISOString(),
    };
    cache.setNotes([...cache.getNotes(), note]);
    enqueue({ kind: 'note.upsert', id: note.id });
    return note;
  },

  async deleteNote(id: string): Promise<void> {
    cache.setNotes(cache.getNotes().filter((n) => n.id !== id));
    enqueue({ kind: 'note.delete', id });
  },
};
