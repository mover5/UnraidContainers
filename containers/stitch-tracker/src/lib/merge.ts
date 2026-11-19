import { SYNC_FIELDS, type Project } from './types.ts';

/**
 * Field-level last-write-wins merge of two copies of the same project. Ties go
 * to `b`. The server runs the same rule (server/merge.js) — keep them in step.
 */
export function mergeProjects(a: Project, b: Project): Project {
  const out = { ...b, stamps: { ...b.stamps } } as Project;
  for (const f of SYNC_FIELDS) {
    const ta = a.stamps?.[f] ?? 0;
    const tb = b.stamps?.[f] ?? 0;
    if (ta > tb) {
      (out as unknown as Record<string, unknown>)[f] = a[f];
      out.stamps[f] = ta;
    }
  }
  out.created_at = Math.min(a.created_at || Infinity, b.created_at || Infinity) || Date.now();
  return out;
}

/** Most recent change to any field. */
export const updatedAt = (p: Project) => Math.max(0, ...SYNC_FIELDS.map((f) => p.stamps?.[f] ?? 0));
