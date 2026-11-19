// Stitch Tracker API + static SPA host. Projects are stored as JSON documents
// in a local SQLite file; clients sync by PUTting whole documents, which the
// server merges field by field (newest write wins per field) and returns.
import express from 'express';
import Database from 'better-sqlite3';
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { isValidId, merge, sanitize, updatedAt } from './project.js';

export function openDb(path) {
  if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
  const db = new Database(path);
  db.pragma('journal_mode = WAL');
  db.exec(`
    create table if not exists projects (
      id         text primary key,
      doc        text    not null,   -- JSON project document
      updated_at integer not null    -- ms epoch, newest field stamp
    );
  `);
  return db;
}

export function createApp(db, publicDirIn) {
  const publicDir = publicDirIn && resolve(publicDirIn);
  const getOne = db.prepare('select doc from projects where id = ?');
  const getAll = db.prepare('select doc from projects order by updated_at desc');
  const upsert = db.prepare(
    `insert into projects (id, doc, updated_at) values (@id, @doc, @updated_at)
     on conflict(id) do update set doc = excluded.doc, updated_at = excluded.updated_at`
  );
  const save = db.transaction((incoming) => {
    const row = getOne.get(incoming.id);
    const merged = row ? merge(JSON.parse(row.doc), incoming) : incoming;
    upsert.run({ id: merged.id, doc: JSON.stringify(merged), updated_at: updatedAt(merged) });
    return merged;
  });

  const app = express();
  app.use(express.json({ limit: '2mb' }));

  const api = express.Router();
  api.get('/health', (_req, res) => {
    db.prepare('select 1').get();
    res.json({ ok: true });
  });

  // Every project, including deleted tombstones (so deletes propagate).
  api.get('/projects', (_req, res) => {
    res.json(getAll.all().map((r) => JSON.parse(r.doc)));
  });

  api.put('/projects/:id', (req, res) => {
    if (!isValidId(req.params.id)) return res.status(400).json({ error: 'bad id' });
    const doc = sanitize(req.body, req.params.id);
    if (!doc) return res.status(400).json({ error: 'bad project' });
    res.json(save(doc));
  });

  api.use((_req, res) => res.status(404).json({ error: 'not found' }));
  app.use('/api', api);

  if (publicDir && existsSync(publicDir)) {
    app.use(express.static(publicDir, { index: false }));
    // SPA fallback for client routes; /api/* already 404s above.
    app.get(/^(?!\/api).*/, (_req, res) => res.sendFile(join(publicDir, 'index.html')));
  }
  return app;
}
