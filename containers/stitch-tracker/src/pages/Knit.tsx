import { useEffect, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useProject, useWakeLock } from '../hooks/useStore';
import { updateProject } from '../lib/store.ts';
import { colorById, contrastText, position, stepStarts } from '../lib/pattern.ts';
import type { Project } from '../lib/types.ts';
import { ColorPill, EmptyState, StripeBar, Swatch } from '../components/ui';
import { IconBack, IconCheck, IconEdit, IconSun, IconUndo } from '../components/icons';

const WAKE_KEY = 'st.keepAwake';

export default function Knit() {
  const { id } = useParams();
  const project = useProject(id);
  if (!project) {
    return (
      <EmptyState title="Project not found" hint="It may have been deleted on another device.">
        <Link to="/" className="btn-ghost">
          Back to projects
        </Link>
      </EmptyState>
    );
  }
  return <KnitView project={project} />;
}

function KnitView({ project: p }: { project: Project }) {
  const pos = position(p);
  const color = colorById(p.colors, pos.step?.color_id ?? null);
  const nextColor = colorById(p.colors, pos.next?.color_id ?? null);
  const hasPattern = pos.total > 0;

  const [keepAwake, setKeepAwake] = useState(() => {
    try {
      return localStorage.getItem(WAKE_KEY) === '1';
    } catch {
      return false;
    }
  });
  const wake = useWakeLock(keepAwake);
  useEffect(() => {
    try {
      localStorage.setItem(WAKE_KEY, keepAwake ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [keepAwake]);

  // Brief "pop" on the counter after each tap, so a completed row registers.
  const [bump, setBump] = useState(0);
  const setRows = (n: number) => updateProject(p.id, { rows_done: Math.max(0, n) });
  const rowDone = () => {
    setRows(p.rows_done + 1);
    setBump((b) => b + 1);
    navigator.vibrate?.(12);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Link to="/" className="btn-icon -ml-2" aria-label="All projects">
          <IconBack className="h-5 w-5" />
        </Link>
        <h1 className="heading min-w-0 flex-1 truncate text-xl">{p.name || 'Untitled project'}</h1>
        <Link to={`/p/${p.id}/edit`} className="btn-ghost !px-3 !py-1.5 text-sm">
          <IconEdit className="h-4 w-4" /> Edit
        </Link>
      </div>

      {/* ---- Now knitting ---- */}
      <section className="card overflow-hidden">
        {color && <div className="h-2" style={{ background: color.hex }} />}
        <div className="space-y-4 p-4">
          {pos.finished ? (
            <Finished project={p} onUndo={() => setRows(pos.total - 1)} />
          ) : (
            <>
              {pos.justChangedColor && color && (
                <Banner hex={color.hex}>
                  New color — switch to <b>{color.name}</b>
                </Banner>
              )}
              {pos.colorChangeAfterThisRow && nextColor && (
                <div className="flex items-center gap-2 rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
                  <Swatch color={nextColor} />
                  Last {color?.name ?? ''} row — <b>{nextColor.name}</b> is next
                </div>
              )}

              <div className="flex items-end justify-between gap-3">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-muted">
                    {hasPattern ? `Step ${pos.stepIndex + 1} of ${p.steps.length}` : 'Row counter'}
                  </div>
                  <div key={bump} className="heading mt-1 animate-[pop_.25s_ease-out] text-5xl tabular-nums">
                    {hasPattern ? (
                      <>
                        Row {pos.rowInStep}
                        <span className="text-2xl text-muted"> / {pos.step!.rows}</span>
                      </>
                    ) : (
                      <>Row {pos.row}</>
                    )}
                  </div>
                </div>
                {color && <ColorPill color={color} className="mb-1" />}
              </div>

              {pos.step?.text && (
                <div className="rounded-xl bg-panel2 px-3 py-2.5 text-lg leading-snug">{pos.step.text}</div>
              )}

              <button
                onClick={rowDone}
                className="flex h-28 w-full items-center justify-center gap-3 rounded-2xl text-2xl font-semibold shadow-lg transition active:scale-[0.98]"
                style={{
                  background: color?.hex ?? '#f0a77c',
                  color: contrastText(color?.hex ?? '#f0a77c'),
                }}
              >
                <IconCheck className="h-8 w-8" strokeWidth={2.5} />
                Row done
              </button>

              <div className="flex items-center justify-between text-sm">
                <button className="btn-ghost !py-1.5" onClick={() => setRows(p.rows_done - 1)} disabled={p.rows_done === 0}>
                  <IconUndo className="h-4 w-4" /> Undo row
                </button>
                <span className="tabular-nums text-muted">
                  {hasPattern
                    ? `Row ${pos.row} of ${pos.total} · ${Math.round((p.rows_done / pos.total) * 100)}%`
                    : `${p.rows_done} done`}
                </span>
              </div>
            </>
          )}
        </div>
      </section>

      {hasPattern && <StripeBar project={p} height="h-4" />}

      {!hasPattern && (
        <p className="text-center text-sm text-muted">
          No pattern yet — <Link to={`/p/${p.id}/edit`} className="text-wool underline">add one</Link> to track
          stripes, color changes, and per-row instructions.
        </p>
      )}

      {/* ---- Notes ---- */}
      {(p.description || p.notes) && (
        <section className="card space-y-2 p-4">
          {p.description && <p className="text-muted">{p.description}</p>}
          {p.notes && <p className="whitespace-pre-wrap leading-relaxed">{p.notes}</p>}
        </section>
      )}

      {hasPattern && <PatternList project={p} current={pos.finished ? -1 : pos.stepIndex} onJump={setRows} />}

      {wake.supported && (
        <label className="flex cursor-pointer items-center justify-center gap-2 py-2 text-sm text-muted">
          <input type="checkbox" className="accent-[#f0a77c]" checked={keepAwake} onChange={(e) => setKeepAwake(e.target.checked)} />
          <IconSun className="h-4 w-4" /> Keep screen on while knitting
        </label>
      )}
    </div>
  );
}

function Banner({ hex, children }: { hex: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium" style={{ background: hex, color: contrastText(hex) }}>
      <span className="text-base">🧶</span>
      <span>{children}</span>
    </div>
  );
}

function Finished({ project: p, onUndo }: { project: Project; onUndo: () => void }) {
  return (
    <div className="space-y-3 py-4 text-center">
      <div className="text-4xl">🎉</div>
      <div className="heading text-2xl">Pattern complete!</div>
      <p className="text-sm text-muted">All {p.rows_done} rows knitted. Time to bind off and weave in those ends.</p>
      <div className="flex flex-wrap justify-center gap-2 whitespace-nowrap pt-1">
        <button className="btn-ghost" onClick={onUndo}>
          <IconUndo className="h-4 w-4" /> Undo last row
        </button>
        {p.status !== 'finished' && (
          <button className="btn-primary" onClick={() => updateProject(p.id, { status: 'finished' })}>
            Mark project finished
          </button>
        )}
      </div>
    </div>
  );
}

function PatternList({ project: p, current, onJump }: { project: Project; current: number; onJump: (rows: number) => void }) {
  const starts = stepStarts(p.steps);
  const [expanded, setExpanded] = useState(false);

  // Show a window around the current step unless expanded.
  const WINDOW = 6;
  const focus = current < 0 ? p.steps.length - 1 : current;
  const from = expanded ? 0 : Math.max(0, focus - 2);
  const to = expanded ? p.steps.length : Math.min(p.steps.length, from + WINDOW);
  const hidden = p.steps.length - (to - from);

  const jump = (i: number) => {
    const s = p.steps[i];
    const label = colorById(p.colors, s.color_id)?.name ?? s.text ?? '';
    if (confirm(`Jump to the start of step ${i + 1}${label ? ` (${label})` : ''}? Rows done will be set to ${starts[i]}.`)) {
      onJump(starts[i]);
    }
  };

  return (
    <section className="card p-2">
      <div className="flex items-center justify-between px-2 pb-1 pt-2">
        <h2 className="heading">Pattern</h2>
        <span className="text-xs text-muted">Tap a step to jump there</span>
      </div>
      <ol>
        {p.steps.slice(from, to).map((s, k) => {
          const i = from + k;
          const c = colorById(p.colors, s.color_id);
          const done = current < 0 || i < current;
          const isCur = i === current;
          const knitted = isCur ? p.rows_done - starts[i] : 0;
          return (
            <li key={s.id}>
              <button
                onClick={() => jump(i)}
                className={`flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-panel2 ${
                  isCur ? 'bg-panel2 ring-1 ring-wool/50' : ''
                } ${done ? 'opacity-50' : ''}`}
              >
                <span className="w-6 shrink-0 text-right text-xs tabular-nums text-muted">{i + 1}</span>
                <Swatch color={c} size="lg" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">
                    <b className="tabular-nums">{s.rows}</b> {s.rows === 1 ? 'row' : 'rows'}
                    {c && <span> · {c.name}</span>}
                  </span>
                  {s.text && <span className="block truncate text-sm text-muted">{s.text}</span>}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted">
                  {done ? '✓' : isCur ? `${knitted}/${s.rows}` : `row ${starts[i] + 1}`}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      {(hidden > 0 || expanded) && (
        <button className="w-full py-2 text-sm text-wool" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : `Show all ${p.steps.length} steps`}
        </button>
      )}
    </section>
  );
}
