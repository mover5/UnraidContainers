import { useEffect, useState, type ReactNode } from 'react';
import { colorById, contrastText, stepStarts, totalRows } from '../lib/pattern.ts';
import type { Project, YarnColor } from '../lib/types.ts';
import { useSyncStatus } from '../hooks/useStore.ts';

const NO_COLOR = '#5b4d52';

export function Swatch({ color, size = 'md' }: { color: YarnColor | null; size?: 'sm' | 'md' | 'lg' }) {
  const dim = size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-6 w-6' : 'h-4 w-4';
  return (
    <span
      className={`inline-block shrink-0 rounded-full ring-1 ring-white/20 ${dim}`}
      style={{ background: color?.hex ?? NO_COLOR }}
      title={color?.name}
    />
  );
}

/** A named color pill, filled with the yarn color. */
export function ColorPill({ color, className = '' }: { color: YarnColor | null; className?: string }) {
  if (!color) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-white/15 ${className}`}
      style={{ background: color.hex, color: contrastText(color.hex) }}
    >
      {color.name}
    </span>
  );
}

/**
 * The whole pattern as one bar of stripes, sized by row count. Knitted rows are
 * shown full strength, the rest faded, with a marker at the current row.
 */
export function StripeBar({ project, height = 'h-3' }: { project: Project; height?: string }) {
  const total = totalRows(project);
  if (total === 0) return null;
  const starts = stepStarts(project.steps);
  const done = Math.min(project.rows_done, total);
  return (
    <div className={`relative flex w-full overflow-hidden rounded-full bg-panel2 ${height}`}>
      {project.steps.map((s, i) => {
        const hex = colorById(project.colors, s.color_id)?.hex ?? NO_COLOR;
        const knitted = Math.max(0, Math.min(s.rows, done - starts[i]));
        return (
          <div key={s.id} className="flex h-full" style={{ flexGrow: s.rows, flexBasis: 0 }}>
            {knitted > 0 && <div style={{ flexGrow: knitted, background: hex }} />}
            {knitted < s.rows && <div style={{ flexGrow: s.rows - knitted, background: hex, opacity: 0.28 }} />}
          </div>
        );
      })}
      {done > 0 && done < total && (
        <div className="absolute inset-y-0 w-0.5 bg-cream shadow" style={{ left: `calc(${(done / total) * 100}% - 1px)` }} />
      )}
    </div>
  );
}

export function SyncBadge() {
  const s = useSyncStatus();
  let dot = 'bg-sage';
  let text = 'Synced';
  if (!s.remote) {
    dot = 'bg-muted';
    text = 'This device only';
  } else if (!s.online) {
    dot = 'bg-warn';
    text = s.pending ? `Offline · ${s.pending} to sync` : 'Offline';
  } else if (s.syncing) {
    dot = 'bg-wool animate-pulse';
    text = 'Syncing…';
  } else if (s.lastError) {
    dot = 'bg-bad';
    text = s.pending ? `Can't reach server · ${s.pending} waiting` : "Can't reach server";
  } else if (s.pending) {
    dot = 'bg-wool';
    text = `${s.pending} to sync`;
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-muted"
      title={s.lastError ?? (s.lastSyncedAt ? `Last synced ${new Date(s.lastSyncedAt).toLocaleTimeString()}` : undefined)}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {text}
    </span>
  );
}

/**
 * Whole-number input that can be cleared while typing (a controlled number
 * input would snap back). Commits valid values as you type; restores on blur.
 */
export function NumberField({
  value,
  onChange,
  min = 0,
  className = 'input',
  ...rest
}: {
  value: number;
  onChange: (n: number) => void;
  min?: number;
  className?: string;
  'aria-label'?: string;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => {
    setDraft((d) => (Number(d) === value && d.trim() !== '' ? d : String(value)));
  }, [value]);
  return (
    <input
      {...rest}
      type="text"
      inputMode="numeric"
      className={className}
      value={draft}
      onFocus={(e) => e.target.select()}
      onChange={(e) => {
        const t = e.target.value.replace(/[^\d]/g, '');
        setDraft(t);
        if (t !== '' && Number(t) >= min && Number(t) !== value) onChange(Number(t));
      }}
      onBlur={() => setDraft(String(value))}
    />
  );
}

export function EmptyState({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-14 text-center">
      <div className="heading text-lg">{title}</div>
      {hint && <div className="max-w-sm text-sm text-muted">{hint}</div>}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
