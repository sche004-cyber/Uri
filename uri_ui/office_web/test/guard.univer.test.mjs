// The page's guards against the real Univer 1.0.3 engine (needs `npm ci` in uri_ui/office_web):
//   node --test test/guard.univer.test.mjs
// Headless: core + formula engine + sheets model, the same services the page's preset registers.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { CanceledError, ICommandService, IUniverInstanceService, LocaleType, Univer, UniverInstanceType } from '@univerjs/core';
import { IFunctionService, UniverFormulaEnginePlugin } from '@univerjs/engine-formula';
import { UniverSheetsPlugin } from '@univerjs/sheets';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';

import { BLOCKED_FUNCTIONS, blockFunctions, guardStructure } from '../src/guard.js';

const tick = () => new Promise((r) => setTimeout(r, 50));

function start() {
  const univer = new Univer({ locale: LocaleType.EN_US, locales: { [LocaleType.EN_US]: sheetsCoreEnUS } });
  univer.registerPlugin(UniverFormulaEnginePlugin);
  univer.registerPlugin(UniverSheetsPlugin);
  return univer;
}

const book = (id) => ({ id, sheetOrder: ['s0'], sheets: { s0: { id: 's0', name: 'Sales', rowCount: 20, columnCount: 5,
  cellData: { 0: { 0: { v: 'Region' } }, 4: { 0: { v: 'A5' } } } } } });

test('blocked functions stay unregistered after the first and later workbooks load', async () => {
  const univer = start();
  const fs = univer.__getInjector().get(IFunctionService);
  const guard = blockFunctions(fs);
  univer.createUnit(UniverInstanceType.UNIVER_SHEET, book('w1'));
  await tick();
  assert.ok(fs.hasExecutor('SUM'), 'the formula engine registered its functions');
  for (const n of BLOCKED_FUNCTIONS) assert.equal(fs.hasExecutor(n), false, n);
  assert.deepEqual(guard.present(), []);
  univer.createUnit(UniverInstanceType.UNIVER_SHEET, book('w2'));
  await tick();
  assert.deepEqual(guard.present(), []);
  univer.dispose();
});

test('structural commands are cancelled and the grid is unchanged', async () => {
  const univer = start();
  const injector = univer.__getInjector();
  const refused = [];
  guardStructure(injector.get(ICommandService), CanceledError, (id) => refused.push(id));
  univer.createUnit(UniverInstanceType.UNIVER_SHEET, book('w'));
  await tick();
  const cs = injector.get(ICommandService);
  const wb = injector.get(IUniverInstanceService).getUnit('w');
  const ws = wb.getSheetBySheetId('s0');
  const ok = await cs.executeCommand('sheet.command.insert-row', {
    unitId: 'w', subUnitId: 's0', direction: 'up',
    range: { startRow: 1, endRow: 1, startColumn: 0, endColumn: 4 } });
  assert.equal(ok, false);
  assert.equal(cs.syncExecuteCommand('sheet.mutation.remove-rows', { unitId: 'w', subUnitId: 's0',
    range: { startRow: 0, endRow: 0, startColumn: 0, endColumn: 4 } }), false);
  assert.equal(ws.getCellRaw(4, 0).v, 'A5');
  assert.equal(ws.getCellRaw(0, 0).v, 'Region');
  assert.equal(wb.getSheets().length, 1);
  assert.deepEqual(refused, ['sheet.command.insert-row', 'sheet.mutation.remove-rows']);
  // ordinary cell writes still go through
  assert.notEqual(await cs.executeCommand('sheet.command.set-range-values', { unitId: 'w', subUnitId: 's0',
    range: { startRow: 2, endRow: 2, startColumn: 1, endColumn: 1 }, value: { v: 7 } }), false);
  assert.equal(ws.getCellRaw(2, 1).v, 7);
  univer.dispose();
});
