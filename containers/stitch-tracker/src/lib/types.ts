// A yarn color in a project's palette.
export interface YarnColor {
  id: string;
  name: string;
  hex: string; // "#rrggbb"
}

// One block of the pattern: N rows worked the same way, optionally in a color
// and/or with an instruction ("8 Purple", "Row 5: k2, p2 across").
export interface Step {
  id: string;
  rows: number; // >= 1
  color_id: string | null;
  text: string; // per-row instruction; may be empty
}

export type ProjectStatus = 'active' | 'finished';

// The fields that sync independently. Each has its own last-modified stamp, so
// counting rows on the phone offline doesn't clobber an edit to the notes made
// on another device (and vice versa) — the newest write wins per field.
export const SYNC_FIELDS = ['name', 'description', 'notes', 'colors', 'steps', 'rows_done', 'status', 'deleted'] as const;
export type SyncField = (typeof SYNC_FIELDS)[number];

export interface Project {
  id: string;
  name: string;
  description: string;
  notes: string; // basic notes / instructions (cast on, stitch, gauge…)
  colors: YarnColor[];
  steps: Step[];
  rows_done: number; // rows completed across the whole pattern
  status: ProjectStatus;
  deleted: boolean; // tombstone so deletes sync too
  created_at: number; // ms epoch
  stamps: Record<SyncField, number>; // ms epoch per field
}
