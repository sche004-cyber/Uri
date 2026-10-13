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
