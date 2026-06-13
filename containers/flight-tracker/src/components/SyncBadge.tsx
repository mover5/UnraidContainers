import { useSyncStatus } from '../hooks/useSyncStatus';

export default function SyncBadge({ compact = false }: { compact?: boolean }) {
  const s = useSyncStatus();

  let dot = 'bg-good';
  let text = 'Synced';
  if (!s.remote) {
    dot = 'bg-slate-400';
    text = compact ? 'Local' : 'Local mode (this device)';
  } else if (!s.online) {
    dot = 'bg-warn';
    text = s.pending ? `Offline · ${s.pending} queued` : 'Offline';
  } else if (s.syncing) {
    dot = 'bg-sky animate-pulse';
    text = 'Syncing…';
  } else if (s.pending > 0) {
    dot = 'bg-sky';
    text = `${s.pending} to sync`;
  } else {
    dot = 'bg-good';
    text = compact ? 'Synced' : '☁ Synced';
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] text-muted"
      title={s.lastError ?? (s.lastSyncedAt ? `Last synced ${new Date(s.lastSyncedAt).toLocaleTimeString()}` : undefined)}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {text}
    </span>
  );
}
