import type { Project, Step, YarnColor } from './types.ts';

export const totalRows = (p: Pick<Project, 'steps'>) => p.steps.reduce((n, s) => n + s.rows, 0);

/** First row (0-based) of each step. */
export function stepStarts(steps: Step[]): number[] {
  const out: number[] = [];
  let n = 0;
  for (const s of steps) {
    out.push(n);
    n += s.rows;
  }
  return out;
}

export interface Position {
  /** Index of the step the next row belongs to; -1 when there's no pattern or it's finished. */
  stepIndex: number;
  step: Step | null;
  /** 1-based row within the current step that you're about to knit. */
  rowInStep: number;
  /** 1-based overall row you're about to knit. */
  row: number;
  total: number;
  finished: boolean;
  /** You just moved into this step and its color differs from the previous one. */
  justChangedColor: boolean;
  /** This is the last row of the step and the next step is a different color. */
  colorChangeAfterThisRow: boolean;
  next: Step | null;
}

export function position(p: Pick<Project, 'steps' | 'rows_done'>): Position {
  const total = totalRows(p);
  const done = Math.max(0, p.rows_done);
  const base: Position = {
    stepIndex: -1,
    step: null,
    rowInStep: 0,
    row: done + 1,
    total,
    finished: total > 0 && done >= total,
    justChangedColor: false,
    colorChangeAfterThisRow: false,
    next: null,
  };
  if (total === 0 || done >= total) return base;

  const starts = stepStarts(p.steps);
  let i = starts.length - 1;
  while (i > 0 && starts[i] > done) i--;
  // Skip zero-row steps defensively (rows is clamped >= 1, but be safe).
  while (i < p.steps.length - 1 && done >= starts[i] + p.steps[i].rows) i++;

  const step = p.steps[i];
  const rowInStep = done - starts[i] + 1;
  const prev = i > 0 ? p.steps[i - 1] : null;
  const next = i < p.steps.length - 1 ? p.steps[i + 1] : null;
  return {
    ...base,
    stepIndex: i,
    step,
    rowInStep,
    next,
    justChangedColor: rowInStep === 1 && prev !== null && step.color_id !== null && prev.color_id !== step.color_id,
    colorChangeAfterThisRow:
      rowInStep === step.rows && next !== null && next.color_id !== null && next.color_id !== step.color_id,
  };
}

export const colorById = (colors: YarnColor[], id: string | null) =>
  id ? (colors.find((c) => c.id === id) ?? null) : null;

/** Readable text color (dark or light) for a given swatch background. */
export function contrastText(hex: string): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return '#1c1618';
  const n = parseInt(m[1], 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.35 ? '#1c1618' : '#f5ece6';
}
