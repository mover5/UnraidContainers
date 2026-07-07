import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useFlights } from '../hooks/useFlights';
import { store } from '../lib/store';
import type { Flight } from '../lib/types';
import {
  airTime,
  arrivalDelay,
  blockTime,
  departureDelay,
  fmtDelay,
  fmtDuration,
  taxiIn,
  taxiOut,
} from '../lib/time';
import { CarrierBadge, Spinner, fmtDate } from '../components/ui';
import { IconBack, IconCheck, IconTrash } from '../components/icons';
import LiveLogger from '../components/LiveLogger';
import NotesThread from '../components/NotesThread';
import PassengerEditor from '../components/PassengerEditor';
import { allPeople } from '../lib/analytics';

export default function FlightDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { flights, reload } = useFlights();
  const [flight, setFlight] = useState<Flight | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedFlash, setSavedFlash] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (savedTimer.current) clearTimeout(savedTimer.current);
  }, []);

  useEffect(() => {
    let alive = true;
    const cached = flights.find((f) => f.id === id);
    if (cached) {
      setFlight(cached);
      setLoading(false);
    }
    if (id)
      store.getFlight(id).then((f) => {
        if (alive) {
          setFlight(f);
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function patch(p: Partial<Flight>) {
    if (!flight) return;
    setFlight({ ...flight, ...p }); // optimistic
    await store.updateFlight(flight.id, p);
    reload();
    // Visible confirmation that the autosave landed.
    setSavedFlash(true);
    if (savedTimer.current) clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSavedFlash(false), 1600);
  }

  async function del() {
    if (!flight) return;
    if (!confirm('Delete this flight and its notes?')) return;
    await store.deleteFlight(flight.id);
    await reload();
    nav('/flights');
  }

  if (loading) return <Spinner />;
  if (!flight) return <div className="card p-6 text-center text-muted">Flight not found.</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/flights" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-sky">
          <IconBack className="h-4 w-4" /> All flights
        </Link>
        <button onClick={del} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-bad">
          <IconTrash className="h-4 w-4" /> Delete
        </button>
      </div>

      {/* Header */}
      <div className="card p-5">
        <div className="flex items-center gap-3 text-3xl font-bold tracking-tight">
          <span className="font-mono">{flight.origin}</span>
          <span className="text-muted">→</span>
          <span className="font-mono">{flight.destination}</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
          <CarrierBadge carrier={flight.carrier} />
          <span>{flight.carrier} {flight.flight_number}</span>
          <span>·</span>
          <span>{fmtDate(flight.date)}</span>
          {flight.passengers.length > 0 && (
            <>
              <span>·</span>
              <span>{flight.passengers.join(', ')}</span>
            </>
          )}
        </div>
      </div>

      {/* People */}
      <div className="card space-y-2 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">People</h2>
          <SavedFlash show={savedFlash} />
        </div>
        <PassengerEditor
          value={flight.passengers}
          onChange={(v) => patch({ passengers: v })}
          suggestions={allPeople(flights)}
        />
      </div>

      <LiveLogger flight={flight} onPatch={patch} />

      {/* Derived metrics */}
      <div className="card p-4">
        <h2 className="mb-3 font-semibold">Metrics</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Metric label="Taxi-out" value={fmtDuration(taxiOut(flight))} hint="push → wheels up" />
          <Metric label="Air time" value={fmtDuration(airTime(flight))} hint="wheels up → down" />
          <Metric label="Taxi-in" value={fmtDuration(taxiIn(flight))} hint="touchdown → gate" />
          <Metric label="Block time" value={fmtDuration(blockTime(flight))} hint="gate → gate" />
          <Metric label="Dep. delay" value={fmtDelay(departureDelay(flight))} tone={delayTone(departureDelay(flight))} />
          <Metric label="Arr. delay" value={fmtDelay(arrivalDelay(flight))} tone={delayTone(arrivalDelay(flight))} />
        </div>
        {flight.projected_flying_time && (
          <div className="mt-3 text-xs text-muted">
            Airline-projected flying time: <span className="text-slate-300">{flight.projected_flying_time}</span>
          </div>
        )}
      </div>

      {/* Schedule & flags */}
      <div className="card space-y-4 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Schedule &amp; details</h2>
          <SavedFlash show={savedFlash} />
        </div>
        <p className="-mt-2 text-xs text-muted">Changes save automatically.</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <TimeField label="Sched. departure" value={flight.scheduled_departure} onChange={(v) => patch({ scheduled_departure: v })} />
          <TimeField label="Delayed departure" value={flight.delayed_departure} onChange={(v) => patch({ delayed_departure: v })} />
          <TimeField label="Sched. arrival" value={flight.scheduled_arrival} onChange={(v) => patch({ scheduled_arrival: v })} />
          <TimeField label="Delayed arrival" value={flight.delayed_arrival} onChange={(v) => patch({ delayed_arrival: v })} />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className="label">TZ change (hours)</label>
            <input
              type="number"
              className="input"
              value={flight.tz_change}
              onChange={(e) => patch({ tz_change: Number(e.target.value) || 0 })}
            />
            <p className="mt-1 text-xs text-muted">Destination offset − origin. West = negative (ORD→SEA = −2), east = positive.</p>
          </div>
          <Toggle label="Deicing?" value={flight.deicing} onChange={(v) => patch({ deicing: v })} />
          <Toggle
            label="Gate occupied on arrival?"
            value={flight.gate_occupied}
            onChange={(v) => patch({ gate_occupied: v })}
            nullable
          />
        </div>
      </div>

      <NotesThread flightId={flight.id} legacyNote={flight.notes} />
    </div>
  );
}

function SavedFlash({ show }: { show: boolean }) {
  return (
    <span
      aria-live="polite"
      className={`inline-flex items-center gap-1 text-[11px] font-medium text-good transition-opacity duration-300 ${
        show ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <IconCheck className="h-3.5 w-3.5" /> Saved
    </span>
  );
}

function delayTone(min: number | null): 'good' | 'warn' | 'bad' | undefined {
  if (min === null) return undefined;
  return min <= 0 ? 'good' : min <= 15 ? 'warn' : 'bad';
}

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: 'good' | 'warn' | 'bad';
}) {
  const color = tone === 'good' ? 'text-good' : tone === 'warn' ? 'text-warn' : tone === 'bad' ? 'text-bad' : 'text-slate-100';
  return (
    <div className="rounded-xl border border-edge bg-ink/60 p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-xl font-semibold tabular-nums ${color}`}>{value}</div>
      {hint && <div className="text-[11px] text-muted">{hint}</div>}
    </div>
  );
}

function TimeField({ label, value, onChange }: { label: string; value: string | null; onChange: (v: string | null) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="time" className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)} />
    </div>
  );
}

function Toggle({
  label,
  value,
  onChange,
  nullable = false,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
  nullable?: boolean;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex h-[42px] items-center gap-1 rounded-xl border border-edge bg-ink p-1">
        {(nullable ? [true, false] : [true, false]).map((opt) => {
          const active = value === opt;
          return (
            <button
              key={String(opt)}
              onClick={() => onChange(opt)}
              className={`flex-1 rounded-lg px-2 py-1.5 text-sm font-medium transition ${
                active ? (opt ? 'bg-good/20 text-good' : 'bg-panel2 text-slate-200') : 'text-muted hover:text-slate-200'
              }`}
            >
              {opt ? 'Yes' : 'No'}
            </button>
          );
        })}
      </div>
    </div>
  );
}
