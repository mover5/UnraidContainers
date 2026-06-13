// Local-first data API used by the UI. Every read and write goes to the local
// cache (instant, offline-capable); in cloud mode each write also enqueues an
// outbox op that the sync engine replays to the backend API when online.
import * as cache from './cache';
import { enqueue, purgeNoteOps } from './sync';
import type { Flight, FlightNote, NewFlight } from './types';

export { isRemote } from './api';
export { subscribe } from './cache';

const uuid = () => crypto.randomUUID();

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
