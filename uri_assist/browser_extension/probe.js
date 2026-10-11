// URI Assist render probe (R13-01 / D10). Injected by the adapter right after snapshot.js, by the same user click.
// It binds each text unit the snapshot sends (a range of one text node) to the pixels that unit itself draws. The
// adapter takes a screenshot of the page as it is ("base"), then for each probe group one with only that group's
// glyphs made transparent ("clear") and two with them painted in two independent random probe palettes ("tint",
// "tint2"), using a CSS Custom Highlight, and finally "base" again. URI (uri_assist/onscreen.py) keeps a unit only
// where its own glyphs take both tints and differ from what is behind them. Nothing in the DOM is changed: the
// highlights and an adopted style sheet are removed by "end", and the user's selection (which would paint over the
// highlight) is removed for the probe and put back by "end". In the extension the adapter injects the probe rules
// with chrome.scripting.insertCSS (user origin, unreadable by the page) and runs this script in its isolated world.
// Called as (probe)({op, key, ...}); state between calls lives under window[key] (the adapter's random key).
(arg) => {
  const MAX_RECTS = 8, MAX_GROUPS = 8;
  const st = window[arg.key];
  if (arg.op === "begin") {
    if (st || typeof CSS === "undefined" || !CSS.highlights || typeof Highlight !== "function") return { ok: false };
    // Text nodes are numbered as snapshot.js numbers them (document order over the whole document).
    const nodes = [], w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) nodes.push(n);
    const units = arg.units.map((x) => {                  // [n, a, b], or null for a unit not to probe
      const [n, a, b] = Array.isArray(x) ? x : [-1, 0, 0], node = nodes[n];
      if (!node || !(a >= 0 && b > a && b <= node.nodeValue.length)) return { range: null, r: [], c: 0, l: -1, s: 0 };
      // R14-02: glyphs drawn as discs or squares (-webkit-text-security) are reported; URI drops such units.
      const cs = node.parentElement ? getComputedStyle(node.parentElement) : null;
      const s = cs && (cs.webkitTextSecurity || cs.getPropertyValue("-webkit-text-security") || "none") !== "none" ? 1 : 0;
      const range = document.createRange(); range.setStart(node, a); range.setEnd(node, b);
      const all = [...range.getClientRects()].filter((q) => q.width > 0 && q.height > 0)
        .map((q) => { const x = Math.floor(q.left), y = Math.floor(q.top); return [x, y, Math.ceil(q.right) - x, Math.ceil(q.bottom) - y]; });
      return { range, r: all.slice(0, MAX_RECTS), c: all.length, l: node.nodeValue.length, s };
    });
    // Groups: units whose rects, grown by a quarter of their height, touch go to different groups (so a clear shot
    // removes no other ink inside a unit's own box). Colours: inside a group, units closer than three line heights
    // get different probe colours (so glyphs drawn outside their own box are not credited to a neighbour).
    const grow = (r, m) => [r[0] - m, r[1] - m, r[0] + r[2] + m, r[1] + r[3] + m];
    const hit = (p, q) => p[0] < q[2] && q[0] < p[2] && p[1] < q[3] && q[1] < p[3];
    const near = (u, v, f) => u.r.some((p) => v.r.some((q) => hit(grow(p, f * Math.max(p[3], q[3])), grow(q, 0))));
    const groups = [], inView = (r) => r[0] >= -2 && r[1] >= -2 && r[0] + r[2] <= innerWidth + 2 && r[1] + r[3] <= innerHeight + 2;
    units.forEach((u, i) => {
      if (!u.range || u.s || !u.r.length || u.c > MAX_RECTS || !u.r.every(inView)) return;   // URI cannot check these
      for (const g of groups) {
        if (g.units.some((j) => near(u, units[j], 0.25))) continue;
        const used = new Set(g.units.filter((j) => near(u, units[j], 3)).map((j) => g.colours[g.units.indexOf(j)]));
        const ci = arg.palette.findIndex((_, k) => !used.has(k));
        if (ci < 0) continue;
        g.units.push(i); g.colours.push(ci); return;
      }
      if (groups.length < MAX_GROUPS) groups.push({ units: [i], colours: [0] });
    });
    const sel = getSelection(), saved = [];
    for (let i = 0; i < sel.rangeCount; i++) saved.push(sel.getRangeAt(i).cloneRange());
    const sheet = new CSSStyleSheet();
    window[arg.key] = { units, groups, saved, sheet, sheets: document.adoptedStyleSheets, names: [] };
    sel.removeAllRanges();
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
    return { ok: true, units: units.map(({ r, c, l, s }) => ({ r, c, l, s })), groups,
      viewport: { w: innerWidth, h: innerHeight }, device_pixel_ratio: window.devicePixelRatio || 1 };
  }
  if (!st) return { ok: false };
  for (const n of st.names) CSS.highlights.delete(n);
  st.names = [];
  if (arg.op === "show") {                                   // {group, mode: "clear" | "tint", palette, nonce}
    const g = st.groups[arg.group], rules = [];
    const by = new Map();
    g.units.forEach((i, k) => { const c = arg.mode === "clear" ? -1 : g.colours[k];
      if (!by.has(c)) by.set(c, []); by.get(c).push(st.units[i].range); });
    for (const [c, ranges] of by) {
      const name = `${arg.key}-${arg.nonce}-${c < 0 ? 0 : c + 1}`, col = c < 0 ? "transparent" : `rgb(${arg.palette[c].join(",")})`;
      CSS.highlights.set(name, new Highlight(...ranges)); st.names.push(name);
      rules.push(`::highlight(${name}){color:${col} !important;-webkit-text-fill-color:${col} !important;` +
        "text-shadow:none !important;text-decoration:none !important;background-color:transparent !important}");
    }
    st.sheet.replaceSync(rules.join("\n"));
    return { ok: true };
  }
  if (arg.op === "base") { st.sheet.replaceSync(""); return { ok: true }; }
  // "end": restore everything.
  document.adoptedStyleSheets = st.sheets;
  const sel = getSelection(); sel.removeAllRanges();
  for (const r of st.saved) sel.addRange(r);
  delete window[arg.key];
  return { ok: true };
}
