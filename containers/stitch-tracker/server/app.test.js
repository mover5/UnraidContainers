import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp, openDb } from './app.js';

async function withServer(fn) {
  const server = createApp(openDb(':memory:'), null).listen(0);
  const base = `http://127.0.0.1:${server.address().port}/api`;
  try {
    await fn(base);
  } finally {
    server.close();
  }
}

const stamps = (t) => Object.fromEntries(['name', 'description', 'notes', 'colors', 'steps', 'rows_done', 'status', 'deleted'].map((f) => [f, t]));
const put = (base, doc) =>
  fetch(`${base}/projects/${doc.id}`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(doc) });

test('PUT stores, merges per field, and GET returns it', async () => {
  await withServer(async (base) => {
    const doc = {
      id: 'p1', name: 'Scarf', description: '', notes: '', status: 'active', deleted: false, created_at: 1,
      colors: [{ id: 'c1', name: 'Purple', hex: '#6E3F8F' }],
      steps: [{ id: 's1', rows: 8, color_id: 'c1', text: '' }],
      rows_done: 0, stamps: stamps(10),
    };
    assert.equal((await put(base, doc)).status, 200);

    // Phone (offline) counted rows at t=30; laptop edited notes at t=20 but synced later.
    await put(base, { ...doc, rows_done: 5, stamps: { ...stamps(10), rows_done: 30 } });
    const res = await put(base, { ...doc, notes: '5mm needles', stamps: { ...stamps(10), notes: 20 } });
    const merged = await res.json();
    assert.equal(merged.rows_done, 5);
    assert.equal(merged.notes, '5mm needles');
    assert.equal(merged.colors[0].hex, '#6e3f8f');

    const all = await (await fetch(`${base}/projects`)).json();
    assert.equal(all.length, 1);
    assert.equal(all[0].rows_done, 5);
  });
});

test('rejects bad ids and junk; unknown API paths 404', async () => {
  await withServer(async (base) => {
    assert.equal((await put(base, { id: 'bad id!' })).status, 400);
    assert.equal((await fetch(`${base}/projects/x`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: '"nope"' })).status, 400);
    assert.equal((await fetch(`${base}/nope`)).status, 404);
  });
});
