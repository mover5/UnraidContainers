// Turn pasted pattern text into steps. Understands the shapes knitting patterns
// (and notes-app transcriptions of them) usually take:
//
//   8 Purple            -> 8 rows, color Purple
//   8 rows in Purple    -> same
//   Purple 8 / Purple: 8 -> same
//   12 Rust - slip first st -> 12 rows, Rust, instruction "slip first st"
//   Row 5: k2, p2 across -> 1 row with that instruction
//   Rows 3-6: knit      -> 4 rows with that instruction
//
// Lines it can't read (headers, "etc.") are returned in `skipped` so the
// preview can show what was left out.
import { guessHex, looksLikeColor } from './colors.ts';
import type { Step, YarnColor } from './types.ts';
import { uuid } from './uuid.ts';

export interface ParseResult {
  steps: Step[];
  newColors: YarnColor[];
  skipped: string[];
}

const SEP = String.raw`[\s:;,.)\-–—]*`;

const titleCase = (s: string) => s.trim().replace(/\s+/g, ' ').replace(/\b[a-z]/g, (c) => c.toUpperCase());

export function parsePattern(text: string, existing: YarnColor[]): ParseResult {
  const palette = [...existing];
  const newColors: YarnColor[] = [];
  const steps: Step[] = [];
  const skipped: string[] = [];

  const findColor = (name: string) => palette.find((c) => c.name.toLowerCase() === name.trim().toLowerCase()) ?? null;

  const colorFor = (name: string): YarnColor => {
    const hit = findColor(name);
    if (hit) return hit;
    const c: YarnColor = { id: uuid(), name: titleCase(name), hex: guessHex(name, palette.length) };
    palette.push(c);
    newColors.push(c);
    return c;
  };

  /** Split "Purple - slip first st" into a color and an instruction, when it starts with one. */
  const splitColor = (rest: string): { color: YarnColor | null; text: string } => {
    const r = rest.trim().replace(/^[:;,.\-–—]+\s*/, '');
    if (!r) return { color: null, text: '' };
    // Known palette names first, longest first ("Light Grey" before "Grey").
    for (const c of [...palette].sort((a, b) => b.name.length - a.name.length)) {
      const n = c.name.toLowerCase();
      if (r.toLowerCase() === n) return { color: c, text: '' };
      if (r.toLowerCase().startsWith(n) && /^[\s:;,(\-–—]/.test(r.slice(n.length))) {
        return { color: c, text: r.slice(n.length).replace(/^[\s:;,(\-–—]+/, '').replace(/\)$/, '').trim() };
      }
    }
    if (looksLikeColor(r)) return { color: colorFor(r), text: '' };
    // "Rust - slip first st" / "Heather Grey: knit"
    const m = /^([a-z][a-z\s'-]{0,40}?)\s*[:;,(\-–—]\s*(.+)$/i.exec(r);
    if (m && looksLikeColor(m[1])) return { color: colorFor(m[1]), text: m[2].replace(/\)$/, '').trim() };
    return { color: null, text: r };
  };

  const push = (rows: number, rest: string) => {
    if (!Number.isFinite(rows) || rows < 1) return false;
    const { color, text } = splitColor(rest);
    steps.push({ id: uuid(), rows: Math.min(rows, 100000), color_id: color?.id ?? null, text });
    return true;
  };

  for (const raw of text.split(/\r?\n/)) {
    let line = raw.trim().replace(/^[-*•·]\s+/, '');
    if (!line) continue;
    // Numbered list wrapping a count: "1. 8 Purple" -> "8 Purple"
    line = line.replace(/^\d+[.)]\s+(?=\d)/, '');

    let m: RegExpExecArray | null;
    if ((m = new RegExp(String.raw`^rows?\s+(\d+)\s*(?:-|–|—|to|through|thru)\s*(\d+)${SEP}(.*)$`, 'i').exec(line))) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (push(Math.abs(b - a) + 1, m[3])) continue;
    } else if ((m = new RegExp(String.raw`^row\s+(\d+)${SEP}(.*)$`, 'i').exec(line))) {
      if (push(1, m[2])) continue;
    } else if ((m = /^(\d+)\s*(?:rows?\b)?\s*(?:x\b|×)?\s*(?:of\b|in\b|with\b)?(.*)$/i.exec(line))) {
      if (push(Number(m[1]), m[2])) continue;
    } else if ((m = /^([a-z][a-z\s'-]*?)\s*[:\-–—x×]?\s*(\d+)\s*(?:rows?)?\.?$/i.exec(line)) && (findColor(m[1]) || looksLikeColor(m[1]))) {
      if (push(Number(m[2]), m[1])) continue;
    }
    skipped.push(raw.trim());
  }

  return { steps, newColors, skipped };
}
