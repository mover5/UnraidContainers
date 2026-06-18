import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useFlights } from '../hooks/useFlights';
import { Spinner, StatCard } from '../components/ui';
import { fmtDelay, fmtDuration } from '../lib/time';
import { allPeople, byCarrier, byRoute, delayTrend, summary, taxiByAirport } from '../lib/analytics';

const axis = { stroke: '#8aa0c6', fontSize: 12 };
const grid = '#243250';

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card p-4">
      <div className="mb-3">
        <h2 className="font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function TipBox({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-edge bg-ink px-3 py-2 text-xs shadow-lg">{children}</div>;
}

function PersonTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1 text-sm font-medium transition ${
        active ? 'bg-sky text-ink' : 'text-muted hover:text-slate-200'
      }`}
    >
      {label}
    </button>
  );
}

export default function Dashboard() {
  const { flights, loading } = useFlights();
  const [person, setPerson] = useState('');

  const people = useMemo(() => allPeople(flights), [flights]);
  const view = useMemo(
    () => (person ? flights.filter((f) => f.passengers.includes(person)) : flights),
    [flights, person]
  );

  const s = useMemo(() => summary(view), [view]);
  const taxi = useMemo(() => taxiByAirport(view).slice(0, 10), [view]);
  const trend = useMemo(() => delayTrend(view).slice(-24), [view]);
  const carriers = useMemo(() => byCarrier(view.filter((f) => f.gate_arrive)), [view]);
  const routes = useMemo(() => byRoute(view).slice(0, 8), [view]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        {people.length > 1 && (
          <div className="flex flex-wrap gap-1 rounded-xl border border-edge bg-panel p-1">
            <PersonTab label="Everyone" active={person === ''} onClick={() => setPerson('')} />
            {people.map((p) => (
              <PersonTab key={p} label={p} active={person === p} onClick={() => setPerson(p)} />
            ))}
          </div>
        )}
      </div>
      {person && (
        <p className="-mt-2 text-sm text-muted">
          Showing {view.length} {view.length === 1 ? 'flight' : 'flights'} with {person}.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Flights logged" value={s.completed} sub={`${s.upcoming} upcoming`} />
        <StatCard
          label="On-time rate"
          value={s.onTimeRate === null ? '—' : `${Math.round(s.onTimeRate * 100)}%`}
          sub="within 15m of schedule"
          tone={s.onTimeRate !== null && s.onTimeRate >= 0.7 ? 'good' : 'warn'}
        />
        <StatCard label="Avg taxi-out" value={fmtDuration(s.avgTaxiOut)} sub="gate push → wheels up" />
        <StatCard
          label="Avg dep. delay"
          value={fmtDelay(s.avgDepDelay)}
          sub="vs scheduled"
          tone={s.avgDepDelay !== null && s.avgDepDelay > 15 ? 'bad' : 'default'}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total time aloft" value={fmtDuration(s.totalAir)} />
        <StatCard label="Airports visited" value={s.uniqueAirports} />
        <StatCard
          label="Longest flight"
          value={s.longest ? `${s.longest.origin}→${s.longest.destination}` : '—'}
          sub={s.longest ? s.longest.carrier : undefined}
        />
        <StatCard label="Carriers flown" value={carriers.length} />
      </div>

      {/* Taxi time by airport */}
      <ChartCard title="Taxi time by airport" subtitle="Avg minutes — taxi-out (departing) vs taxi-in (arriving)">
        <ResponsiveContainer width="100%" height={Math.max(220, taxi.length * 34)}>
          <BarChart data={taxi} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid stroke={grid} horizontal={false} />
            <XAxis type="number" tick={axis} tickFormatter={(v) => `${v}m`} />
            <YAxis type="category" dataKey="airport" tick={axis} width={44} />
            <Tooltip
              cursor={{ fill: '#ffffff08' }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TipBox>
                    <div className="font-semibold text-slate-100">{label}</div>
                    {payload.map((p) => (
                      <div key={p.name} style={{ color: p.color as string }}>
                        {p.name}: {fmtDuration(p.value as number)}
                      </div>
                    ))}
                  </TipBox>
                ) : null
              }
            />
            <Bar dataKey="taxiOut" name="Taxi-out" fill="#38bdf8" radius={[0, 4, 4, 0]} />
            <Bar dataKey="taxiIn" name="Taxi-in" fill="#22d3ee" radius={[0, 4, 4, 0]} opacity={0.55} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Departure delay trend */}
      <ChartCard title="Departure delay" subtitle="Per flight (most recent 24) — minutes vs scheduled push">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={trend} margin={{ left: -8, right: 8 }}>
            <CartesianGrid stroke={grid} vertical={false} />
            <XAxis dataKey="label" tick={{ ...axis, fontSize: 10 }} interval="preserveStartEnd" angle={-30} textAnchor="end" height={50} />
            <YAxis tick={axis} tickFormatter={(v) => `${v}m`} />
            <Tooltip
              cursor={{ fill: '#ffffff08' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TipBox>
                    <div className="font-semibold text-slate-100">{payload[0].payload.label}</div>
                    <div className="text-muted">{payload[0].payload.date}</div>
                    <div>Departure: {fmtDelay(payload[0].payload.depDelay)}</div>
                    <div>Arrival: {fmtDelay(payload[0].payload.arrDelay)}</div>
                  </TipBox>
                ) : null
              }
            />
            <Bar dataKey="depDelay" name="Dep delay" radius={[4, 4, 0, 0]}>
              {trend.map((d, i) => (
                <Cell key={i} fill={(d.depDelay ?? 0) <= 0 ? '#34d399' : (d.depDelay ?? 0) <= 15 ? '#fbbf24' : '#f87171'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid gap-3 lg:grid-cols-2">
        {/* On-time by carrier */}
        <ChartCard title="On-time rate by carrier" subtitle="Share within 15m of schedule">
          <div className="space-y-2.5">
            {carriers.map((c) => (
              <div key={c.carrier}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>{c.carrier} <span className="text-muted">· {c.n}</span></span>
                  <span className="tabular-nums text-muted">
                    {c.onTimeRate === null ? '—' : `${Math.round(c.onTimeRate * 100)}%`} · {fmtDelay(c.avgDepDelay)}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-ink">
                  <div
                    className="h-full rounded-full bg-sky"
                    style={{ width: `${Math.round((c.onTimeRate ?? 0) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartCard>

        {/* Most-flown routes */}
        <ChartCard title="Most-flown routes" subtitle="Avg air time / block time">
          <div className="divide-y divide-edge">
            {routes.map((r) => (
              <div key={r.route} className="flex items-center justify-between py-2 text-sm">
                <span className="font-mono font-medium">{r.route}</span>
                <span className="flex items-center gap-3 text-muted">
                  <span className="chip bg-panel2">{r.n}×</span>
                  <span className="tabular-nums">air {fmtDuration(r.avgAir)}</span>
                  <span className="tabular-nums">block {fmtDuration(r.avgBlock)}</span>
                </span>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
