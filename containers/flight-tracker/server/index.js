// Flight Tracker server: serves the built frontend (static) and a JSON API
// backed by Postgres. Single container, connects to an existing Postgres.
import express from 'express';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';
import { db, init } from './db.js';

const PORT = Number(process.env.PORT || 8080);
const PUBLIC_DIR =
  process.env.PUBLIC_DIR || fileURLToPath(new URL('./public', import.meta.url));

const app = express();
app.use(express.json({ limit: '1mb' }));

// Wrap async handlers so rejections become 500s instead of crashing.
const h = (fn) => (req, res) => fn(req, res).catch((err) => {
  console.error(err);
  res.status(500).json({ error: err.message });
});

const api = express.Router();
api.get('/health', h(async (_req, res) => {
  await db.listFlights();
  res.json({ ok: true });
}));
api.get('/flights', h(async (_req, res) => res.json(await db.listFlights())));
api.get('/notes', h(async (_req, res) => res.json(await db.listNotes())));

api.put('/flights/:id', h(async (req, res) => {
  const flight = { ...req.body, id: req.params.id };
  res.json(await db.upsertFlight(flight));
}));
api.delete('/flights/:id', h(async (req, res) => {
  await db.deleteFlight(req.params.id);
  res.status(204).end();
}));

api.put('/notes/:id', h(async (req, res) => {
  const note = { ...req.body, id: req.params.id };
  res.json(await db.upsertNote(note));
}));
api.delete('/notes/:id', h(async (req, res) => {
  await db.deleteNote(req.params.id);
  res.status(204).end();
}));

app.use('/api', api);

// Serve the built SPA with a history-API fallback (non-/api routes -> index).
if (existsSync(PUBLIC_DIR)) {
  app.use(express.static(PUBLIC_DIR));
  app.get(/^(?!\/api).*/, (_req, res) => res.sendFile(`${PUBLIC_DIR}/index.html`));
}

init()
  .then(() => {
    app.listen(PORT, () => console.log(`Flight Tracker listening on :${PORT}`));
  })
  .catch((err) => {
    console.error('Failed to initialize database:', err);
    process.exit(1);
  });
