import { test } from 'node:test';
import assert from 'node:assert/strict';
import { position } from './pattern.ts';
import { mergeProjects } from './merge.ts';
import type { Project } from './types.ts';

const steps = [
  { id: 'a', rows: 2, color_id: 'P', text: '' },
  { id: 'b', rows: 3, color_id: 'C', text: '' },
  { id: 'c', rows: 1, color_id: 'C', text: 'bind off' },
];

test('position walks through steps', () => {
  const at = (rows_done: number) => position({ steps, rows_done });
  assert.equal(at(0).stepIndex, 0);
  assert.equal(at(0).rowInStep, 1);
  assert.equal(at(1).colorChangeAfterThisRow, true); // last Purple row, Camel next
  assert.equal(at(2).stepIndex, 1);
  assert.equal(at(2).justChangedColor, true);
  assert.equal(at(4).colorChangeAfterThisRow, false); // Camel -> Camel
  assert.equal(at(5).justChangedColor, false);
  assert.equal(at(5).step?.text, 'bind off');
  assert.equal(at(5).row, 6);
  assert.equal(at(6).finished, true);
  assert.equal(at(99).finished, true);
});

test('no pattern = plain counter', () => {
  const p = position({ steps: [], rows_done: 7 });
  assert.equal(p.row, 8);
  assert.equal(p.total, 0);
  assert.equal(p.finished, false);
});

test('merge keeps the newest value per field', () => {
  const base = {
    id: 'x', name: 'Scarf', description: '', notes: '', colors: [], steps: [], rows_done: 0,
    status: 'active', deleted: false, created_at: 1,
    stamps: { name: 1, description: 1, notes: 1, colors: 1, steps: 1, rows_done: 1, status: 1, deleted: 1 },
  } as Project;
  const phone = { ...base, rows_done: 14, stamps: { ...base.stamps, rows_done: 50 } };
  const laptop = { ...base, notes: 'use 5mm needles', stamps: { ...base.stamps, notes: 40 } };
  const m1 = mergeProjects(phone, laptop);
  const m2 = mergeProjects(laptop, phone);
  for (const m of [m1, m2]) {
    assert.equal(m.rows_done, 14);
    assert.equal(m.notes, 'use 5mm needles');
    assert.equal(m.stamps.rows_done, 50);
  }
});
