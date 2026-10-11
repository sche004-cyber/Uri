// URI Office sheet page inside the shared WebView2 host (AC1, AC2, AC15).
//
// The page is display and input only. It never talks to the network or to the Office service: every message goes to
// the Flutter host through window.chrome.webview, and the host relays to the service (which is the authority).
//
// Host -> page: {type: "load", workbook, marks}           show the workbook as opened plus the draft's live changes
//               (marks: [{sheet, cell, state: proposed|accepted|user, after}])
//               {type: "marks", marks}                     refresh marks after a decision
// Page -> host: {type: "ready"} | {type: "edit", sheet, cell, value|formula} | {type: "error", code}
//               (code FORMULA_NOT_RESOLVED: a shared-formula cell whose formula could not be read; nothing is sent)
//               (code RICH_TEXT_NOT_READ: rich text with no plain-text form, e.g. an embedded object; nothing is sent)
//               (code STRUCTURE_CHANGE_NOT_SUPPORTED: a structural grid change was refused in the page, see guard.js)
import './no-network.js';        // must stay the first import: runs before any Univer code (AC15)
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';
import { CanceledError, ICommandService } from '@univerjs/core';
import { FormulaDataModel, IFunctionService } from '@univerjs/engine-formula';
import '@univerjs/preset-sheets-core/lib/index.css';
import { editsFromMutation, parseCell, toUniver } from './convert.js';
import { blockFunctions, guardStructure } from './guard.js';

// user: owner's own edits are applied without a mark.
const MARK_BG = { proposed: '#FFF2B3', accepted: '#D9F2D9', user: null };

const host = window.chrome && window.chrome.webview;
const send = (msg) => host && host.postMessage(msg);

const { univer, univerAPI } = createUniver({
  locale: LocaleType.EN_US,
  locales: { [LocaleType.EN_US]: mergeLocales(sheetsCoreEnUS) },
  presets: [UniverSheetsCorePreset({ container: 'app', header: true, footer: true })],
});

// Network-capable formula functions are filtered out of registration (Univer registers its functions when the first
// workbook loads) and re-checked after every load; a workbook is never shown while one of them is present (AC15).
const injector = univer.__getInjector();
const functionGuard = blockFunctions(injector.get(IFunctionService));
// Structural grid edits are refused in the page (see guard.js); the owner is told why.
guardStructure(injector.get(ICommandService), CanceledError,
  () => send({ type: 'error', code: 'STRUCTURE_CHANGE_NOT_SUPPORTED' }));
// Read-only diagnostics for the Edge/WebView2 probe: which blocked functions the engine still has (must be none).
Object.defineProperty(window, 'uriOfficeGuard', {
  value: Object.freeze({ blockedFunctionsPresent: () => functionGuard.present() }),
});

let workbook = null;
let sheetNameById = {};
let applying = 0;           // > 0 while the page itself changes cells (marks, loads): not user edits
let marked = [];            // [{sheet, cell}] currently shown with a mark

function load(wb) {
  applying++;
  try {
    if (workbook) univerAPI.disposeUnit(workbook.getId());
    const data = toUniver(wb);
    sheetNameById = Object.fromEntries(Object.values(data.sheets).map((s) => [s.id, s.name]));
    workbook = univerAPI.createWorkbook(data);
    functionGuard.remove();
    const left = functionGuard.present();
    if (left.length) {
      univerAPI.disposeUnit(workbook.getId());
      workbook = null;
      throw new Error('blocked formula functions present: ' + left.join(','));
    }
  } finally {
    applying--;
  }
}

function sheetByName(name) {
  return workbook && workbook.getSheets().find((s) => s.getSheetName() === name);
}

function setMarks(marks) {
  applying++;
  try {
    for (const m of marked) {
      const sh = sheetByName(m.sheet);
      if (sh) { const { row, col } = parseCell(m.cell); sh.getRange(row, col).setBackground(m.restore || null); }
    }
    marked = [];
    for (const m of marks || []) {
      const sh = sheetByName(m.sheet);
      if (!sh || !(m.state in MARK_BG)) continue;
      const { row, col } = parseCell(m.cell);
      const r = sh.getRange(row, col);
      if (m.after) {
        if (m.after.f) r.setFormula(m.after.f); else r.setValue(m.after.v ?? '');
      }
      if (!MARK_BG[m.state]) continue;
      const restore = r.getBackground();
      r.setBackground(MARK_BG[m.state]);
      marked.push({ sheet: m.sheet, cell: m.cell, restore });
    }
  } finally {
    applying--;
  }
}

univerAPI.addEvent(univerAPI.Event.CommandExecuted, (ev) => {
  if (applying || ev.id !== 'sheet.mutation.set-range-values') return;
  // Univer's own writes (formula results are {onlyLocal: true, fromFormula: true}) are not owner edits. Without this, a
  // recalculated formula cell would be sent to the service as an edit that replaces its formula with a value.
  const o = ev.options || {};
  if (o.onlyLocal || o.fromFormula) return;
  const p = ev.params || {};
  const formulas = injector.get(FormulaDataModel);
  const resolve = (row, col) => formulas.getFormulaStringByCell(row, col, p.subUnitId, p.unitId);
  for (const e of editsFromMutation(p, sheetNameById, resolve)) {
    if (e.error) send({ type: 'error', code: e.error, detail: `${e.sheet}!${e.cell}` });
    else send({ type: 'edit', ...e });
  }
});

if (host) {
  host.addEventListener('message', (ev) => {
    const msg = ev.data;
    try {
      if (msg && msg.type === 'load') { load(msg.workbook); setMarks(msg.marks); }
      else if (msg && msg.type === 'marks') setMarks(msg.marks);
    } catch (err) {
      send({ type: 'error', code: 'PAGE_ERROR', detail: String(err && err.message || err).slice(0, 200) });
    }
  });
}

// No navigation away from this page and no new windows, even if a cell link is clicked (the host enforces this too).
window.open = () => null;
document.addEventListener('click', (e) => {
  const a = e.target && e.target.closest && e.target.closest('a[href]');
  if (a) { e.preventDefault(); e.stopPropagation(); }
}, true);

send({ type: 'ready' });
