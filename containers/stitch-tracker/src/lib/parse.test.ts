import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parsePattern } from './parse.ts';

const summarize = (text: string, existing = []) => {
  const r = parsePattern(text, existing);
  const name = (id: string | null) => [...existing, ...r.newColors].find((c: { id: string }) => c.id === id)?.name ?? null;
  return { steps: r.steps.map((s) => [s.rows, name(s.color_id), s.text]), colors: r.newColors.map((c) => c.name), skipped: r.skipped };
};

test('the Doctor Who scarf sample', () => {
  const r = summarize(`Doctor Who Scarf
Requires purple, camel, bronze, mustard, rust, green, and grey yarn.
Cast On 60 stitches

8 Purple
26 Camel
8 Bronze
6 Mustard
12 Rust
8 Purple
etc.`);
  assert.deepEqual(r.steps, [
    [8, 'Purple', ''],
    [26, 'Camel', ''],
    [8, 'Bronze', ''],
    [6, 'Mustard', ''],
    [12, 'Rust', ''],
    [8, 'Purple', ''],
  ]);
  assert.deepEqual(r.colors, ['Purple', 'Camel', 'Bronze', 'Mustard', 'Rust']); // Purple reused, not duplicated
  assert.deepEqual(r.skipped, [
    'Doctor Who Scarf',
    'Requires purple, camel, bronze, mustard, rust, green, and grey yarn.',
    'Cast On 60 stitches',
    'etc.',
  ]);
});

test('row and range instructions', () => {
  assert.deepEqual(summarize('Row 1: k2, p2 across\nRows 2-5: knit\nRow 6 - purl').steps, [
    [1, null, 'k2, p2 across'],
    [4, null, 'knit'],
    [1, null, 'purl'],
  ]);
});

test('color plus instruction, alternate phrasings', () => {
  assert.deepEqual(summarize('12 Rust - slip first st\n4 rows in Heather Grey\nGreen: 10\n- 3 x Navy\n1. 2 Cream').steps, [
    [12, 'Rust', 'slip first st'],
    [4, 'Heather Grey', ''],
    [10, 'Green', ''],
    [3, 'Navy', ''],
    [2, 'Cream', ''],
  ]);
});

test('reuses existing palette colors, case-insensitively', () => {
  const existing = [{ id: 'p', name: 'Purple', hex: '#000000' }];
  const r = parsePattern('8 purple\n2 Dusk', existing);
  assert.equal(r.steps[0].color_id, 'p');
  assert.equal(r.newColors.length, 0);
  // "Dusk" isn't a color word, so it's kept as an instruction rather than invented as a color.
  assert.equal(r.steps[1].text, 'Dusk');
});

test('a bare count becomes plain rows', () => {
  assert.deepEqual(summarize('20').steps, [[20, null, '']]);
});
