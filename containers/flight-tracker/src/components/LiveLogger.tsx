import { useState } from 'react';
import { EVENT_FIELDS, type Flight } from '../lib/types';
import { nowClock } from '../lib/time';
import { IconClock } from './icons';

export default function LiveLogger({
  flight,
  onPatch,
}: {
  flight: Flight;
  onPatch: (patch: Partial<Flight>) => Promise<void>;
}) {
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Live logging</h2>
        <span className="text-xs text-muted">Tap to stamp the current time</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {EVENT_FIELDS.map((ev) => (
          <EventButton
            key={ev.key}
            label={ev.label}
            value={flight[ev.key]}
            onStamp={() => onPatch({ [ev.key]: nowClock() } as Partial<Flight>)}
            onSet={(v) => onPatch({ [ev.key]: v } as Partial<Flight>)}
            onClear={() => onPatch({ [ev.key]: null } as Partial<Flight>)}
          />
        ))}
      </div>
    </div>
  );
}

function EventButton({
  label,
  value,
  onStamp,
  onSet,
  onClear,
}: {
  label: string;
  value: string | null;
  onStamp: () => void;
  onSet: (v: string) => void;
  onClear: () => void;
}) {
  const [editing, setEditing] = useState(false);

  if (value) {
    return (
      <div className="flex flex-col rounded-2xl border border-edge bg-ink/60 p-3">
        <span className="text-xs text-muted">{label}</span>
        {editing ? (
          <input
            type="time"
            autoFocus
            className="input mt-1"
            defaultValue={value}
            onBlur={(e) => {
              if (e.target.value) onSet(e.target.value);
              setEditing(false);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
          />
        ) : (
          <span className="font-mono text-2xl font-semibold text-good tabular-nums">{value}</span>
        )}
        <div className="mt-2 flex gap-3 text-[11px] text-muted">
          <button className="hover:text-sky" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Done' : 'Edit'}
          </button>
          <button className="hover:text-bad" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>
    );
  }

  return (
    <button
      onClick={onStamp}
      className="flex min-h-[92px] flex-col items-center justify-center gap-1 rounded-2xl border border-dashed border-edge bg-panel2 p-3 text-center transition active:scale-[0.98] hover:border-sky"
    >
      <IconClock className="h-5 w-5 text-sky" />
      <span className="font-medium">{label}</span>
      <span className="text-[11px] text-muted">Tap to stamp now</span>
    </button>
  );
}
