// Postgres access layer: connection pool, schema bootstrap, optional seeding,
// and CRUD used by the API. Connects to an existing Postgres via DATABASE_URL
// (or standard PG* env vars).
import pg from 'pg';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const { Pool } = pg;

const useSsl = process.env.DATABASE_SSL === 'true';
export const pool = new Pool({
  connectionString: process.env.DATABASE_URL || undefined,
  ssl: useSsl ? { rejectUnauthorized: false } : undefined,
});

// Data columns (excludes server-managed created_at/updated_at).
export const FLIGHT_COLUMNS = [
  'id', 'date', 'passengers', 'carrier', 'flight_number', 'origin', 'destination',
  'scheduled_departure', 'delayed_departure', 'gate_push', 'takeoff',
  'scheduled_arrival', 'delayed_arrival', 'land', 'gate_arrive', 'tz_change',
  'projected_flying_time', 'deicing', 'gate_occupied', 'notes',
];
const NOTE_COLUMNS = ['id', 'flight_id', 'body', 'created_at'];

const SCHEMA = `
create table if not exists flights (
  id                    uuid primary key,
  date                  date not null,
  passengers            text not null default '',
  carrier               text not null default '',
  flight_number         text not null default '',
  origin                text not null,
  destination           text not null,
  scheduled_departure   text,
  delayed_departure     text,
  gate_push             text,
  takeoff               text,
  scheduled_arrival     text,
  delayed_arrival       text,
  land                  text,
  gate_arrive           text,
  tz_change             integer not null default 0,
  projected_flying_time text,
  deicing               boolean not null default false,
  gate_occupied         boolean,
  notes                 text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create table if not exists flight_notes (
  id         uuid primary key,
  flight_id  uuid not null references flights (id) on delete cascade,
  body       text not null,
  created_at timestamptz not null default now()
);
create index if not exists flights_date_idx on flights (date);
create index if not exists flight_notes_flight_idx on flight_notes (flight_id);
`;

// Build an "INSERT ... ON CONFLICT (id) DO UPDATE" statement for a column set.
function upsertSql(table, columns) {
  const cols = columns.join(', ');
  const params = columns.map((_, i) => `$${i + 1}`).join(', ');
  const updates = columns
    .filter((c) => c !== 'id')
    .map((c) => `${c} = excluded.${c}`)
    .concat(table === 'flights' ? ['updated_at = now()'] : [])
    .join(', ');
  return `insert into ${table} (${cols}) values (${params})
          on conflict (id) do update set ${updates}
          returning *`;
}

const pick = (obj, cols) => cols.map((c) => (obj[c] === undefined ? null : obj[c]));

export async function init() {
  await pool.query(SCHEMA);
  await maybeSeed();
}

async function maybeSeed() {
  if (process.env.SEED_ON_EMPTY === 'false') return;
  const { rows } = await pool.query('select count(*)::int as n from flights');
  if (rows[0].n > 0) return;

  const here = fileURLToPath(new URL('.', import.meta.url));
  const candidates = [
    process.env.SEED_FILE,
    `${here}seed/flights.json`,
    `${here}../src/data/seedFlights.json`,
  ].filter(Boolean);
  const path = candidates.find((p) => existsSync(p));
  if (!path) {
    console.log('No seed file found; starting with an empty database.');
    return;
  }
  const flights = JSON.parse(readFileSync(path, 'utf8'));
  for (const f of flights) {
    await pool.query(upsertSql('flights', FLIGHT_COLUMNS), pick(f, FLIGHT_COLUMNS));
  }
  console.log(`Seeded ${flights.length} flights from ${path}`);
}

export const db = {
  listFlights: () =>
    pool.query('select * from flights order by date asc').then((r) => r.rows),
  listNotes: () =>
    pool.query('select * from flight_notes order by created_at desc').then((r) => r.rows),
  upsertFlight: (f) =>
    pool.query(upsertSql('flights', FLIGHT_COLUMNS), pick(f, FLIGHT_COLUMNS)).then((r) => r.rows[0]),
  deleteFlight: (id) => pool.query('delete from flights where id = $1', [id]),
  upsertNote: (n) =>
    pool.query(upsertSql('flight_notes', NOTE_COLUMNS), pick(n, NOTE_COLUMNS)).then((r) => r.rows[0]),
  deleteNote: (id) => pool.query('delete from flight_notes where id = $1', [id]),
};
