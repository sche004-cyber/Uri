// The page's guards against the real Univer 1.0.3 engine (needs `npm ci` in uri_ui/office_web):
//   node --test test/guard.univer.test.mjs
// Headless: core + formula engine + sheets model, the same services the page's preset registers.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { CanceledError, ICommandService, IUniverInstanceService, LocaleType, Univer, UniverInstanceType } from '@univerjs/core';
import { IFunctionService, UniverFormulaEnginePlugin } from '@univerjs/engine-formula';
import { SetBoldCommand, SetStyleCommand, SheetsSelectionsService, UniverSheetsPlugin } from '@univerjs/sheets';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';

import { BLOCKED_FUNCTIONS, blockFunctions, guardFormatting, guardStructure } from '../src/guard.js';
import { editsFromMutation } from '../src/convert.js';

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

// XF-1: formatting is not saved, so the page does not apply it; values and formulas still go to the service.
test('formatting is not applied; values, existing styles and page marks are kept', async () => {
  const univer = start();
  const injector = univer.__getInjector();
  const cs = injector.get(ICommandService);
  let applying = 0;
  const refused = [];
  guardFormatting(cs, CanceledError, () => applying > 0, (id) => refused.push(id));
  const data = book('w');
  data.styles = { k: { bl: 1 } };
  data.sheets.s0.cellData[1] = { 0: { v: 3, s: 'k' } };
  univer.createUnit(UniverInstanceType.UNIVER_SHEET, data);
  await tick();
  // The page's preset registers these through the UI plugin; the headless model registers only some of them.
  for (const c of [SetBoldCommand, SetStyleCommand]) { if (!cs.hasCommand(c.id)) cs.registerCommand(c); }
  const edits = [];
  cs.onCommandExecuted((cmd, o) => {
    if (cmd.id === 'sheet.mutation.set-range-values' && !(o && (o.onlyLocal || o.fromFormula)) && !applying) {
      edits.push(...editsFromMutation(cmd.params, { s0: 'Sales' }));
    }
  });
  const ws = injector.get(IUniverInstanceService).getUnit('w').getSheetBySheetId('s0');
  const primary = { actualRow: 0, actualColumn: 0, startRow: 0, startColumn: 0, endRow: 0, endColumn: 0,
    isMerged: false, isMergedMainCell: false };
  injector.get(SheetsSelectionsService).setSelections([{ range: { startRow: 0, endRow: 0, startColumn: 0,
    endColumn: 0 }, primary, style: null }]);
  // toolbar bold and fill: nothing is applied, nothing is sent
  await cs.executeCommand(SetBoldCommand.id);
  await cs.executeCommand(SetStyleCommand.id, { style: { type: 'bg', value: { rgb: '#FF0000' } } });
  assert.equal(ws.getCellRaw(0, 0).s, undefined);
  // a paste of a value with formatting: the value is applied and sent, the formatting is not
  await cs.executeCommand('sheet.command.set-range-values', { unitId: 'w', subUnitId: 's0',
    range: { startRow: 2, endRow: 2, startColumn: 0, endColumn: 0 }, value: { v: 7, s: { bl: 1 } } });
  assert.equal(ws.getCellRaw(2, 0).v, 7);
  assert.equal(ws.getCellRaw(2, 0).s, undefined);
  // typing into a formatted cell keeps its existing style
  await cs.executeCommand('sheet.command.set-range-values', { unitId: 'w', subUnitId: 's0',
    range: { startRow: 1, endRow: 1, startColumn: 0, endColumn: 0 }, value: { v: 9 } });
  assert.equal(ws.getCellRaw(1, 0).v, 9);
  assert.equal(ws.getCellRaw(1, 0).s, 'k');
  // merging is refused before it can clear cells
  const merged = await cs.executeCommand('sheet.command.add-worksheet-merge', { unitId: 'w', subUnitId: 's0',
    selections: [{ startRow: 0, endRow: 1, startColumn: 0, endColumn: 1 }] });
  assert.equal(merged, false);
  assert.equal(ws.getMergeData().length, 0);
  assert.equal(ws.getCellRaw(1, 0).v, 9);
  // the page's own change marks (applying > 0) still set backgrounds
  applying++;
  await cs.executeCommand(SetStyleCommand.id, { style: { type: 'bg', value: { rgb: '#FFF2B3' } } });
  applying--;
  assert.ok(ws.getCellRaw(0, 0).s, 'mark applied');
  assert.deepEqual(edits, [{ sheet: 'Sales', cell: 'A3', value: 7 }, { sheet: 'Sales', cell: 'A2', value: 9 }]);
  assert.ok(refused.includes('sheet.mutation.set-range-values'));
  assert.ok(refused.includes('sheet.command.add-worksheet-merge'));
  univer.dispose();
});
