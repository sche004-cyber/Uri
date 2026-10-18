// What the page refuses to do, kept free of Univer imports so it can be unit tested in node (test/guard.test.mjs) and
// checked against the real engine (test/guard.univer.test.mjs).

// Formula functions that can reach the network or other programs (AC15). WEBSERVICE is listed by Univer 1.0.3 but
// not implemented; it is blocked too in case a later version adds it.
export const BLOCKED_FUNCTIONS = Object.freeze(['IMAGE', 'HYPERLINK', 'WEBSERVICE', 'FILTERXML', 'ENCODEURL']);

// Block `names` in Univer's IFunctionService for the life of the page. Univer registers its formula functions when the
// formula engine becomes ready, which happens on the first workbook load, so removing them once at start-up is not
// enough: registration itself is filtered, and anything already registered is removed now. Returns
// {remove(), present()}: `present()` lists blocked names the service still has (must always be empty).
export function blockFunctions(service, names = BLOCKED_FUNCTIONS) {
  const blocked = new Set(names.map((n) => String(n).toUpperCase()));
  const isBlocked = (n) => typeof n === 'string' && blocked.has(n.toUpperCase());
  const registerExecutors = service.registerExecutors.bind(service);
  const registerDescriptions = service.registerDescriptions.bind(service);
  service.registerExecutors = (...fns) => registerExecutors(...fns.filter((f) => !isBlocked(f && f.name)));
  service.registerDescriptions = (...ds) => registerDescriptions(...ds.filter((d) => !isBlocked(d && d.functionName)));
  const remove = () => {
    service.unregisterExecutors(...blocked);
    service.unregisterDescriptions(...blocked);
  };
  const present = () => [...blocked].filter((n) => service.hasExecutor(n) ||
    (typeof service.hasDescription === 'function' && service.hasDescription(n)));
  remove();
  return { remove, present };
}

// Grid-structure changes (insert/delete/move rows, columns or ranges, sort, add/copy/remove/rename/reorder sheets) are
// out of scope for M1. The service keys every change by sheet name and A1 ref as opened, and the page reports only
// cell values, so a local structural change would make later edits land on the wrong cells (or on unknown sheets).
// Both the user-facing commands and the mutations they produce are refused.
export const STRUCTURAL_COMMANDS = Object.freeze(new Set([
  'sheet.command.append-row',
  'sheet.command.copy-sheet',
  'sheet.command.delete-range-move-left', 'sheet.command.delete-range-move-left-confirm',
  'sheet.command.delete-range-move-up', 'sheet.command.delete-range-move-up-confirm',
  'sheet.command.insert-col', 'sheet.command.insert-col-after', 'sheet.command.insert-col-before',
  'sheet.command.insert-col-by-range', 'sheet.command.insert-multi-cols-before', 'sheet.command.insert-multi-cols-right',
  'sheet.command.insert-multi-rows-above', 'sheet.command.insert-multi-rows-after',
  'sheet.command.insert-range-move-down', 'sheet.command.insert-range-move-down-confirm',
  'sheet.command.insert-range-move-right', 'sheet.command.insert-range-move-right-confirm',
  'sheet.command.insert-row', 'sheet.command.insert-row-after', 'sheet.command.insert-row-before',
  'sheet.command.insert-row-by-range',
  'sheet.command.insert-sheet',
  'sheet.command.move-cols', 'sheet.command.move-range', 'sheet.command.move-range-confirm', 'sheet.command.move-rows',
  'sheet.command.remove-col', 'sheet.command.remove-col-by-range', 'sheet.command.remove-col-confirm',
  'sheet.command.remove-row', 'sheet.command.remove-row-by-range', 'sheet.command.remove-row-confirm',
  'sheet.command.remove-sheet', 'sheet.command.remove-sheet-confirm',
  'sheet.command.reorder-range',
  'sheet.command.set-worksheet-name', 'sheet.command.set-worksheet-order',
  'sheet.command.table-remove-col', 'sheet.command.table-remove-column-at',
  'sheet.mutation.copy-worksheet-end',
  'sheet.mutation.insert-col', 'sheet.mutation.insert-row', 'sheet.mutation.insert-sheet',
  'sheet.mutation.move-columns', 'sheet.mutation.move-range', 'sheet.mutation.move-rows',
  'sheet.mutation.remove-col', 'sheet.mutation.remove-rows', 'sheet.mutation.remove-sheet',
  'sheet.mutation.reorder-range',
  'sheet.mutation.set-worksheet-name', 'sheet.mutation.set-worksheet-order',
]));

export const isStructural = (id) => STRUCTURAL_COMMANDS.has(id);

// Refuse structural commands before they run. `commandService` is Univer's ICommandService; `CancelError` is Univer's
// CanceledError (a CustomCommandExecutionError, so the command service turns it into a quiet `false` result).
// `onRefused(id)` lets the page tell the host.
export function guardStructure(commandService, CancelError, onRefused = () => {}) {
  return commandService.beforeCommandExecuted((info) => {
    if (info && isStructural(info.id)) {
      onRefused(info.id);
      throw new CancelError();
    }
  });
}

// XF-1 (Office capability audit, 2026-10-15): formatting is not saved. The page reports cell values and formulas only,
// and the service writes only those, so bold, colours, number formats, borders or merges applied in the page were shown
// and then silently lost on save. Until formatting is saved, the page does not apply it: what is shown is what is saved.
// Merges are refused as commands (a merge also clears the non-anchor cells, which would be sent as clears) and as
// mutations; worksheet-wide styles are refused as mutations.
export const FORMAT_COMMANDS = Object.freeze(new Set([
  'sheet.command.add-worksheet-merge', 'sheet.command.add-worksheet-merge-all',
  'sheet.command.add-worksheet-merge-horizontal', 'sheet.command.add-worksheet-merge-vertical',
  'sheet.command.remove-worksheet-merge',
  'sheet.mutation.add-worksheet-merge', 'sheet.mutation.remove-worksheet-merge',
  'sheet.mutation.set-worksheet-default-style', 'sheet.mutation.set-worksheet-range-theme-style',
  // Codex review R1-1: column widths and row heights are not saved either. The owner's resize commands are refused
  // (dragging a header edge, the width/height dialogs, auto-fit). The row auto-height mutation Univer runs itself while
  // text is typed is not touched.
  'sheet.command.delta-column-width', 'sheet.command.delta-row-height', 'sheet.command.set-worksheet-col-width',
  'sheet.command.set-row-height', 'sheet.command.set-col-auto-width', 'sheet.command.set-col-is-auto-width',
  'sheet.command.set-row-is-auto-height',
  // Codex review R2-1: also the paste of column widths and the width/height mutations themselves, whatever command
  // runs them. Univer's own auto-height on typing uses a different mutation (set-worksheet-row-auto-height).
  'sheet.command.paste-col-width',
  'sheet.mutation.set-worksheet-col-width', 'sheet.mutation.set-worksheet-row-height',
]));

// Remove the style (`s`) of every cell in a set-range-values mutation's params; values, formulas and rich text stay.
// Returns how many cells had a style. A cell keeps the style it already has (a value write without `s` does not touch
// it), so typing into a formatted cell keeps its look.
export function stripCellStyles(params) {
  let n = 0;
  const cv = params && params.cellValue;
  if (!cv || typeof cv !== 'object') return 0;
  for (const cols of Object.values(cv)) {
    for (const cell of Object.values(cols || {})) {
      if (cell && typeof cell === 'object' && 's' in cell) { delete cell.s; n++; }
    }
  }
  return n;
}

// OD-R3 (2026-10-16): for local workbooks URI now saves this subset of formatting (uri_office/xlsx_styles.py):
// bold, italic, underline, text colour, fill, number format, horizontal alignment and wrap. Any other style property
// (font size or family, borders, strikethrough, vertical alignment, rotation...) is still removed before it is
// applied, so what is shown stays what is saved.
export const SAVED_STYLE_KEYS = Object.freeze(['bl', 'it', 'ul', 'cl', 'bg', 'n', 'ht', 'tb']);

// Keep only the saved keys of every user cell style in a set-range-values mutation's params. A style given as a
// reference (string) or a clear (null) cannot be split and is removed. Returns how many cells lost something.
export function keepSavedStyles(params) {
  let n = 0;
  const cv = params && params.cellValue;
  if (!cv || typeof cv !== 'object') return 0;
  for (const cols of Object.values(cv)) {
    for (const cell of Object.values(cols || {})) {
      if (!cell || typeof cell !== 'object' || !('s' in cell)) continue;
      const s = cell.s;
      if (!s || typeof s !== 'object') { delete cell.s; n++; continue; }
      let lost = false;
      for (const k of Object.keys(s)) if (!SAVED_STYLE_KEYS.includes(k)) { delete s[k]; lost = true; }
      if (s.ul && typeof s.ul === 'object') for (const k of Object.keys(s.ul)) if (k !== 's') { delete s.ul[k]; lost = true; }
      if (!Object.keys(s).length) delete cell.s;
      if (lost) n++;
    }
  }
  return n;
}

function hex(c) {
  if (!c) return null;
  const v = String(c.rgb || '').trim();
  let m = /^#?([0-9a-f]{6})$/i.exec(v);
  if (m) return '#' + m[1].toUpperCase();
  m = /^#?([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(v);
  if (m) return ('#' + m[1] + m[1] + m[2] + m[2] + m[3] + m[3]).toUpperCase();
  m = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(v);
  if (m) return '#' + [m[1], m[2], m[3]].map((x) => Number(x).toString(16).padStart(2, '0')).join('').toUpperCase();
  return null;
}

// Univer IStyleData -> URI's style dict (the inverse of convert.js toUniverStyle). `markRestore`: the background the
// cell had before URI marked it (a change mark is never saved as a fill).
export function fromUniverStyle(st, markRestore) {
  const out = {};
  if (!st) return out;
  if (st.bl === 1) out.b = true;
  if (st.it === 1) out.i = true;
  if (st.ul && st.ul.s === 1) out.u = true;
  const fc = hex(st.cl);
  if (fc && fc !== '#000000') out.fc = fc;
  const bg = markRestore !== undefined ? hex(markRestore ? { rgb: markRestore } : null) : hex(st.bg);
  if (bg) out.bg = bg;
  if (st.n && st.n.pattern && st.n.pattern !== 'General') out.nf = st.n.pattern;
  const ha = { 1: 'left', 2: 'center', 3: 'right' }[st.ht];
  if (ha) out.ha = ha;
  if (st.tb === 3) out.wrap = true;
  return out;
}

// `isApplying()` is true while the page itself changes cells (loads and change marks), which may set backgrounds.
// `onRefused(id)` lets the page tell the host once per refused or stripped action. `allowSavedStyles()` is true for a
// local workbook: then the saved subset is applied and reported, and only the rest is removed.
export function guardFormatting(commandService, CancelError, isApplying = () => false, onRefused = () => {},
  allowSavedStyles = () => false) {
  return commandService.beforeCommandExecuted((info, options) => {
    if (!info || isApplying()) return;
    if (FORMAT_COMMANDS.has(info.id)) {
      onRefused(info.id);
      throw new CancelError();
    }
    if (info.id === 'sheet.mutation.set-range-values') {
      const o = options || {};
      if (o.onlyLocal || o.fromFormula) return;
      if (allowSavedStyles() ? keepSavedStyles(info.params) : stripCellStyles(info.params)) onRefused(info.id);
    }
  });
}
