// Parses scripts/source-data.md (the original Google Sheet export) into
// src/data/seedFlights.json. Run once: `node scripts/parse-source.mjs`.
// Ids are generated and frozen into the JSON so they stay stable across runs.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const srcMd = join(__dirname, 'source-data.md');
const outJson = join(root, 'src', 'data', 'seedFlights.json');

const clean = (s) => (s ?? '').trim();

// Only keep values that look like a real HH:MM clock time.
const timeOrNull = (s) => {
  const v = clean(s);
  return /^\d{1,2}:\d{2}$/.test(v) ? v.padStart(5, '0') : null;
};

const intOrZero = (s) => {
  const v = clean(s).replace(/\\?-/, '-').replace('\\', '');
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
};

const boolOrNull = (s) => {
  const v = clean(s).toLowerCase();
  if (v === 'yes') return true;
  if (v === 'no') return false;
  return null;
};

// Convert m/d/yyyy -> yyyy-mm-dd
const isoDate = (s) => {
  const [m, d, y] = clean(s).split('/');
  if (!y) return null;
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
};

// Preserve previously assigned ids so they remain stable.
const existing = existsSync(outJson)
  ? JSON.parse(readFileSync(outJson, 'utf8'))
  : [];
const idByKey = new Map(
  existing.map((f) => [`${f.date}|${f.flight_number}|${f.origin}|${f.destination}`, f.id])
);

const lines = readFileSync(srcMd, 'utf8')
  .split('\n')
  .filter((l) => l.trim().startsWith('|'));

// Drop header (row 0) and separator (row 1).
const rows = lines.slice(2);

const flights = rows.map((line) => {
  // Split on un-escaped pipes, trim the leading/trailing empty cells.
  const cells = line.split('|').slice(1, -1).map((c) => c.replace(/\\#/g, '#'));
  const [
    date, passengers, carrier, flightNo, origin, destination,
    schedDep, delayedDep, gatePush, takeoff, schedArr, delayedArr,
    land, gateArrive, tz, projFly, deicing, gateOccupied, notes,
  ] = cells;

  const d = isoDate(date);
  const key = `${d}|${clean(flightNo)}|${clean(origin)}|${clean(destination)}`;

  return {
    id: idByKey.get(key) ?? randomUUID(),
    date: d,
    passengers: clean(passengers),
    carrier: clean(carrier),
    flight_number: clean(flightNo),
    origin: clean(origin).toUpperCase(),
    destination: clean(destination).toUpperCase(),
    scheduled_departure: timeOrNull(schedDep),
    delayed_departure: timeOrNull(delayedDep),
    gate_push: timeOrNull(gatePush),
    takeoff: timeOrNull(takeoff),
    scheduled_arrival: timeOrNull(schedArr),
    delayed_arrival: timeOrNull(delayedArr),
    land: timeOrNull(land),
    gate_arrive: timeOrNull(gateArrive),
    tz_change: intOrZero(tz),
    projected_flying_time: clean(projFly) || null,
    deicing: boolOrNull(deicing) ?? false,
    gate_occupied: boolOrNull(gateOccupied),
    notes: clean(notes) || null,
  };
});

writeFileSync(outJson, JSON.stringify(flights, null, 2) + '\n');
console.log(`Wrote ${flights.length} flights to ${outJson}`);
