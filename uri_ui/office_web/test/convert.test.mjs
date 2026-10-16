// Unit tests for the page's workbook conversion and edit extraction: node --test test/
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { cellRef, editsFromMutation, parseCell, toUniver, toUniverStyle } from '../src/convert.js';

test('cell refs round-trip', () => {
  for (const ref of ['A1', 'Z9', 'AA10', 'XFD1048576']) {
    const { row, col } = parseCell(ref);
    assert.equal(cellRef(row, col), ref);
  }
  assert.throws(() => parseCell('1A'));
});

test('workbook converts values, formulas, styles, merges and sizes', () => {
  const wb = { styles: { k: { b: true, fc: '#FF0000', bg: '#FFFF00', ha: 'center', wrap: true, nf: '0.00' } },
    sheets: [{ name: 'Sales', max_row: 5, max_col: 3, merges: ['D1:E1'], col_widths: { A: 22 }, row_heights: { 1: 15 },
      cells: { A1: { v: 'Region', s: 'k' }, B5: { f: '=SUM(B2:B4)', v: 60 }, C2: { v: true } } }] };
  const u = toUniver(wb);
  const s = u.sheets.s0;
  assert.equal(s.name, 'Sales');
  assert.deepEqual(s.cellData[0][0], { v: 'Region', s: 'k' });
  assert.deepEqual(s.cellData[4][1], { f: '=SUM(B2:B4)', v: 60 });
  assert.deepEqual(s.cellData[1][2], { v: 1 });
  assert.deepEqual(s.mergeData, [{ startRow: 0, startColumn: 3, endRow: 0, endColumn: 4 }]);
  assert.equal(s.columnData[0].w, 22 * 7 + 5);
  assert.equal(s.rowData[0].h, 20);
  assert.deepEqual(u.styles.k, toUniverStyle(wb.styles.k));
  assert.deepEqual(u.styles.k, { bl: 1, cl: { rgb: '#FF0000' }, bg: { rgb: '#FFFF00' }, n: { pattern: '0.00' }, ht: 2, tb: 3 });
});

test('edits from a user mutation: values, formulas, clears; style-only writes ignored', () => {
  const edits = editsFromMutation({ subUnitId: 's0', cellValue: {
    1: { 1: { v: 12 }, 2: { f: '=B2*2' }, 3: null, 4: { s: 'k' } } } }, { s0: 'Sales' });
  assert.deepEqual(edits, [
    { sheet: 'Sales', cell: 'B2', value: 12 },
    { sheet: 'Sales', cell: 'C2', formula: '=B2*2' },
    { sheet: 'Sales', cell: 'D2', value: null },
  ]);
});

test('unknown sheet ids produce no edits', () => {
  assert.deepEqual(editsFromMutation({ subUnitId: 'zz', cellValue: { 0: { 0: { v: 1 } } } }, { s0: 'Sales' }), []);
});

test('shared-formula cells (si only, f and v null) are sent as their resolved formula, never as clears (R2-01)', () => {
  const cellValue = { 0: { 1: { f: '=A1*2', si: 'x1' } }, 1: { 1: { si: 'x1', f: null, v: null } },
    2: { 1: { si: 'x1', f: null, v: null } } };
  const resolve = (r, c) => (c === 1 ? `=A${r + 1}*2` : null);
  assert.deepEqual(editsFromMutation({ subUnitId: 's0', cellValue }, { s0: 'Sales' }, resolve), [
    { sheet: 'Sales', cell: 'B1', formula: '=A1*2' },
    { sheet: 'Sales', cell: 'B2', formula: '=A2*2' },
    { sheet: 'Sales', cell: 'B3', formula: '=A3*2' },
  ]);
  // unresolvable: an error entry, never value null
  assert.deepEqual(editsFromMutation({ subUnitId: 's0', cellValue: { 1: { 1: { si: 'x1', f: null, v: null } } } },
    { s0: 'Sales' }), [{ sheet: 'Sales', cell: 'B2', error: 'FORMULA_NOT_RESOLVED' }]);
});

test('rich text (multi-line or partly styled) is sent as its plain text, never as a clear (R3-03)', () => {
  const cellValue = {
    0: { 0: { p: { body: { dataStream: 'line1\rline2\r\n', paragraphs: [{ startIndex: 5 }, { startIndex: 11 }] } },
      v: null, f: null, si: null } },
    1: { 0: { p: { body: { dataStream: 'bold and plain\r\n', textRuns: [{ st: 0, ed: 4, ts: { bl: 1 } }] } }, v: null } },
    2: { 0: { p: { body: { dataStream: 'see \x1Fsite\x1E now\r\n', customRanges: [{}] } }, v: null } },
    3: { 0: { p: { body: { dataStream: '\b\r\n', customBlocks: [{}] } }, v: '', f: null, si: null } },  // cell image
    4: { 0: { p: {}, v: null } },
  };
  assert.deepEqual(editsFromMutation({ subUnitId: 's0', cellValue }, { s0: 'Sales' }), [
    { sheet: 'Sales', cell: 'A1', value: 'line1\nline2' },
    { sheet: 'Sales', cell: 'A2', value: 'bold and plain' },
    { sheet: 'Sales', cell: 'A3', value: 'see site now' },
    { sheet: 'Sales', cell: 'A4', error: 'RICH_TEXT_NOT_READ' },
    { sheet: 'Sales', cell: 'A5', error: 'RICH_TEXT_NOT_READ' },
  ]);
});
