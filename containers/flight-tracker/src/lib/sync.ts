// Sync engine: replays queued local mutations ("outbox") to the backend API
// when online, and pulls fresh data down. Records carry client-generated ids
// and timestamps so an offline tag keeps the time it actually happened.
import { api, isRemote } from './api';
import * as cache from './cache';

const OUTBOX_KEY = 'ft.outbox.v1';

export type Op =
  | { kind: 'flight.upsert'; id: string }
  | { kind: 'flight.delete'; id: string }
  | { kind: 'note.upsert'; id: string }
  | { kind: 'note.delete'; id: string };

function readOutbox(): Op[] {
  try {
    return JSON.parse(localStorage.getItem(OUTBOX_KEY) || '[]') as Op[];
  } catch {
    return [];
  }
}
function writeOutbox(ops: Op[]) {
  localStorage.setItem(OUTBOX_KEY, JSON.stringify(ops));
  emitStatus();
}

// ---------------- status ----------------

export interface SyncStatus {
  remote: boolean;
  online: boolean;
  pending: number;
  syncing: boolean;
  lastError: string | null;
  lastSyncedAt: number | null;
}

const online = () => (typeof navigator === 'undefined' ? true : navigator.onLine);

let status: SyncStatus = {
  remote: isRemote,
  online: online(),
  pending: readOutbox().length,
  syncing: false,
  lastError: null,
  lastSyncedAt: null,
};

const statusListeners = new Set<(s: SyncStatus) => void>();
export function subscribeStatus(fn: (s: SyncStatus) => void): () => void {
  statusListeners.add(fn);
  fn(status);
  return () => statusListeners.delete(fn);
}
function emitStatus(patch: Partial<SyncStatus> = {}) {
  status = { ...status, online: online(), pending: readOutbox().length, ...patch };
  statusListeners.forEach((l) => l(status));
}

// ---------------- enqueue ----------------

export function enqueue(op: Op) {
  if (!isRemote) return;
  let ops = readOutbox();

  if (op.kind === 'flight.upsert' || op.kind === 'note.upsert') {
    // Coalesce: one pending upsert per record (flush reads current state).
    if (!ops.some((o) => o.kind === op.kind && o.id === op.id)) ops.push(op);
  } else if (op.kind === 'flight.delete') {
    ops = ops.filter((o) => !(o.kind === 'flight.upsert' && o.id === op.id));
    ops.push(op);
  } else if (op.kind === 'note.delete') {
    ops = ops.filter((o) => !(o.kind === 'note.upsert' && o.id === op.id));
    ops.push(op);
  }
  writeOutbox(ops);
  scheduleFlush();
}

/** Drop queued note ops for the given note ids (used when a flight is deleted). */
export function purgeNoteOps(noteIds: string[]) {
  if (!isRemote || noteIds.length === 0) return;
  const set = new Set(noteIds);
  writeOutbox(readOutbox().filter((o) => !(o.kind.startsWith('note.') && set.has(o.id))));
}

// ---------------- flush / pull ----------------

// A Postgres/HTTP error (has a code or 4xx status) is permanent: drop the op
// instead of retrying forever. A bare network failure is transient: keep it.
function isPermanent(e: unknown): boolean {
  const err = e as { code?: string; status?: number } | null;
  return Boolean(err && (err.code || (err.status && err.status >= 400 && err.status < 500)));
}

async function apply(op: Op): Promise<void> {
  if (op.kind === 'flight.upsert') {
    const f = cache.getFlights().find((x) => x.id === op.id);
    if (!f) return;
    await api.upsertFlight(f);
  } else if (op.kind === 'flight.delete') {
    await api.deleteFlight(op.id);
  } else if (op.kind === 'note.upsert') {
    const n = cache.getNotes().find((x) => x.id === op.id);
    if (!n) return;
    await api.upsertNote(n);
  } else if (op.kind === 'note.delete') {
    await api.deleteNote(op.id);
  }
}

let flushing = false;

export async function flush(): Promise<void> {
  if (!isRemote || !online() || flushing) return;
  flushing = true;
  emitStatus({ syncing: true, lastError: null });
  try {
    let ops = readOutbox();
    while (ops.length > 0) {
      const op = ops[0];
      try {
        await apply(op);
      } catch (e) {
        if (isPermanent(e)) {
          emitStatus({ lastError: e instanceof Error ? e.message : 'sync error' });
        } else {
          // transient (offline) — stop and keep the queue for later
          emitStatus({ syncing: false });
          return;
        }
      }
      ops = readOutbox().filter((o) => !(o.kind === op.kind && o.id === op.id));
      writeOutbox(ops);
    }
    emitStatus({ lastSyncedAt: Date.now() });
    await pull();
  } finally {
    flushing = false;
    emitStatus({ syncing: false });
  }
}

export async function pull(): Promise<void> {
  if (!isRemote || !online()) return;
  if (readOutbox().length > 0) return; // don't clobber un-synced local writes
  try {
    const [flights, notes] = await Promise.all([api.listFlights(), api.listNotes()]);
    cache.setFlights(flights);
    cache.setNotes(notes);
    emitStatus({ lastSyncedAt: Date.now() });
  } catch {
    // offline or server unreachable — keep the cached data
  }
}

let flushTimer: ReturnType<typeof setTimeout> | undefined;
export function scheduleFlush(delay = 800) {
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => void flush(), delay);
}

// ---------------- wiring ----------------

if (isRemote && typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    emitStatus({ online: true });
    void flush();
  });
  window.addEventListener('offline', () => emitStatus({ online: false }));
  void flush(); // initial sync / pull on load
  setInterval(() => {
    if (online() && readOutbox().length > 0) void flush();
  }, 30_000);
}
