import type { ReactNode } from 'react';
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
  // Treat the date as local calendar date (no tz shift).
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
}
