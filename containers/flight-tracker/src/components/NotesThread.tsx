import { useEffect, useState } from 'react';
import { store } from '../lib/store';
import type { FlightNote } from '../lib/types';
import { IconTrash } from './icons';

function fmtStamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function NotesThread({ flightId, legacyNote }: { flightId: string; legacyNote: string | null }) {
  const [notes, setNotes] = useState<FlightNote[]>([]);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    store.listNotes(flightId).then((n) => {
      if (alive) {
        setNotes(n);
        setLoading(false);
      }
    });
    return () => {
      alive = false;
    };
  }, [flightId]);

  async function add() {
    const text = body.trim();
    if (!text) return;
    setBusy(true);
    const note = await store.addNote(flightId, text);
    setNotes((n) => [note, ...n]);
    setBody('');
    setBusy(false);
  }

  async function remove(id: string) {
    await store.deleteNote(id);
    setNotes((n) => n.filter((x) => x.id !== id));
  }

  return (
    <div className="card p-4">
      <h2 className="mb-3 font-semibold">Notes</h2>

      <div className="flex gap-2">
        <textarea
          className="input min-h-[44px] resize-none"
          rows={1}
          placeholder="Log a note — delays, what you saw, how it felt…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') add();
          }}
        />
        <button className="btn-primary" onClick={add} disabled={busy || !body.trim()}>
          Add
        </button>
      </div>

      <div className="mt-4 space-y-2">
        {legacyNote && (
          <div className="rounded-xl border border-edge bg-ink/60 p-3">
            <div className="mb-0.5 text-[11px] uppercase tracking-wide text-muted">From the original log</div>
            <div className="text-sm text-slate-200">{legacyNote}</div>
          </div>
        )}

        {loading ? (
          <div className="py-4 text-center text-sm text-muted">Loading notes…</div>
        ) : notes.length === 0 && !legacyNote ? (
          <div className="py-4 text-center text-sm text-muted">No notes yet.</div>
        ) : (
          notes.map((n) => (
            <div key={n.id} className="group rounded-xl border border-edge bg-ink/60 p-3">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[11px] text-muted">{fmtStamp(n.created_at)}</span>
                <button
                  onClick={() => remove(n.id)}
                  className="text-muted opacity-0 transition group-hover:opacity-100 hover:text-bad"
                  aria-label="Delete note"
                >
                  <IconTrash className="h-4 w-4" />
                </button>
              </div>
              <div className="whitespace-pre-wrap text-sm text-slate-200">{n.body}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
