// Wine Tracker server: a tiny Express API backed by a local SQLite file, which
// also serves the static single-page UI. One container, no external database.
//
// The SQLite file lives at DB_PATH (default /data/wine.db). Map /data to a
// persistent host path (Unraid appdata) and the cellar survives reboots, image
// updates, and container recreation.
import express from 'express';
import Database from 'better-sqlite3';
import { fileURLToPath } from 'node:url';
import { mkdirSync, existsSync } from 'node:fs';
import { dirname } from 'node:path';

const PORT = Number(process.env.PORT || 8080);
const DB_PATH = process.env.DB_PATH || '/data/wine.db';
const PUBLIC_DIR =
  process.env.PUBLIC_DIR || fileURLToPath(new URL('./public', import.meta.url));

// Make sure the directory for the SQLite file exists before opening it.
mkdirSync(dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.exec(`
  create table if not exists wines (
    id         integer primary key autoincrement,
    name       text    not null,
    year       integer,                       -- vintage year; null = non-vintage / unknown
    won_date   text,                          -- YYYY-MM-DD, null for backfilled cellar
    drank_date text,                          -- YYYY-MM-DD, null = still in the cellar
    created_at text    not null default (datetime('now'))
  );
  create index if not exists wines_drank_idx on wines (drank_date);
`);

// --- helpers ---------------------------------------------------------------

// Normalize an optional calendar date to 'YYYY-MM-DD' or null. Rejects garbage.
function cleanDate(v) {
  if (v === undefined || v === null || v === '') return null;
  const s = String(v).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null;
}

// Normalize an optional vintage year to an int in a sane range, or null.
function cleanYear(v) {
  if (v === undefined || v === null || v === '') return null;
  const n = Number.parseInt(v, 10);
  return Number.isInteger(n) && n >= 1800 && n <= 2200 ? n : null;
}

const app = express();
app.use(express.json({ limit: '256kb' }));

const api = express.Router();

api.get('/health', (_req, res) => {
  db.prepare('select 1').get();
  res.json({ ok: true });
});

// List wines. ?status=cellar (default) | drank | all
api.get('/wines', (req, res) => {
  const status = req.query.status || 'cellar';
  let where = '';
  if (status === 'cellar') where = 'where drank_date is null';
  else if (status === 'drank') where = 'where drank_date is not null';
  // Cellar: alphabetical. History: most recently drunk first.
  const order =
    status === 'drank'
      ? 'order by drank_date desc, name collate nocase asc'
      : 'order by name collate nocase asc, year desc';
  res.json(db.prepare(`select * from wines ${where} ${order}`).all());
});

// Add a bottle to the cellar.
api.post('/wines', (req, res) => {
  const name = String(req.body?.name ?? '').trim();
  if (!name) return res.status(400).json({ error: 'name is required' });
  const year = cleanYear(req.body?.year);
  const won_date = cleanDate(req.body?.won_date);
  const info = db
    .prepare('insert into wines (name, year, won_date) values (?, ?, ?)')
    .run(name, year, won_date);
  res.status(201).json(db.prepare('select * from wines where id = ?').get(info.lastInsertRowid));
});

// Update a bottle. Accepts any of name/year/won_date/drank_date. A drank_date
// of null (explicitly) moves the bottle back into the cellar.
api.patch('/wines/:id', (req, res) => {
  const row = db.prepare('select * from wines where id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'not found' });
  const b = req.body ?? {};
  const name = b.name !== undefined ? String(b.name).trim() : row.name;
  if (!name) return res.status(400).json({ error: 'name is required' });
  const year = b.year !== undefined ? cleanYear(b.year) : row.year;
  const won_date = b.won_date !== undefined ? cleanDate(b.won_date) : row.won_date;
  const drank_date = b.drank_date !== undefined ? cleanDate(b.drank_date) : row.drank_date;
  db.prepare('update wines set name = ?, year = ?, won_date = ?, drank_date = ? where id = ?')
    .run(name, year, won_date, drank_date, req.params.id);
  res.json(db.prepare('select * from wines where id = ?').get(req.params.id));
});

api.delete('/wines/:id', (req, res) => {
  db.prepare('delete from wines where id = ?').run(req.params.id);
  res.status(204).end();
});

app.use('/api', api);

// Serve the static UI, with a fallback to index.html for any non-API path.
if (existsSync(PUBLIC_DIR)) {
  app.use(express.static(PUBLIC_DIR));
  app.get(/^(?!\/api).*/, (_req, res) => res.sendFile(`${PUBLIC_DIR}/index.html`));
}

app.listen(PORT, () => console.log(`Wine Tracker listening on :${PORT} (db: ${DB_PATH})`));
