import { useEffect, useState, type ReactNode } from 'react';
import { IconArrowRight } from './icons';

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-edge border-t-sky" />
      {label}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  tone = 'default',
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: 'default' | 'good' | 'warn' | 'bad';
}) {
  const toneColor =
    tone === 'good' ? 'text-good' : tone === 'warn' ? 'text-warn' : tone === 'bad' ? 'text-bad' : 'text-slate-100';
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${toneColor}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

const CARRIER_COLORS: Record<string, string> = {
  Alaska: 'bg-sky/15 text-sky',
  American: 'bg-rose-400/15 text-rose-300',
  United: 'bg-indigo-400/15 text-indigo-300',
  Delta: 'bg-red-400/15 text-red-300',
  'Air Tahiti': 'bg-emerald-400/15 text-emerald-300',
};

export function CarrierBadge({ carrier }: { carrier: string }) {
  const cls = CARRIER_COLORS[carrier] ?? 'bg-slate-400/15 text-slate-300';
  return <span className={`chip ${cls}`}>{carrier}</span>;
}

export function RouteBadge({ origin, destination }: { origin: string; destination: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono font-semibold">
      {origin}
      <IconArrowRight className="h-3.5 w-3.5 text-muted" />
      {destination}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card flex flex-col items-center gap-1 py-16 text-center">
      <div className="text-slate-200">{title}</div>
      {hint && <div className="text-sm text-muted">{hint}</div>}
    </div>
  );
}

export function fmtDate(iso: string, opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' }) {
  // Treat the date as a local calendar date (no tz shift). Tolerate a full ISO
  // timestamp ("2026-06-16T07:00:00.000Z") by taking just the date portion.
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return 'Invalid Date';
  return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
}

/** Parse a TZ-offset draft ("-2", "+5.5", "3") -> hours, or null if incomplete/invalid. */
function parseHours(s: string): number | null {
  const t = s.trim();
  if (!/^[+-]?\d+(\.\d+)?$/.test(t)) return null;
  return Number(t);
}

/**
 * Hours input for the timezone change. Keeps its own text draft so the field
 * can be emptied and a lone "-" typed (a controlled type=number input snaps
 * back to 0). Only commits parseable values; a blank field commits 0 on blur.
 * The ± button flips the sign, since phone number pads often lack a minus key.
 */
export function TzChangeInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [draft, setDraft] = useState(String(value));

  // Follow outside changes (sync, another device) unless the draft already means that value.
  useEffect(() => {
    setDraft((d) => (parseHours(d) === value ? d : String(value)));
  }, [value]);

  const edit = (next: string) => {
    setDraft(next);
    const n = parseHours(next);
    if (n !== null && n !== value) onChange(n);
  };

  const flip = () => {
    const t = draft.trim();
    edit(t.startsWith('-') ? t.slice(1) : '-' + t.replace(/^\+/, ''));
  };

  return (
    <div className="flex gap-2">
      <button type="button" className="btn-ghost shrink-0 px-3 font-mono" onClick={flip} aria-label="Flip sign">
        ±
      </button>
      <input
        type="text"
        inputMode="decimal"
        className="input min-w-0 flex-1"
        placeholder="0"
        value={draft}
        onChange={(e) => edit(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={() => {
          const t = draft.trim();
          if (t === '' || t === '-' || t === '+') {
            if (value !== 0) onChange(0);
            setDraft('0');
          } else {
            setDraft(String(parseHours(t) ?? value));
          }
        }}
      />
    </div>
  );
}
