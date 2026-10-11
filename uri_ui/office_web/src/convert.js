// Workbook JSON from the URI Office service (uri_office/xlsx_model.py) -> Univer IWorkbookData. Pure; tested in Node.

export function colIndex(letters) {
  let n = 0;
  for (const ch of letters) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n;
}

export function parseCell(ref) {
  const m = /^([A-Z]{1,3})([1-9][0-9]{0,6})$/.exec(ref);
  if (!m) throw new Error(`bad cell ref ${ref}`);
  return { row: Number(m[2]) - 1, col: colIndex(m[1]) - 1 };
}

export function cellRef(row, col) {
  let n = col + 1, s = '';
  while (n) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); }
  return `${s}${row + 1}`;
}

const HALIGN = { left: 1, center: 2, right: 3 };

export function toUniverStyle(s) {
  const out = {};
  if (s.b) out.bl = 1;
  if (s.i) out.it = 1;
  if (s.u) out.ul = { s: 1 };
  if (s.fc) out.cl = { rgb: s.fc };
  if (s.bg) out.bg = { rgb: s.bg };
  if (s.nf) out.n = { pattern: s.nf };
  if (s.ha && HALIGN[s.ha]) out.ht = HALIGN[s.ha];
  if (s.wrap) out.tb = 3;
  return out;
}

export function toUniverCell(c) {
  const out = {};
  if (c.f) out.f = c.f;
  if (c.v !== undefined && c.v !== null) out.v = typeof c.v === 'boolean' ? (c.v ? 1 : 0) : c.v;
  if (c.s) out.s = c.s;
  return out;
}

export function toUniver(wb, id = 'uri-office') {
  const styles = {};
  for (const [k, s] of Object.entries(wb.styles || {})) styles[k] = toUniverStyle(s);
  const sheets = {};
  const order = [];
  wb.sheets.forEach((sh, i) => {
    const sid = `s${i}`;
    order.push(sid);
    const cellData = {};
    for (const [ref, c] of Object.entries(sh.cells)) {
      const { row, col } = parseCell(ref);
      (cellData[row] ||= {})[col] = toUniverCell(c);
    }
    const mergeData = (sh.merges || []).map((m) => {
      const [a, b] = m.split(':');
      const p = parseCell(a), q = parseCell(b || a);
      return { startRow: p.row, startColumn: p.col, endRow: q.row, endColumn: q.col };
    });
    const columnData = {};
    for (const [letters, w] of Object.entries(sh.col_widths || {})) columnData[colIndex(letters) - 1] = { w: Math.round(w * 7 + 5) };
    const rowData = {};
    for (const [r, h] of Object.entries(sh.row_heights || {})) rowData[Number(r) - 1] = { h: Math.round((h * 4) / 3) };
    sheets[sid] = {
      id: sid, name: sh.name, cellData, mergeData, columnData, rowData,
      rowCount: Math.max((sh.max_row || 0) + 50, 100), columnCount: Math.max((sh.max_col || 0) + 10, 26),
    };
  });
  return { id, name: 'URI Office', sheetOrder: order, styles, sheets };
}

// One user edit from a Univer set-range-values mutation -> service edit requests.
export function editsFromMutation(params, sheetNameById) {
  const sheet = sheetNameById[params.subUnitId];
  if (!sheet || !params.cellValue) return [];
  const out = [];
  for (const [r, cols] of Object.entries(params.cellValue)) {
    for (const [c, cell] of Object.entries(cols || {})) {
      const ref = cellRef(Number(r), Number(c));
      if (cell == null) { out.push({ sheet, cell: ref, value: null }); continue; }
      if (typeof cell.f === 'string' && cell.f.startsWith('=')) out.push({ sheet, cell: ref, formula: cell.f });
      else if ('v' in cell || 'p' in cell) out.push({ sheet, cell: ref, value: cell.v ?? null });
    }
  }
  return out;
}
