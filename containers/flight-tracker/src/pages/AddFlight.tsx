import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFlights } from '../hooks/useFlights';
import { store } from '../lib/store';
import type { NewFlight } from '../lib/types';

const todayIso = () => new Date().toISOString().slice(0, 10);

const blank: NewFlight = {
  date: todayIso(),
  passengers: 'Janelle + Mark',
  carrier: 'Alaska',
  flight_number: '',
  origin: '',
  destination: '',
  scheduled_departure: null,
  delayed_departure: null,
  gate_push: null,
  takeoff: null,
  scheduled_arrival: null,
  delayed_arrival: null,
  land: null,
  gate_arrive: null,
  tz_change: 0,
  projected_flying_time: null,
  deicing: false,
  gate_occupied: null,
  notes: null,
};

export default function AddFlight() {
  const nav = useNavigate();
  const { flights, reload } = useFlights();
  const [form, setForm] = useState<NewFlight>(blank);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const carriers = Array.from(new Set([...flights.map((f) => f.carrier), 'Alaska', 'United', 'American', 'Delta'])).sort();

  const set = <K extends keyof NewFlight>(k: K, v: NewFlight[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.origin || !form.destination || !form.flight_number) {
      setError('Origin, destination, and flight number are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await store.createFlight({
        ...form,
        origin: form.origin.toUpperCase().trim(),
        destination: form.destination.toUpperCase().trim(),
        carrier: form.carrier.trim(),
        flight_number: form.flight_number.trim(),
      });
      await reload();
      nav(`/flights/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Add a flight</h1>
      <p className="text-sm text-muted">
        Just the high-level info. You'll tag gate push, takeoff, and landing live from the flight page.
      </p>

      <form onSubmit={submit} className="card space-y-4 p-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Date</label>
            <input type="date" className="input" value={form.date} onChange={(e) => set('date', e.target.value)} />
          </div>
          <div>
            <label className="label">Passengers</label>
            <input className="input" value={form.passengers} onChange={(e) => set('passengers', e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Carrier</label>
            <input list="carriers" className="input" value={form.carrier} onChange={(e) => set('carrier', e.target.value)} />
            <datalist id="carriers">
              {carriers.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>
          <div>
            <label className="label">Flight #</label>
            <input className="input" placeholder="1190" value={form.flight_number} onChange={(e) => set('flight_number', e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Origin</label>
            <input
              className="input font-mono uppercase"
              placeholder="SEA"
              maxLength={4}
              value={form.origin}
              onChange={(e) => set('origin', e.target.value.toUpperCase())}
            />
          </div>
          <div>
            <label className="label">Destination</label>
            <input
              className="input font-mono uppercase"
              placeholder="ORD"
              maxLength={4}
              value={form.destination}
              onChange={(e) => set('destination', e.target.value.toUpperCase())}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="label">Sched. departure</label>
            <input
              type="time"
              className="input"
              value={form.scheduled_departure ?? ''}
              onChange={(e) => set('scheduled_departure', e.target.value || null)}
            />
          </div>
          <div>
            <label className="label">Sched. arrival</label>
            <input
              type="time"
              className="input"
              value={form.scheduled_arrival ?? ''}
              onChange={(e) => set('scheduled_arrival', e.target.value || null)}
            />
          </div>
          <div>
            <label className="label">TZ change (h)</label>
            <input
              type="number"
              className="input"
              value={form.tz_change}
              onChange={(e) => set('tz_change', Number(e.target.value) || 0)}
            />
          </div>
        </div>

        {error && <div className="rounded-xl bg-bad/15 px-3 py-2 text-sm text-bad">{error}</div>}

        <div className="flex gap-2">
          <button type="submit" className="btn-primary flex-1" disabled={saving}>
            {saving ? 'Saving…' : 'Save & start logging'}
          </button>
        </div>
      </form>
    </div>
  );
}
