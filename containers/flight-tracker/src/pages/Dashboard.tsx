import { useMemo } from 'react';
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
import { byCarrier, byRoute, delayTrend, summary, taxiByAirport } from '../lib/analytics';

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

export default function Dashboard() {
  const { flights, loading } = useFlights();

  const s = useMemo(() => summary(flights), [flights]);
  const taxi = useMemo(() => taxiByAirport(flights).slice(0, 10), [flights]);
  const trend = useMemo(() => delayTrend(flights).slice(-24), [flights]);
  const carriers = useMemo(() => byCarrier(flights.filter((f) => f.gate_arrive)), [flights]);
  const routes = useMemo(() => byRoute(flights).slice(0, 8), [flights]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Dashboard</h1>

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
