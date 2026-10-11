// Page edits from shared-formula writes against the real Univer 1.0.3 engine (needs `npm ci` in uri_ui/office_web):
//   node --test test/edits.univer.test.mjs
// Formula fill and insert-function write {f, si} to the first cell and {si, f: null, v: null} to the rest (R2-01).
// Those cells must reach the service as their formulas, never as empty values.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ICommandService, LocaleType, Univer, UniverInstanceType } from '@univerjs/core';
import { FormulaDataModel, UniverFormulaEnginePlugin } from '@univerjs/engine-formula';
import { SheetsSelectionsService, UniverSheetsPlugin } from '@univerjs/sheets';
import { InsertFunctionCommand } from '@univerjs/sheets-formula';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';

import { editsFromMutation } from '../src/convert.js';

const tick = () => new Promise((r) => setTimeout(r, 50));

// The same path as main.js: user set-range-values mutations -> editsFromMutation with the formula data model resolver.
function start() {
  const univer = new Univer({ locale: LocaleType.EN_US, locales: { [LocaleType.EN_US]: sheetsCoreEnUS } });
  univer.registerPlugin(UniverFormulaEnginePlugin);
  univer.registerPlugin(UniverSheetsPlugin);
  univer.createUnit(UniverInstanceType.UNIVER_SHEET, { id: 'w', sheetOrder: ['s0'], sheets: { s0: { id: 's0',
    name: 'Sales', rowCount: 20, columnCount: 5, cellData: { 0: { 0: { v: 2 } }, 1: { 0: { v: 3 } }, 2: { 0: { v: 4 } },
      3: { 0: { v: 5 } }, 4: { 0: { v: 6 } } } } } });
  const injector = univer.__getInjector();
  const cs = injector.get(ICommandService);
  const formulas = injector.get(FormulaDataModel);
  const edits = [];
  cs.onCommandExecuted((cmd, options) => {
    if (cmd.id !== 'sheet.mutation.set-range-values') return;
    const o = options || {};
    if (o.onlyLocal || o.fromFormula) return;
    const p = cmd.params || {};
    edits.push(...editsFromMutation(p, { s0: 'Sales' },
      (row, col) => formulas.getFormulaStringByCell(row, col, p.subUnitId, p.unitId)));
  });
  return { univer, injector, cs, edits };
}

test('insert-function over a range sends every cell as its formula', async () => {
  const { univer, injector, cs, edits } = start();
  await tick();
  cs.registerCommand(InsertFunctionCommand);
  // The toolbar runs it with the target range selected.
  const range = { startRow: 0, endRow: 2, startColumn: 1, endColumn: 1 };
  injector.get(SheetsSelectionsService).setSelections([{ range, primary: null, style: null }]);
  assert.notEqual(await cs.executeCommand(InsertFunctionCommand.id, { list: [{
    range, primary: { row: 0, column: 1 }, formula: '=A1*2' }] }),
  false);
  assert.deepEqual(edits, [
    { sheet: 'Sales', cell: 'B1', formula: '=A1*2' },
    { sheet: 'Sales', cell: 'B2', formula: '=A2*2' },
    { sheet: 'Sales', cell: 'B3', formula: '=A3*2' },
  ]);
  univer.dispose();
});

test('auto-fill copy shape (si-only cells, f and v null) sends formulas, not clears', async () => {
  const { univer, cs, edits } = start();
  await tick();
  // FormulaAutoFillController._fillCopyFormula: first new cell {si, f}, the rest {si, f: null, v: null}.
  cs.syncExecuteCommand('sheet.mutation.set-range-values', { unitId: 'w', subUnitId: 's0', cellValue: {
    0: { 1: { si: 'abc123', f: '=A1*2', v: null } }, 1: { 1: { si: 'abc123', f: null, v: null, p: null, t: null } },
    2: { 1: { si: 'abc123', f: null, v: null, p: null, t: null } } } });
  // Filling further from an si-only source copies its id only: no cell in the mutation carries f.
  cs.syncExecuteCommand('sheet.mutation.set-range-values', { unitId: 'w', subUnitId: 's0', cellValue: {
    3: { 1: { si: 'abc123', f: null, v: null, p: null, t: null } },
    4: { 1: { si: 'abc123', f: null, v: null, p: null, t: null } } } });
  assert.deepEqual(edits, [
    { sheet: 'Sales', cell: 'B1', formula: '=A1*2' },
    { sheet: 'Sales', cell: 'B2', formula: '=A2*2' },
    { sheet: 'Sales', cell: 'B3', formula: '=A3*2' },
    { sheet: 'Sales', cell: 'B4', formula: '=A4*2' },
    { sheet: 'Sales', cell: 'B5', formula: '=A5*2' },
  ]);
  assert.ok(edits.every((e) => !('value' in e)), 'no shared-formula cell is sent as an empty value');
  univer.dispose();
});

test('a shared-formula id the engine cannot resolve is an error, never an empty value', async () => {
  const { univer, cs, edits } = start();
  await tick();
  cs.syncExecuteCommand('sheet.mutation.set-range-values', { unitId: 'w', subUnitId: 's0', cellValue: {
    6: { 1: { si: 'nosuch', f: null, v: null } } } });
  assert.deepEqual(edits, [{ sheet: 'Sales', cell: 'B7', error: 'FORMULA_NOT_RESOLVED' }]);
  univer.dispose();
});
