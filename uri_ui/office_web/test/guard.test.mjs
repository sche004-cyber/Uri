// Unit tests for the page's guards (no Univer needed): node --test test/guard.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { BLOCKED_FUNCTIONS, blockFunctions, guardStructure, isStructural } from '../src/guard.js';

// Same shape as Univer 1.0.3's FunctionService: executors keyed by `name`, descriptions by `functionName`.
class FakeFunctionService {
  constructor() { this.ex = new Map(); this.desc = new Map(); }
  registerExecutors(...fns) { for (const f of fns) this.ex.set(f.name, f); }
  registerDescriptions(...ds) { for (const d of ds) this.desc.set(d.functionName, d); return { dispose() {} }; }
  unregisterExecutors(...names) { for (const n of names) this.ex.delete(n); }
  unregisterDescriptions(...names) { for (const n of names) this.desc.delete(n); }
  hasExecutor(n) { return this.ex.has(n); }
  hasDescription(n) { return this.desc.has(n); }
}
const ALL = ['SUM', 'IMAGE', 'HYPERLINK', 'FILTERXML', 'ENCODEURL', 'WEBSERVICE', 'IF'];

test('blocked functions registered later (on the first workbook load) never reach the engine', () => {
  const svc = new FakeFunctionService();
  const guard = blockFunctions(svc);
  // What Univer's formula engine does in its onReady, i.e. after the page's start-up code ran.
  svc.registerExecutors(...ALL.map((name) => ({ name })));
  svc.registerDescriptions(...ALL.map((functionName) => ({ functionName })));
  for (const n of BLOCKED_FUNCTIONS) assert.equal(svc.hasExecutor(n) || svc.hasDescription(n), false, n);
  assert.deepEqual(guard.present(), []);
  assert.ok(svc.hasExecutor('SUM') && svc.hasExecutor('IF') && svc.hasDescription('SUM'));
});

test('functions registered before the guard are removed, and present() reports any that slip in', () => {
  const svc = new FakeFunctionService();
  svc.registerExecutors(...ALL.map((name) => ({ name })));
  const guard = blockFunctions(svc);
  assert.deepEqual(guard.present(), []);
  svc.ex.set('IMAGE', { name: 'IMAGE' });            // bypassing registration: present() must see it
  assert.deepEqual(guard.present(), ['IMAGE']);
  guard.remove();
  assert.deepEqual(guard.present(), []);
});

test('structural commands and mutations are refused, cell edits and formatting are not', () => {
  for (const id of ['sheet.command.insert-row-before', 'sheet.command.remove-col', 'sheet.command.move-rows',
    'sheet.command.insert-sheet', 'sheet.command.set-worksheet-name', 'sheet.command.remove-sheet-confirm',
    'sheet.command.reorder-range', 'sheet.mutation.insert-row', 'sheet.mutation.remove-rows',
    'sheet.mutation.move-range', 'sheet.mutation.insert-sheet', 'sheet.mutation.set-worksheet-order']) {
    assert.equal(isStructural(id), true, id);
  }
  for (const id of ['sheet.mutation.set-range-values', 'sheet.command.set-range-values', 'sheet.command.set-bold',
    'sheet.command.set-worksheet-activate', 'sheet.command.paste', 'univer.command.undo']) {
    assert.equal(isStructural(id), false, id);
  }
});

test('guardStructure cancels a structural command before it runs and reports it', () => {
  const listeners = [];
  const cs = { beforeCommandExecuted(l) { listeners.push(l); return { dispose() {} }; } };
  class Cancel extends Error {}
  const refused = [];
  guardStructure(cs, Cancel, (id) => refused.push(id));
  assert.throws(() => listeners[0]({ id: 'sheet.command.insert-row-after', type: 0 }), Cancel);
  assert.doesNotThrow(() => listeners[0]({ id: 'sheet.mutation.set-range-values', type: 2 }));
  assert.deepEqual(refused, ['sheet.command.insert-row-after']);
});

test('the page wires both guards and re-checks the functions after every workbook load', () => {
  const src = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
  assert.match(src, /blockFunctions\(injector\.get\(IFunctionService\)\)/);
  assert.match(src, /guardStructure\(injector\.get\(ICommandService\), CanceledError/);
  const load = src.slice(src.indexOf('function load('), src.indexOf('function sheetByName('));
  assert.ok(load.indexOf('functionGuard.present()') > load.indexOf('createWorkbook('), 'check runs after createWorkbook');
});
