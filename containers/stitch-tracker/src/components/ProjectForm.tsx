// The editable parts of a project — details, yarn colors, and the pattern —
// shared by the New and Edit pages. Purely controlled: every change goes out
// through onChange(patch).
import { useMemo, useState } from 'react';
import { guessHex } from '../lib/colors.ts';
import { parsePattern } from '../lib/parse.ts';
import { colorById, totalRows } from '../lib/pattern.ts';
import type { Step, YarnColor } from '../lib/types.ts';
import { uuid } from '../lib/uuid.ts';
import { NumberField, Swatch } from './ui';
import { IconClipboard, IconCopy, IconDown, IconPlus, IconUp, IconX } from './icons';

export interface FormValue {
  name: string;
  description: string;
  notes: string;
  colors: YarnColor[];
  steps: Step[];
}

export default function ProjectForm({
  value,
  onChange,
  startWithPaste = false,
}: {
  value: FormValue;
  onChange: (patch: Partial<FormValue>) => void;
  startWithPaste?: boolean;
}) {
  return (
    <div className="space-y-4">
      <section className="card space-y-4 p-4">
        <div>
          <label className="label" htmlFor="pf-name">Name</label>
          <input
            id="pf-name"
            className="input text-lg"
            placeholder="Doctor Who Scarf"
            value={value.name}
            onChange={(e) => onChange({ name: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="pf-desc">Description</label>
          <textarea
            id="pf-desc"
            rows={2}
            className="input"
            placeholder="Season 12 stripes, for Dad"
            value={value.description}
            onChange={(e) => onChange({ description: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="pf-notes">Notes &amp; instructions</label>
          <textarea
            id="pf-notes"
            rows={4}
            className="input"
            placeholder={'Cast on 60 stitches.\nBasic knit stitch; slip the first stitch of every row.'}
            value={value.notes}
            onChange={(e) => onChange({ notes: e.target.value })}
          />
        </div>
      </section>

      <ColorsEditor colors={value.colors} steps={value.steps} onChange={onChange} />
      <PatternEditor value={value} onChange={onChange} startWithPaste={startWithPaste} />
    </div>
  );
}

// ---------------------------------------------------------------- colors

function ColorsEditor({
  colors,
  steps,
  onChange,
}: {
  colors: YarnColor[];
  steps: Step[];
  onChange: (patch: Partial<FormValue>) => void;
}) {
  const [name, setName] = useState('');
  const set = (id: string, patch: Partial<YarnColor>) =>
    onChange({ colors: colors.map((c) => (c.id === id ? { ...c, ...patch } : c)) });
  const remove = (c: YarnColor) => {
    const used = steps.filter((s) => s.color_id === c.id).length;
    if (used && !confirm(`${c.name} is used by ${used} step${used === 1 ? '' : 's'}. Remove it anyway?`)) return;
    onChange({
      colors: colors.filter((x) => x.id !== c.id),
      steps: used ? steps.map((s) => (s.color_id === c.id ? { ...s, color_id: null } : s)) : steps,
    });
  };
  const add = () => {
    const n = name.trim();
    if (!n) return;
    onChange({ colors: [...colors, { id: uuid(), name: n, hex: guessHex(n, colors.length) }] });
    setName('');
  };

  return (
    <section className="card space-y-3 p-4">
      <div>
        <h2 className="heading">Yarn colors</h2>
        <p className="text-xs text-muted">Tap a swatch to fine-tune its color.</p>
      </div>
      {colors.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {colors.map((c) => (
            <li key={c.id} className="flex items-center gap-2 rounded-xl bg-panel2 p-1.5 pl-2">
              <input
                type="color"
                className="h-8 w-8 shrink-0"
                value={c.hex}
                onChange={(e) => set(c.id, { hex: e.target.value })}
                aria-label={`${c.name} color`}
              />
              <input
                className="input !border-transparent !bg-transparent !px-1 !py-1"
                value={c.name}
                onChange={(e) => set(c.id, { name: e.target.value })}
                aria-label="Color name"
              />
              <button type="button" className="btn-icon shrink-0" onClick={() => remove(c)} aria-label={`Remove ${c.name}`}>
                <IconX className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          className="input"
          placeholder="Add a color, e.g. Mustard"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
        />
        <button type="button" className="btn-ghost shrink-0" onClick={add} disabled={!name.trim()}>
          <IconPlus className="h-4 w-4" /> Add
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- pattern

function PatternEditor({
  value,
  onChange,
  startWithPaste,
}: {
  value: FormValue;
  onChange: (patch: Partial<FormValue>) => void;
  startWithPaste: boolean;
}) {
  const { steps, colors } = value;
  const [pasting, setPasting] = useState(startWithPaste);
  const total = totalRows(value);

  const setSteps = (next: Step[]) => onChange({ steps: next });
  const patchStep = (i: number, patch: Partial<Step>) => setSteps(steps.map((s, k) => (k === i ? { ...s, ...patch } : s)));
  const move = (i: number, d: -1 | 1) => {
    const next = [...steps];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    setSteps(next);
  };
  const duplicate = (i: number) => setSteps([...steps.slice(0, i + 1), { ...steps[i], id: uuid() }, ...steps.slice(i + 1)]);
  const addStep = () => setSteps([...steps, { id: uuid(), rows: 1, color_id: null, text: '' }]);

  return (
    <section className="card space-y-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="heading">Pattern</h2>
          <p className="text-xs text-muted">
            {steps.length
              ? `${steps.length} step${steps.length === 1 ? '' : 's'} · ${total} rows`
              : 'Each step is a run of rows — a stripe, or a row with its own instruction.'}
          </p>
        </div>
        {!pasting && (
          <button type="button" className="btn-ghost shrink-0 !py-1.5 text-sm" onClick={() => setPasting(true)}>
            <IconClipboard className="h-4 w-4" /> Paste
          </button>
        )}
      </div>

      {pasting && (
        <PasteImport
          value={value}
          onPatch={onChange}
          onCancel={() => setPasting(false)}
          onApply={(patch) => {
            onChange(patch);
            setPasting(false);
          }}
        />
      )}

      {steps.length > 0 && (
        <ol className="space-y-2">
          {steps.map((s, i) => {
            const c = colorById(colors, s.color_id);
            return (
              <li key={s.id} className="rounded-xl border-l-4 bg-panel2 p-2" style={{ borderLeftColor: c?.hex ?? '#45383d' }}>
                <div className="flex items-center gap-2">
                  <span className="w-6 shrink-0 text-right text-xs tabular-nums text-muted">{i + 1}</span>
                  <NumberField
                    className="input w-16 shrink-0 !px-2 !py-1.5 text-center tabular-nums"
                    value={s.rows}
                    min={1}
                    onChange={(n) => patchStep(i, { rows: n })}
                    aria-label="Rows"
                  />
                  <span className="text-sm text-muted">{s.rows === 1 ? 'row' : 'rows'}</span>
                  <span className="flex min-w-0 flex-1 items-center gap-1.5">
                    <Swatch color={c} />
                    <select
                      className="input min-w-0 !px-2 !py-1.5"
                      value={s.color_id ?? ''}
                      onChange={(e) => patchStep(i, { color_id: e.target.value || null })}
                      aria-label="Color"
                    >
                      <option value="">No color</option>
                      {colors.map((col) => (
                        <option key={col.id} value={col.id}>
                          {col.name}
                        </option>
                      ))}
                    </select>
                  </span>
                </div>
                <div className="mt-1.5 flex items-center gap-1 pl-8">
                  <input
                    className="input !py-1.5 text-sm"
                    placeholder="Instruction (optional) — e.g. k2, p2 across"
                    value={s.text}
                    onChange={(e) => patchStep(i, { text: e.target.value })}
                  />
                  <button type="button" className="btn-icon shrink-0" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">
                    <IconUp className="h-4 w-4" />
                  </button>
                  <button type="button" className="btn-icon shrink-0" onClick={() => move(i, 1)} disabled={i === steps.length - 1} aria-label="Move down">
                    <IconDown className="h-4 w-4" />
                  </button>
                  <button type="button" className="btn-icon shrink-0" onClick={() => duplicate(i)} aria-label="Duplicate step">
                    <IconCopy className="h-4 w-4" />
                  </button>
                  <button type="button" className="btn-icon shrink-0 hover:!text-bad" onClick={() => setSteps(steps.filter((_, k) => k !== i))} aria-label="Delete step">
                    <IconX className="h-4 w-4" />
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <button type="button" className="btn-ghost w-full" onClick={addStep}>
        <IconPlus className="h-4 w-4" /> Add step
      </button>
    </section>
  );
}

function PasteImport({
  value,
  onPatch,
  onApply,
  onCancel,
}: {
  value: FormValue;
  onPatch: (patch: Partial<FormValue>) => void; // keeps the panel open
  onApply: (patch: Partial<FormValue>) => void; // applies and closes
  onCancel: () => void;
}) {
  const [text, setText] = useState('');
  const [leftoversUsed, setLeftoversUsed] = useState(false);
  const parsed = useMemo(() => parsePattern(text, value.colors), [text, value.colors]);
  const palette = [...value.colors, ...parsed.newColors];
  const rows = parsed.steps.reduce((n, s) => n + s.rows, 0);

  const apply = (mode: 'append' | 'replace') =>
    onApply({
      colors: palette,
      steps: mode === 'append' ? [...value.steps, ...parsed.steps] : parsed.steps,
    });

  // Leftover lines are usually the header ("Doctor Who Scarf", "Cast on 60").
  const useLeftovers = () => {
    const lines = [...parsed.skipped].filter((l) => !/^etc\.?$|^\.\.\.$|^…$/i.test(l));
    const patch: Partial<FormValue> = {};
    if (!value.name.trim() && lines.length) patch.name = lines.shift()!;
    if (lines.length) patch.notes = [value.notes.trim(), lines.join('\n')].filter(Boolean).join('\n');
    onPatch(patch);
    setLeftoversUsed(true);
  };

  return (
    <div className="space-y-3 rounded-xl border border-wool/40 bg-ink p-3">
      <div>
        <label className="label" htmlFor="pf-paste">Paste your pattern</label>
        <textarea
          id="pf-paste"
          rows={7}
          autoFocus
          className="input font-mono text-sm"
          placeholder={'8 Purple\n26 Camel\n8 Bronze\nRow 5: k2, p2 across\nRows 6-9: knit'}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setLeftoversUsed(false);
          }}
        />
        <p className="mt-1 text-xs text-muted">
          One step per line: “8 Purple”, “12 rows in Rust”, “Row 5: k2, p2”, “Rows 6-9: knit”.
        </p>
      </div>

      {text.trim() && (
        <div className="space-y-2 text-sm">
          {parsed.steps.length > 0 ? (
            <>
              <div className="text-muted">
                Found <b className="text-cream">{parsed.steps.length}</b> steps · {rows} rows
                {parsed.newColors.length > 0 && <> · {parsed.newColors.length} new colors</>}
              </div>
              <ul className="max-h-48 space-y-1 overflow-y-auto pr-1">
                {parsed.steps.map((s) => {
                  const c = colorById(palette, s.color_id);
                  return (
                    <li key={s.id} className="flex items-center gap-2">
                      <Swatch color={c} size="sm" />
                      <span className="tabular-nums">{s.rows}</span>
                      <span>{c?.name}</span>
                      {s.text && <span className="truncate text-muted">{s.text}</span>}
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <div className="text-muted">No steps recognized yet.</div>
          )}
          {parsed.skipped.length > 0 && (
            <div className="rounded-lg bg-panel2 px-2.5 py-2 text-xs text-muted">
              <div className="mb-1">Not part of the pattern ({parsed.skipped.length}):</div>
              <ul className="space-y-0.5">
                {parsed.skipped.map((l, i) => (
                  <li key={i} className="truncate">“{l}”</li>
                ))}
              </ul>
              {leftoversUsed ? (
                <div className="mt-1.5 text-sage">✓ Copied into the project details above</div>
              ) : (
                <button type="button" className="mt-1.5 text-wool underline" onClick={useLeftovers}>
                  {value.name.trim() ? 'Add these to notes' : 'Use first line as the name, the rest as notes'}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="btn !px-3 text-muted hover:text-cream" onClick={onCancel}>
          Cancel
        </button>
        {value.steps.length > 0 && (
          <button type="button" className="btn-ghost" disabled={!parsed.steps.length} onClick={() => apply('replace')}>
            Replace pattern
          </button>
        )}
        <button type="button" className="btn-primary" disabled={!parsed.steps.length} onClick={() => apply('append')}>
          {value.steps.length > 0 ? `Add ${parsed.steps.length} steps` : `Use ${parsed.steps.length} steps`}
        </button>
      </div>
    </div>
  );
}
