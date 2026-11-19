// Local-first project store. The UI reads and writes only this (instant, works
// offline); every write stamps the changed fields and marks the project dirty
// so the sync engine can push it when the server is reachable.
import { mergeProjects } from './merge.ts';
import { SYNC_FIELDS, type Project, type SyncField } from './types.ts';
import { uuid } from './uuid.ts';

const PROJECTS_KEY = 'st.projects.v1';
const DIRTY_KEY = 'st.dirty.v1';

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or blocked: the in-memory copy still works for this session.
  }
}

let all: Project[] = read<Project[]>(PROJECTS_KEY, []);
let dirty = new Set<string>(read<string[]>(DIRTY_KEY, []));
let visible: Project[] = computeVisible();

function computeVisible() {
  return all.filter((p) => !p.deleted);
}

const listeners = new Set<() => void>();
export function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const localWriteListeners = new Set<() => void>();
/** Fires only for edits made on this device (not for sync results). */
export function onLocalWrite(fn: () => void): () => void {
  localWriteListeners.add(fn);
  return () => localWriteListeners.delete(fn);
}

function commit(local = false) {
  write(PROJECTS_KEY, all);
  write(DIRTY_KEY, [...dirty]);
  visible = computeVisible();
  listeners.forEach((l) => l());
  if (local) localWriteListeners.forEach((l) => l());
}

// Stamps must strictly increase on this device even if two writes land in the same ms.
let lastStamp = 0;
function stamp(): number {
  lastStamp = Math.max(Date.now(), lastStamp + 1);
  return lastStamp;
}

export type Editable = Pick<Project, Exclude<SyncField, 'deleted'>>;

export const getProjects = () => visible;
export const getProject = (id: string) => all.find((p) => p.id === id && !p.deleted) ?? null;

export function createProject(data: Partial<Editable> & { name: string }): Project {
  const t = stamp();
  const p: Project = {
    id: uuid(),
    description: '',
    notes: '',
    colors: [],
    steps: [],
    rows_done: 0,
    status: 'active',
    ...data,
    deleted: false,
    created_at: t,
    stamps: Object.fromEntries(SYNC_FIELDS.map((f) => [f, t])) as Project['stamps'],
  };
  all = [...all, p];
  dirty.add(p.id);
  commit(true);
  return p;
}

export function updateProject(id: string, patch: Partial<Editable> | { deleted: true }) {
  const t = stamp();
  all = all.map((p) => {
    if (p.id !== id) return p;
    const next = { ...p, ...patch, stamps: { ...p.stamps } } as Project;
    for (const k of Object.keys(patch) as SyncField[]) next.stamps[k] = t;
    return next;
  });
  dirty.add(id);
  commit(true);
}

export const deleteProject = (id: string) => updateProject(id, { deleted: true });

// ---- used by the sync engine ----

export const dirtyIds = () => [...dirty];
export const getRaw = (id: string) => all.find((p) => p.id === id) ?? null;
/**
 * Accept the server's copy of a project as-is (used after a successful push
 * when nothing changed locally meanwhile — e.g. the server capped a stamp from
 * a fast clock, which would otherwise look like an unsynced local change forever).
 */
export function replaceFromServer(doc: Project) {
  all = all.some((p) => p.id === doc.id) ? all.map((p) => (p.id === doc.id ? doc : p)) : [...all, doc];
  dirty.delete(doc.id);
  commit();
}

export function clearDirty(id: string) {
  dirty.delete(id);
  commit();
}

/**
 * Fold server copies into the local store. A project stays dirty only if this
 * device still holds a field newer than what the server has.
 */
export function absorb(serverDocs: Project[], { full }: { full: boolean }) {
  const byId = new Map(all.map((p) => [p.id, p]));
  for (const s of serverDocs) {
    const local = byId.get(s.id);
    const merged = local ? mergeProjects(local, s) : s;
    byId.set(s.id, merged);
    const ahead = SYNC_FIELDS.some((f) => (merged.stamps[f] ?? 0) > (s.stamps?.[f] ?? 0));
    if (ahead) dirty.add(s.id);
    else dirty.delete(s.id);
  }
  if (full) {
    // Anything the server doesn't know about (e.g. a restored DB) gets re-sent.
    const seen = new Set(serverDocs.map((s) => s.id));
    for (const id of byId.keys()) if (!seen.has(id)) dirty.add(id);
  }
  all = [...byId.values()];
  commit();
}
