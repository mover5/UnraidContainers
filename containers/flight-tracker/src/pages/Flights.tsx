import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useFlights } from '../hooks/useFlights';
import { CarrierBadge, EmptyState, RouteBadge, Spinner, fmtDate } from '../components/ui';
import { IconChevron } from '../components/icons';
import { departureDelay, fmtDelay, fmtDuration, taxiOut, isComplete } from '../lib/time';
import type { Flight } from '../lib/types';

export default function Flights() {
  const { flights, loading } = useFlights();
  const [q, setQ] = useState('');
  const [carrier, setCarrier] = useState('');

  const carriers = useMemo(
    () => Array.from(new Set(flights.map((f) => f.carrier))).sort(),
    [flights]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return flights
      .filter((f) => (carrier ? f.carrier === carrier : true))
      .filter((f) =>
        needle
          ? [f.origin, f.destination, f.carrier, f.flight_number, f.passengers, f.notes ?? '']
              .join(' ')
              .toLowerCase()
              .includes(needle)
          : true
      )
      .sort((a, b) => b.date.localeCompare(a.date));
  }, [flights, q, carrier]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold">Flights <span className="text-muted">· {flights.length}</span></h1>
        <Link to="/add" className="btn-primary self-start sm:self-auto">+ Add flight</Link>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          className="input"
          placeholder="Search route, carrier, notes…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="input sm:w-48" value={carrier} onChange={(e) => setCarrier(e.target.value)}>
          <option value="">All carriers</option>
          {carriers.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No flights match" hint="Try clearing the filters." />
      ) : (
        <div className="space-y-2">
          {filtered.map((f) => (
            <FlightRow key={f.id} f={f} />
          ))}
        </div>
      )}
    </div>
  );
}

function FlightRow({ f }: { f: Flight }) {
  const upcoming = !isComplete(f) && !f.takeoff;
  return (
    <Link
      to={`/flights/${f.id}`}
      className="card flex items-center gap-3 p-3 transition hover:border-sky"
    >
      <div className="w-16 shrink-0 text-center">
        <div className="text-xs text-muted">{fmtDate(f.date, { month: 'short', day: 'numeric' })}</div>
        <div className="text-[11px] text-muted">{f.date.slice(0, 4)}</div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <RouteBadge origin={f.origin} destination={f.destination} />
          <CarrierBadge carrier={f.carrier} />
        </div>
        <div className="mt-0.5 truncate text-xs text-muted">
          {f.carrier} {f.flight_number} · {f.passengers}
          {f.notes ? ` · ${f.notes}` : ''}
        </div>
      </div>
      <div className="hidden shrink-0 text-right sm:block">
        {upcoming ? (
          <span className="chip bg-sky/15 text-sky">Upcoming</span>
        ) : (
          <>
            <div className="text-xs text-muted">taxi-out {fmtDuration(taxiOut(f))}</div>
            <DelayChip min={departureDelay(f)} />
          </>
        )}
      </div>
      <IconChevron className="h-4 w-4 shrink-0 text-muted" />
    </Link>
  );
}

function DelayChip({ min }: { min: number | null }) {
  if (min === null) return null;
  const tone = min <= 0 ? 'bg-good/15 text-good' : min <= 15 ? 'bg-warn/15 text-warn' : 'bg-bad/15 text-bad';
  return <span className={`chip ${tone}`}>{fmtDelay(min)}</span>;
}
