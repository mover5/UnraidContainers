// Project documents: validation and the field-level merge. The client runs the
// same merge (src/lib/merge.ts) — keep the two in step.

export const SYNC_FIELDS = ['name', 'description', 'notes', 'colors', 'steps', 'rows_done', 'status', 'deleted'];

const str = (v, max) => (typeof v === 'string' ? v.slice(0, max) : '');
const int = (v, min, max, dflt) => {
  const n = Math.round(Number(v));
  return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : dflt;
};
const ID = /^[A-Za-z0-9-]{1,64}$/;
const HEX = /^#[0-9a-fA-F]{6}$/;

// A device whose clock runs ahead would otherwise win every merge until real
// time catches up. Cap stamps at the server's clock plus a little skew.
export const MAX_CLOCK_SKEW_MS = 10 * 60 * 1000;

export const isValidId = (id) => typeof id === 'string' && ID.test(id);

/** Coerce an incoming document into a well-formed project, or null if unusable. */
export function sanitize(doc, id) {
  if (!doc || typeof doc !== 'object' || !isValidId(id)) return null;
  const colors = (Array.isArray(doc.colors) ? doc.colors : [])
    .slice(0, 200)
    .filter((c) => c && isValidId(c.id))
    .map((c) => ({ id: c.id, name: str(c.name, 80), hex: HEX.test(c.hex) ? c.hex.toLowerCase() : '#888888' }));
  const steps = (Array.isArray(doc.steps) ? doc.steps : [])
    .slice(0, 5000)
    .filter((s) => s && isValidId(s.id))
    .map((s) => ({
      id: s.id,
      rows: int(s.rows, 1, 100000, 1),
      color_id: isValidId(s.color_id) ? s.color_id : null,
      text: str(s.text, 2000),
    }));
  const stamps = {};
  const maxStamp = Date.now() + MAX_CLOCK_SKEW_MS;
  for (const f of SYNC_FIELDS) stamps[f] = int(doc.stamps?.[f], 0, maxStamp, 0);
  return {
    id,
    name: str(doc.name, 200),
    description: str(doc.description, 5000),
    notes: str(doc.notes, 20000),
    colors,
    steps,
    rows_done: int(doc.rows_done, 0, 10_000_000, 0),
    status: doc.status === 'finished' ? 'finished' : 'active',
    deleted: doc.deleted === true,
    created_at: int(doc.created_at, 0, maxStamp, Date.now()),
    stamps,
  };
}

/** Newest value wins per field; ties go to `b`. */
export function merge(a, b) {
  const out = { ...b, stamps: { ...b.stamps } };
  for (const f of SYNC_FIELDS) {
    const ta = a.stamps?.[f] ?? 0;
    const tb = b.stamps?.[f] ?? 0;
    if (ta > tb) {
      out[f] = a[f];
      out.stamps[f] = ta;
    }
  }
  out.created_at = Math.min(a.created_at || Infinity, b.created_at || Infinity) || Date.now();
  return out;
}

export const updatedAt = (p) => Math.max(0, ...SYNC_FIELDS.map((f) => p.stamps?.[f] ?? 0));
