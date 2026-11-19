// Sync engine: pushes dirty projects to the server and pulls everyone else's
// changes. Runs on load, when the browser comes back online, when the app is
// reopened, shortly after each edit, and every 30s while anything is pending.
import * as store from './store.ts';
import type { Project } from './types.ts';

export const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
export const isRemote = Boolean(import.meta.env.VITE_API_URL);

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
  pending: store.dirtyIds().length,
  syncing: false,
  lastError: null,
  lastSyncedAt: null,
};
const listeners = new Set<() => void>();
export const getStatus = () => status;
export function subscribeStatus(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function emit(patch: Partial<SyncStatus> = {}) {
  status = { ...status, online: online(), pending: store.dirtyIds().length, ...patch };
  listeners.forEach((l) => l());
}

class HttpError extends Error {
  constructor(public status: number) {
    super(`Server said ${status}`);
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(API_URL + path, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!res.ok) throw new HttpError(res.status);
  return (await res.json()) as T;
}

let running: Promise<void> | null = null;
let again = false;

/** Push everything dirty, then pull. Concurrent calls coalesce into one extra pass. */
export function sync(): Promise<void> {
  if (!isRemote) return Promise.resolve();
  if (running) {
    again = true;
    return running;
  }
  running = (async () => {
    do {
      again = false;
      await pass();
    } while (again && online());
  })().finally(() => {
    running = null;
  });
  return running;
}

async function pass() {
  if (!online()) return emit();
  emit({ syncing: true });
  try {
    for (const id of store.dirtyIds()) {
      const doc = store.getRaw(id);
      if (!doc) continue;
      try {
        const saved = await req<Project>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(doc) });
        store.absorb([saved], { full: false });
      } catch (e) {
        // A 4xx means the server will never accept this copy; don't retry forever.
        if (e instanceof HttpError && e.status >= 400 && e.status < 500) {
          store.clearDirty(id);
          emit({ lastError: `Couldn't save “${doc.name}”: ${e.message}` });
          continue;
        }
        throw e;
      }
    }
    store.absorb(await req<Project[]>('/projects'), { full: true });
    emit({ syncing: false, lastError: null, lastSyncedAt: Date.now() });
  } catch (e) {
    // Network failure / server down: keep everything queued for the next try.
    emit({ syncing: false, lastError: e instanceof Error ? e.message : 'Sync failed' });
  }
}

let timer: ReturnType<typeof setTimeout> | undefined;
function soon(delay = 700) {
  clearTimeout(timer);
  timer = setTimeout(() => void sync(), delay);
}

if (isRemote && typeof window !== 'undefined') {
  store.subscribe(() => emit());
  store.onLocalWrite(() => soon());
  window.addEventListener('online', () => void sync());
  window.addEventListener('offline', () => emit());
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void sync();
  });
  setInterval(() => {
    if (online() && store.dirtyIds().length) void sync();
  }, 30_000);
  void sync();
}
