// URI Assist page snapshot (schema uri.assist.dom.v1). Injected only by an explicit user click (activeTab).
// Read-only: it never changes the page, never submits, never reads cookies or storage.
// Private values are removed HERE, inside the page, before the snapshot exists; URI redacts again on receipt.
(() => {
  const MAX_TEXT = 40000, MAX_FIELDS = 200, MAX_HEADINGS = 60, MAX_VALUE = 2000;
  const SENSITIVE_TYPES = new Set(["password", "hidden"]);
  const SENSITIVE_AC = new Set(["current-password", "new-password", "one-time-code", "cc-number", "cc-csc", "cc-exp",
    "cc-exp-month", "cc-exp-year", "cc-name", "cc-type"]);
  // Same rules as uri_assist/redact.py (kept in sync; tests/assist checks both on one fixture).
  const SENSITIVE_WORDS = /\b(pass|pw|pwd|[a-z]*otp|mfa|2 ?fa|pin(?! ?code)|mpin|tpin|cvv|cvc|ccv|csc|cvn|cvd|csv|cid|cav ?2|ssn|pan|iban|secret|token|cookie|session|auth|password|passwd|passcode|passphrase|apikey|aadhar|aadhaar|tan|mtan|smstan|otc|2 ?sv)\b|\bapi ?key\b|\btwo ?step\b|\bone ?time\b|\btwo ?factor\b|\bverification ?code\b|\bsecurity ?(code|answer)\b|\bauth ?code\b|\bcard ?(number|num|no|expiry|exp|expiration)\b|\bacct ?(number|num|no)\b|\bcc ?(num|number|no)\b|\baccount ?(number|num|no)\b|\bsocial ?security\b|\bpan ?(number|no)\b|\bprivate ?key\b/;
  // Run-together lowercase names (see _RUN_TOGETHER in redact.py; same pattern).
  const RUN_TOGETHER = /password|passwd|passcode|passphrase|pwd|cvv|cvc|ccv|\b(mpin|tpin)|(mpin|tpin)\b|\botp|otp\b|otp(code|value|val|number|num|no|input|field|digit|box|text|entry|pin|token)|(upi|atm|card|security|secure|login|user|txn|transaction|account|acct|debit|credit|bank|access|mobile|wallet|new|old|confirm|current|verify|secret)pin(number|num|no)?\b|\bpin(number|num|no|entry|input|field|value)\b|(user|login|admin|account|acct|new|old|confirm|current|root|wifi|txn|master|secret|db)pass\b|(verify|verif|sms|email|access|activation|confirmation|confirm|login|signin)code\b/;
  // Secret stems inside each word (after readable words are cut out), secret phrases on the joined name, and short
  // single-token codes in fields whose name ends in code / pin / key (see _STEMS, _READABLE, _PHRASES, _CODE_END and
  // _CODE_EXCLUDE in redact.py; same patterns).
  const STEMS = /otp(?![ahlo])|mfa|2fa|\btfa|onetime|twofactor|twostep|verification|authenticat|authoriz|cvv|cvc|ccv|cvd|cav2|token|secret(?!ar)|password|passwd|passcode|passphrase|pwd|key|credential|recovery|mnemonic|seedphrase|aadhaa?r|\bssn|ssn\b|passport|iban|jwt|csrf|xsrf|bearer|cookie|session|pat\b|psk\b|maiden/;
  const READABLE = /keyboard|keyword|keynote|keystone|keyframe|monkey|donkey|turkey|hockey|jockey|whiskey|possession|obsession|expat/g;
  const PHRASES = /backupcode|resetcode|unlockcode|recoverycode|seedphrase|secretphrase|socialsecurity|cardnumber|cardnum|ccnumber|ccnum|accountnumber|accountnum|acctnumber|acctnum|sessionid|privatekey|apikey|securitycode|securityanswer|authcode|nationalid|taxid|routingnumber|bankaccount|sessid|nonce/;
  const CODE_END = /(code|pin|key)(number|num|no)?$/, CODE_EXCLUDE = /postal|zip|postcode|pincode|country|area|promo|coupon|voucher|referral|barcode|sortcode|ifsc|swift|currency|language|locale/;
  const tokens = (v) => String(v).replace(/(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])/g, " ").replace(/[^A-Za-z0-9]+/g, " ").toLowerCase();
  const joined = (v) => String(v).toLowerCase().replace(/[^a-z0-9]+/g, "");
  const shortCodeLabel = (v) => !POSTAL.test(v) && !CODE_EXCLUDE.test(joined(v)) &&
    (CODE_LABEL.test(words(v)) || CODE_END.test(joined(v).replace(READABLE, "")));
  const secretName = (v) => SENSITIVE_WORDS.test(words(v)) || RUN_TOGETHER.test(words(v)) ||
    tokens(v).split(" ").some((t) => STEMS.test(t.replace(READABLE, ""))) || PHRASES.test(joined(v));
  const words = (v) => String(v).replace(/(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])/g, " ").replace(/[_\-.:/]+/g, " ").toLowerCase();
  const SHORT_CODE = /^\s*(?=(?:\s?[A-Za-z0-9_-]){3,32}\s*$)[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+){0,3}\s*$/, CODE_LABEL = /\bcode\b/, POSTAL = /postal|zip|post ?code|pin ?code/i;
  const counts = {};
  const bump = (k) => { counts[k] = (counts[k] || 0) + 1; };
  const luhn = (d) => { let t = 0, alt = false; for (let i = d.length - 1; i >= 0; i--) { let n = +d[i];
    if (alt) { n *= 2; if (n > 9) n -= 9; } t += n; alt = !alt; } return t % 10 === 0; };
  const TEXT_RULES = [
    ["jwt", /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g],
    ["bearer", /\bbearer\s+[A-Za-z0-9._~+/=-]{16,}/gi],
    ["basic_auth", /\bbasic\s+(?=[A-Za-z0-9+/]*[0-9+/=])[A-Za-z0-9+/]{12,}={0,2}/gi],
    ["api_key", /\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b|\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}|\bglpat-[A-Za-z0-9_-]{20,}|\bnpm_[A-Za-z0-9]{36}\b|\bhf_[A-Za-z0-9]{30,}\b|\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bxox[abpr]-[A-Za-z0-9-]{10,}\b|\btvly-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{30,}\b/g],
    ["long_secret", /\b(?=[A-Fa-f0-9]*[A-Fa-f])(?=[A-Fa-f0-9]*\d)[A-Fa-f0-9]{32,}\b|\b(?=[A-Za-z0-9+/]*\d)(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])[A-Za-z0-9+/]{40,}={0,2}/g],
    ["aadhaar", /(?<!\d)(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)/g],
  ];
  const QUERY_SECRET = /\b((?:access_?token|token|api_?key|key|secret|password|pwd|sig|signature|code)=)[^&\s"'<>]{6,}/gi;
  const maskText = (s) => {
    if (!s) return s;
    let out = s.replace(/\b(?:\d[ .\u00a0\u2007\u202f-]?){12,18}\d\b/g, (m) => {
      const d = m.replace(/\D/g, "");
      if (d.length >= 13 && d.length <= 19 && luhn(d)) { bump("card"); return "[redacted]"; }
      return m;
    });
    for (const [k, rx] of TEXT_RULES) out = out.replace(rx, () => { bump(k); return "[redacted]"; });
    out = out.replace(QUERY_SECRET, (m, k) => { bump("query_secret"); return k + "[redacted]"; });
    return out;
  };
  const dpr = window.devicePixelRatio || 1;

  const visible = (el) => {
    if (!el || !(el instanceof Element)) return true;
    if (el.closest("[hidden],[aria-hidden='true'],template,script,style,noscript")) return false;
    if (typeof el.checkVisibility === "function" &&
        !el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(el);
    if (parseFloat(cs.fontSize) < 2) return false;
    if (cs.clipPath && cs.clipPath !== "none" && /inset\(\s*(50%|100%)/.test(cs.clipPath)) return false;
    if (r.right < 0 || r.bottom < 0 || r.left > Math.max(document.documentElement.scrollWidth, innerWidth) + 1) return false;
    return true;
  };
  // R11-01: visibility is decided per text node. Its own client rects must survive every clip that applies to it
  // (ancestor overflow boxes on its containing-block chain, the legacy clip property, clip-path inset), stay inside
  // the document (text-indent / negative offsets) and, where the rect is in the viewport, not sit under an opaque
  // element painted above it (elementFromPoint at the rect centre). Paint effects are below (R12-01).
  // These rules are a cheap first filter only. Since owner decision D10 the boundary is the pixel check in URI
  // (uri_assist/onscreen.py, see the pieces below); its residual limits are documented in docs/assist/03.
  // R12-01: subtree-wide paint effects are decided in the same ancestor walk, and anything that cannot be evaluated
  // counts as hidden (fail closed): effective opacity = product of opacity and filter:opacity() over every ancestor
  // (below MIN_ALPHA is hidden; an SVG url() filter is hidden); the text fill colour (-webkit-text-fill-color, which
  // is the colour actually painted) times that opacity below MIN_ALPHA; mask layers unless one is a gradient with an
  // inked stop that tiles over the box (url()/image masks, luminance mode and non-add compositing are hidden);
  // clip-path shapes as geometry (every inset side, circle, ellipse, polygon area; path()/url()/unparseable hidden);
  // content of a closed <details> other than its summary.
  const MIN_ALPHA = 0.1;
  const alpha = (c) => { c = String(c || "").trim(); if (c === "transparent") return 0;
    let m = /^rgba?\(([^)]*)\)$/.exec(c);
    if (m) { const v = m[1].split(/[\s,/]+/).filter(Boolean); return v.length > 3 ? num(v[3]) : 1; }
    m = /\/\s*([-\d.e]+%?)\s*\)$/.exec(c);                  // color(), oklch(), hsl() ... with an explicit alpha
    return m ? num(m[1]) : 1; };
  const num = (s) => (String(s).endsWith("%") ? parseFloat(s) / 100 : parseFloat(s));
  // Split at top level (outside parentheses) on whitespace or on commas.
  const topSplit = (s, comma) => { const out = []; let d = 0, cur = "";
    for (const ch of String(s)) {
      if (ch === "(") d++; else if (ch === ")") d--;
      if (d === 0 && (comma ? ch === "," : /\s/.test(ch))) { if (cur.trim()) out.push(cur.trim()); cur = ""; } else cur += ch;
    }
    if (cur.trim()) out.push(cur.trim()); return out; };
  const KEYPOS = { left: 0, top: 0, center: 50, right: 100, bottom: 100 };
  const len = (t, ref) => { t = String(t || "").trim(); let m = /^(-?[\d.]+(?:e-?\d+)?)(px|%)?$/.exec(t);
    if (m) return m[2] === "%" ? parseFloat(m[1]) * ref / 100 : parseFloat(m[1]);
    m = /^calc\((-?[\d.]+)%\s*([+-])\s*(-?[\d.]+)px\)$/.exec(t);
    if (m) return parseFloat(m[1]) * ref / 100 + (m[2] === "-" ? -1 : 1) * parseFloat(m[3]);
    return t in KEYPOS ? KEYPOS[t] * ref / 100 : NaN; };
  const filterOpacity = (f) => { if (!f || f === "none") return 1; if (/url\(/.test(f)) return 0;
    let o = 1; for (const m of f.matchAll(/opacity\(\s*([-\d.e]+%?)\s*\)/g)) o *= num(m[1]); return o; };
  const masked = (cs) => {
    const img = cs.maskImage || cs.webkitMaskImage || "none";
    if (img === "none") return false;
    if (/luminance/.test(cs.maskMode || "") || topSplit(cs.maskComposite || "add", true).some((c) => c !== "add")) return true;
    const at = (v, d, i) => { const l = topSplit(v || d, true); return l[i % l.length] || d; };
    return !topSplit(img, true).some((layer, i) => {
      if (!/^(repeating-)?(linear|radial|conic)-gradient\(/.test(layer)) return false;   // url()/image: cannot tell
      const stops = layer.match(/(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^)]*\)|\btransparent\b/g) || [];
      if (!stops.some((c) => alpha(c) >= MIN_ALPHA)) return false;
      const size = at(cs.maskSize || cs.webkitMaskSize, "auto", i);
      if (topSplit(size).some((s) => parseFloat(s) === 0)) return false;
      if (!/no-repeat/.test(at(cs.maskRepeat || cs.webkitMaskRepeat, "repeat", i))) return true;
      return /^(auto( auto)?|cover)$/.test(size) && /^0(px|%)? 0(px|%)?$/.test(at(cs.maskPosition || cs.webkitMaskPosition, "0% 0%", i));
    });
  };
  // The viewport box a clip-path leaves on `el` (border box `r`), or null when it leaves nothing or cannot be read.
  const clipPathBox = (cs, r) => {
    const v = cs.clipPath; let x = r.left, y = r.top, w = r.width, h = r.height;
    const g = /\b(margin|padding|content)-box\b/.exec(v);
    if (g) {
      const sides = (k) => ["Top", "Right", "Bottom", "Left"].map((s) => parseFloat(cs[k + s + (k === "border" ? "Width" : "")]) || 0);
      const parts = g[1] === "margin" ? [sides("margin")].map((a) => a.map((n) => -n)) :
        g[1] === "padding" ? [sides("border")] : [sides("border"), sides("padding")];
      for (const [t, rt, b, l] of parts) { x += l; y += t; w -= l + rt; h -= t + b; }
    }
    const open = v.indexOf("(");
    if (open < 0) return { l: x, t: y, r: x + w, b: y + h };          // reference box only
    const fn = v.slice(0, open).trim().split(/\s+/).pop();
    let d = 0, close = -1;
    for (let i = open; i < v.length; i++) { if (v[i] === "(") d++; else if (v[i] === ")" && --d === 0) { close = i; break; } }
    if (close < 0) return null;
    const args = v.slice(open + 1, close);
    const pos = (toks) => {                                            // "at X Y" (2 or 4 value form)
      if (!toks.length) return [w / 2, h / 2];
      if (toks.length === 2) return [len(toks[0], w), len(toks[1], h)];
      if (toks.length === 4) { const ax = len(toks[1], w), ay = len(toks[3], h);
        return [toks[0] === "right" ? w - ax : ax, toks[2] === "bottom" ? h - ay : ay]; }
      return [NaN, NaN];
    };
    const ok = (...n) => n.every(Number.isFinite);
    if (fn === "inset") {
      const t = topSplit(args.split(/\bround\b/)[0]);
      const [a, b = a, c = a, e = b] = t;
      const T = len(a, h), R = len(b, w), B = len(c, h), L = len(e, w);
      return t.length && ok(T, R, B, L) ? { l: x + L, t: y + T, r: x + w - R, b: y + h - B } : null;
    }
    if (fn === "circle" || fn === "ellipse") {
      const t = topSplit(args), i = t.indexOf("at"), radii = i < 0 ? t : t.slice(0, i);
      const [cx, cy] = pos(i < 0 ? [] : t.slice(i + 1));
      if (!ok(cx, cy)) return null;
      const side = (k, lo, hi) => (k === "farthest-side" ? Math.max(lo, hi) : Math.min(lo, hi));
      let rx, ry;
      if (fn === "circle") {
        const k = radii[0] || "closest-side";
        rx = ry = /side$/.test(k) ? (k === "farthest-side" ? Math.max(cx, w - cx, cy, h - cy) : Math.min(cx, w - cx, cy, h - cy))
          : len(k, Math.hypot(w, h) / Math.SQRT2);
      } else {
        const [kx = "closest-side", ky = "closest-side"] = radii;
        rx = /side$/.test(kx) ? side(kx, cx, w - cx) : len(kx, w);
        ry = /side$/.test(ky) ? side(ky, cy, h - cy) : len(ky, h);
      }
      return ok(rx, ry) ? { l: x + cx - rx, t: y + cy - ry, r: x + cx + rx, b: y + cy + ry } : null;
    }
    if (fn === "polygon") {
      const pts = topSplit(args, true).filter((s) => !/^(nonzero|evenodd)$/.test(s)).map((s) => {
        const [px, py] = topSplit(s); return [len(px, w), len(py, h)]; });
      if (pts.length < 3 || !pts.every(([px, py]) => ok(px, py))) return null;
      let area = 0;
      pts.forEach(([ax, ay], k) => { const [bx, by] = pts[(k + 1) % pts.length]; area += ax * by - bx * ay; });
      if (Math.abs(area) / 2 < 4) return null;
      const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
      return { l: x + Math.min(...xs), t: y + Math.min(...ys), r: x + Math.max(...xs), b: y + Math.max(...ys) };
    }
    return null;                                                       // path(), url(), shape(), unknown: hidden
  };
  const meet = (a, b) => ({ l: Math.max(a.l, b.l), t: Math.max(a.t, b.t), r: Math.min(a.r, b.r), b: Math.min(a.b, b.b) });
  const INF = { l: -Infinity, t: -Infinity, r: Infinity, b: Infinity };
  const clipCache = new Map(), opacityCache = new Map();
  // The box every text node directly inside `p` is clipped to (viewport coordinates), or null when nothing can show.
  // Also records the effective opacity of `p` (opacityCache).
  const clipBoxOf = (p) => {
    if (clipCache.has(p)) return clipCache.get(p);
    let box = INF, mode = "normal", op = 1, prev = null;
    for (let el = p; el; prev = el, el = el.parentElement) {
      const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      const containing = el === p || mode === "normal" ||
        (mode === "abs" && (cs.position !== "static" || cs.transform !== "none")) ||
        (mode === "fixed" && cs.transform !== "none");
      // R12-01: these apply to every descendant whatever its containing block.
      op *= (parseFloat(cs.opacity) || 0) * filterOpacity(cs.filter);
      if (op < MIN_ALPHA || masked(cs)) { box = null; break; }
      if (el.tagName === "DETAILS" && !el.open && !(prev && prev === el.querySelector(":scope > summary"))) { box = null; break; }
      if (cs.clipPath && cs.clipPath !== "none") { const c = clipPathBox(cs, r); if (!c) { box = null; break; } box = meet(box, c); }
      if (el === document.documentElement) break;
      if (cs.clip && cs.clip !== "auto" && (cs.position === "absolute" || cs.position === "fixed")) {
        const v = /rect\(([^)]*)\)/.exec(cs.clip);
        if (v) {
          const [ct, cr, cb, cl] = v[1].split(/[\s,]+/).filter(Boolean);
          const n = (x, d) => (x === "auto" ? d : parseFloat(x));
          box = meet(box, { l: r.left + n(cl, 0), t: r.top + n(ct, 0), r: r.left + n(cr, r.width), b: r.top + n(cb, r.height) });
        }
      }
      if (containing && el !== document.body && cs.display !== "inline" && cs.display !== "contents") {
        const ox = cs.overflowX !== "visible", oy = cs.overflowY !== "visible";
        if (ox || oy) {
          const l = r.left + el.clientLeft, t = r.top + el.clientTop;
          box = meet(box, { l: ox ? l : -Infinity, t: oy ? t : -Infinity,
            r: ox ? l + el.clientWidth : Infinity, b: oy ? t + el.clientHeight : Infinity });
        }
      }
      if (containing) mode = cs.position === "fixed" ? "fixed" : cs.position === "absolute" ? "abs" : "normal";
      if (box.r - box.l < 2 || box.b - box.t < 2) { box = null; break; }
    }
    if (box && (box.r - box.l < 2 || box.b - box.t < 2)) box = null;
    clipCache.set(p, box); opacityCache.set(p, op);
    return box;
  };
  const opaque = (e) => { const cs = getComputedStyle(e);
    return alpha(cs.backgroundColor) >= 1 || cs.backgroundImage !== "none" || /^(IMG|VIDEO|CANVAS|IFRAME|svg|OBJECT|EMBED)$/.test(e.tagName); };
  const covered = (p, x, y) => {
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return false;   // outside the viewport: cannot tell
    const e = document.elementFromPoint(x, y);
    if (!e || e === p || p.contains(e) || e.contains(p)) return false;
    for (let a = e; a && !a.contains(p); a = a.parentElement) if (opaque(a)) return true;
    return false;
  };
  // D10: while text is selected the browser repaints it in its own highlight colours, so a screenshot cannot tell
  // whether its own colour would have shown it. For text inside the current selection only, text painted in (almost)
  // the colour of the nearest opaque background behind its element is hidden (white on white). A background image,
  // a partly transparent background or an unreadable colour leaves the decision to the pixel check.
  const MIN_CONTRAST = 24;
  const selRanges = (() => { const s = window.getSelection ? window.getSelection() : null, out = [];
    for (let i = 0; s && i < s.rangeCount; i++) if (!s.getRangeAt(i).collapsed) out.push(s.getRangeAt(i));
    return out; })();
  const rgb = (c) => { const m = /^rgba?\(([^)]*)\)$/.exec(String(c || "").trim()); if (!m) return null;
    const v = m[1].split(/[\s,/]+/).filter(Boolean).map(num); return v.length >= 3 && v.every(Number.isFinite) ? v : null; };
  const contrastCache = new Map();
  const sameAsBackground = (p) => {
    if (contrastCache.has(p)) return contrastCache.get(p);
    let out = false; const fg = p instanceof SVGElement ? null : rgb(getComputedStyle(p).webkitTextFillColor || getComputedStyle(p).color);
    if (fg) {
      let bg = [255, 255, 255, 1], known = true;                    // the default canvas is white
      for (let el = p; el; el = el.parentElement) {
        const cs = getComputedStyle(el);
        if (cs.backgroundImage !== "none") { known = false; break; }
        const b = rgb(cs.backgroundColor);
        if (!b) { known = false; break; }
        const a = b.length > 3 ? b[3] : 1;
        if (a > 0) { if (a < 0.99) known = false; else bg = b; break; }
      }
      if (known) { const a = (fg.length > 3 ? fg[3] : 1) * (opacityCache.get(p) ?? 1);
        out = Math.max(...[0, 1, 2].map((i) => Math.abs(fg[i] * a + bg[i] * (1 - a) - bg[i]))) < MIN_CONTRAST; }
    }
    contrastCache.set(p, out); return out;
  };
  const textCache = new Map(), cache = new Map();
  const FIELD = "input,textarea,select,[contenteditable]:not([contenteditable='false'])";
  const inField = (n) => { const e = n && (n.nodeType === 1 ? n : n.parentElement); return !!(e && e.closest(FIELD)); };
  // R14-02: -webkit-text-security draws every glyph as a disc or square: the user sees dots, not the text, so it is
  // hidden (onscreen.py also drops units probe.js reports with it).
  const secured = (cs) => (cs.webkitTextSecurity || cs.getPropertyValue("-webkit-text-security") || "none") !== "none";
  const textVisible = (n) => {
    const p = n.parentElement;
    if (!p) return false;
    let ok = cache.get(p);
    if (ok === undefined) { ok = visible(p); cache.set(p, ok); }
    if (!ok) return false;
    const box = clipBoxOf(p);
    if (!box) return false;
    if (!textCache.has(p)) { const cs = getComputedStyle(p);       // R12-01: the fill colour is what is painted
      textCache.set(p, !secured(cs) && alpha(cs.webkitTextFillColor || cs.color) * opacityCache.get(p) >= MIN_ALPHA); }
    if (!textCache.get(p)) return false;
    if (selRanges.some((r) => r.intersectsNode(n)) && sameAsBackground(p)) return false;
    const range = document.createRange(); range.selectNodeContents(n);
    const docW = Math.max(document.documentElement.scrollWidth, innerWidth);
    for (const cr of range.getClientRects()) {
      const v = meet({ l: cr.left, t: cr.top, r: cr.right, b: cr.bottom }, box);
      if (v.r - v.l < 2 || v.b - v.t < 2) continue;
      if (v.r + scrollX <= 0 || v.b + scrollY <= 0 || v.l + scrollX >= docW + 1) continue;
      if (covered(p, (v.l + v.r) / 2, (v.t + v.b) / 2)) continue;
      return true;
    }
    return false;
  };
  // Owner decision D10 / R13-01 (render check): every text piece that leaves the page names the text units it was
  // built from (`u`). A unit is one range of one text node: {n: the node's number in document order over the whole
  // document, a, b: offsets, r: its viewport client rects (CSS px, [x, y, w, h], at most MAX_RECTS; `c` is how many
  // it really has), k: its non-space characters, l: the length of the whole text node (no text content leaves the
  // page this way)}. After this script the adapter runs probe.js,
  // which repaints exactly these ranges (transparent, then in probe colours) between screenshots; URI keeps a piece
  // only if every one of its units drew its own glyphs, visibly, in its own box (uri_assist/onscreen.py). The
  // visibility rules above stay as a cheap first filter; they are not the security boundary. A text node is cut into
  // segments of at most SEG characters at whitespace so a piece is roughly one line. Piece text is masked with the
  // same rules, without counting twice; when masking a segment alone differs from masking the whole (a secret across
  // a cut), the whole is sent as one piece.
  const MAX_RECTS = 8, SEG = 200, MAX_TEXT_PIECES = 4000, MAX_SEL_PIECES = 1000, MAX_HEAD_PIECES = 40, MAX_UNITS = 6000;
  const maskQuiet = (s) => { const saved = { ...counts }, out = maskText(s);
    for (const k of Object.keys(counts)) delete counts[k]; Object.assign(counts, saved); return out; };
  const squash = (s) => s.replace(/\s+/g, " ");
  let nodeIndex = null;
  const units = [], unitIds = new Map();
  const unitOf = (n, a, b) => {
    if (!nodeIndex) { nodeIndex = new Map(); const w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
      for (let x = w.nextNode(), i = 0; x; x = w.nextNode(), i++) nodeIndex.set(x, i); }
    const key = `${nodeIndex.get(n)}:${a}:${b}`;
    if (unitIds.has(key)) return unitIds.get(key);
    if (units.length >= MAX_UNITS) return -1;                        // not sent as a unit: the piece cannot be checked
    const rg = document.createRange(); rg.setStart(n, a); rg.setEnd(n, b);
    const all = [...rg.getClientRects()].filter((q) => q.width > 0 && q.height > 0)
      .map((q) => { const x = Math.floor(q.left), y = Math.floor(q.top);
        return [x, y, Math.ceil(q.right) - x, Math.ceil(q.bottom) - y]; });
    const s = n.nodeValue.slice(a, b);
    units.push({ n: nodeIndex.get(n), a, b, r: all.slice(0, MAX_RECTS), c: all.length, k: s.replace(/\s+/g, "").length, l: n.nodeValue.length });
    unitIds.set(key, units.length - 1);
    return units.length - 1;
  };
  const unitsOf = (n, a, b) => ({ u: [unitOf(n, a, b)] });
  const cuts = (s, a, b) => { const out = []; let i = a;
    while (i < b) {
      let j = Math.min(b, i + SEG);
      if (j < b) { const m = /\s+\S*$/.exec(s.slice(i, j)); if (m && m.index > 0) j = i + m.index + /^\s+/.exec(m[0])[0].length; }
      out.push([i, j]); i = j;
    }
    return out; };
  // Pieces of one text node between offsets a and b, in group g.
  const nodePieces = (n, a, b, g) => {
    const s = n.nodeValue, segs = cuts(s, a, b).map(([i, j]) => ({ g, raw: squash(s.slice(i, j)), ...unitsOf(n, i, j) }));
    if (segs.length > 1 && maskQuiet(squash(s.slice(a, b))) !== segs.map((p) => maskQuiet(p.raw)).join("")) {
      return [{ g, raw: squash(s.slice(a, b)), ...unitsOf(n, a, b) }];
    }
    return segs;
  };
  // Mask a list of pieces whose texts are joined with `sep` between groups (a secret across pieces -> one piece).
  const joinG = (xs, gs, sep) => xs.map((x, k) => (k && gs[k - 1] !== gs[k] ? sep : "") + x).join("");
  const finish = (ps, sep) => {
    const out = ps.map((p) => ({ g: p.g, t: maskQuiet(p.raw), u: p.u }));
    if (ps.length > 1) {
      const gs = ps.map((p) => p.g), plain = joinG(ps.map((p) => p.raw), gs, sep);
      if (maskQuiet(plain) !== joinG(out.map((p) => p.t), gs, sep)) {
        return [{ g: ps[0].g, t: maskQuiet(plain), u: ps.flatMap((p) => p.u) }];
      }
    }
    return out;
  };
  const rectOf = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left * dpr), y: Math.round(r.top * dpr), w: Math.round(r.width * dpr), h: Math.round(r.height * dpr) };
  };
  const labelOf = (el) => {
    const parts = [];
    if (el.id) {
      for (const l of document.querySelectorAll(`label[for="${CSS.escape(el.id)}"]`)) parts.push(l.innerText);
    }
    const wrap = el.closest("label");
    if (wrap) parts.push(wrap.innerText);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) for (const id of lb.split(/\s+/)) { const n = document.getElementById(id); if (n) parts.push(n.innerText); }
    if (el.getAttribute("aria-label")) parts.push(el.getAttribute("aria-label"));
    return parts.join(" ").replace(/\s+/g, " ").trim().slice(0, 300);
  };
  // R14-01: the label that leaves the page as label text is rebuilt from the label's own visible text nodes (a
  // <label for>, a wrapping <label>, aria-labelledby targets), as pieces URI render-checks like page text. aria-label
  // and hidden label elements are not drawn, so they are never sent as a label; `label` (labelOf) is used only to
  // decide whether a field is private.
  const MAX_LABEL_PIECES = 20;
  const labelPieces = (el) => {
    const srcs = [];
    if (el.id) srcs.push(...document.querySelectorAll(`label[for="${CSS.escape(el.id)}"]`));
    const wrap = el.closest("label");
    if (wrap) srcs.push(wrap);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) for (const id of lb.split(/\s+/)) { const n = id && document.getElementById(id); if (n) srcs.push(n); }
    const ps = [], seen = new Set();
    for (const src of srcs) {
      const w = document.createTreeWalker(src, NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n && ps.length < MAX_LABEL_PIECES; n = w.nextNode()) {
        if (seen.has(n) || !n.nodeValue.trim() || inField(n) || !textVisible(n)) continue;
        seen.add(n); ps.push(...nodePieces(n, 0, n.nodeValue.length, ps.length ? ps[ps.length - 1].g + 1 : 0));
      }
    }
    return ps.length ? finish(ps.slice(0, MAX_LABEL_PIECES), " ") : [];
  };
  // R15-01: the value of a contenteditable that leaves the page as field text is rebuilt from its own visible text
  // nodes (not innerText, which includes opacity:0 and off-screen descendants), as pieces URI render-checks like page
  // text. An input's or textarea's value is not a text node the probe can repaint, so URI never sends it to the Brain
  // (fail closed); `value` stays here only for D8 and the Live Assist checks.
  const MAX_VALUE_PIECES = 40;
  const valuePieces = (el) => {
    const ps = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n && ps.length < MAX_VALUE_PIECES; n = w.nextNode()) {
      if (!n.nodeValue.trim() || !n.parentElement || n.parentElement.closest(FIELD) !== el || !textVisible(n)) continue;
      ps.push(...nodePieces(n, 0, n.nodeValue.length, ps.length ? ps[ps.length - 1].g + 1 : 0));
    }
    return ps.length ? finish(ps.slice(0, MAX_VALUE_PIECES), " ") : [];
  };
  const sensitive = (el, label, value) => {
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (SENSITIVE_TYPES.has(type)) return true;
    const named = [label, el.name, el.getAttribute("placeholder"), el.getAttribute("aria-label")].filter(Boolean);
    if (type !== "checkbox" && type !== "radio" && SHORT_CODE.test(value || "") && named.some(shortCodeLabel)) return true;
    const ac = (el.getAttribute("autocomplete") || "").toLowerCase().split(/\s+/);
    if (ac.some((t) => SENSITIVE_AC.has(t))) return true;
    return [el.name, el.id, label, el.getAttribute("placeholder"), el.getAttribute("aria-label")]
      .some((v) => v && secretName(v));
  };

  // Owner decision D8: values are withheld by default (fail closed); same rule as redact.py value_shareable().
  const SHAREABLE_NAME = /^(q|query|search|searchterm|searchquery|searchtext|keyword|keywords|comment|comments|message|feedback|subject|title|description|note|notes|remark|remarks)$/;
  const joinedName = (v) => String(v || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  const shareable = (el, type, label) => {
    if (type === "checkbox" || type === "radio") return true;
    if (type === "search" || ["searchbox", "search"].includes((el.getAttribute("role") || "").toLowerCase())) return true;
    if (!["", "text", "textarea", "contenteditable", "input"].includes(type)) return false;
    return [el.getAttribute("name"), el.id, label].some((v) => v && SHAREABLE_NAME.test(joinedName(v)));
  };
  const fields = [], sensitiveRects = [];
  for (const el of document.querySelectorAll("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) {
    if (fields.length >= MAX_FIELDS) break;
    const type = el.isContentEditable ? "contenteditable" : (el.getAttribute("type") || el.tagName).toLowerCase();
    if (["submit", "button", "reset", "image", "file"].includes(type)) continue;
    const label = labelOf(el);
    let value = "";
    if (el.tagName === "SELECT") value = el.selectedOptions[0] ? el.selectedOptions[0].text : "";
    else if (el.isContentEditable) value = el.innerText;
    else if (type === "checkbox" || type === "radio") value = el.checked ? "checked" : "unchecked";
    else value = el.value || "";
    const isSensitive = sensitive(el, label, value);
    const withheld = isSensitive || !shareable(el, type, label);
    const shown = visible(el);
    if (!shown && !isSensitive) continue;          // invisible ordinary fields are not part of what the user sees
    const f = {
      id: maskText(el.id || ""), tag: el.tagName.toLowerCase(), type, name: maskText(el.getAttribute("name") || ""),
      label: maskText(label), autocomplete: el.getAttribute("autocomplete") || "",
      placeholder: maskText(el.getAttribute("placeholder") || ""),
      required: !!el.required || el.getAttribute("aria-required") === "true", readonly: !!el.readOnly || !!el.disabled,
      visible: shown, label_pieces: shown ? labelPieces(el) : [],
    };
    if (shown) f.rect = rectOf(el);
    if (withheld) {
      f.sensitive = true; f.withheld = isSensitive ? "sensitive" : "not_shared"; f.has_value = !!value; f.value = "";
      if (value) bump(isSensitive ? "sensitive_field" : "withheld_field");
      if (shown) sensitiveRects.push(f.rect);
    } else {
      f.sensitive = false; f.value = maskText(String(value).slice(0, MAX_VALUE));
      if (shown && el.isContentEditable) f.value_pieces = valuePieces(el);
    }
    fields.push(f);
  }

  // Visible text only: hidden, aria-hidden, zero-size, transparent, off-screen, clipped and covered text is skipped.
  const chunks = [], textPieces = []; let total = 0, textGroup = 0;
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n && total < MAX_TEXT; n = walker.nextNode()) {
    const t = n.nodeValue.replace(/\s+/g, " ").trim();
    if (!t) continue;
    const p = n.parentElement;
    if (!p || p.closest("input,textarea,select,[contenteditable]:not([contenteditable='false'])")) continue;
    if (!textVisible(n)) { bump("hidden_text"); continue; }
    chunks.push(maskText(t)); total += t.length + 1;
    if (textPieces.length < MAX_TEXT_PIECES) {
      for (const q of finish(nodePieces(n, 0, n.nodeValue.length, textGroup++), "\n")) {
        if (textPieces.length < MAX_TEXT_PIECES) textPieces.push(q);
      }
    }
  }
  // Headings are rebuilt from their own visible text nodes (R11-01), not from innerText.
  const visibleTextOf = (el, ps) => { const parts = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) if (n.nodeValue.trim() && textVisible(n)) {
      parts.push(n.nodeValue); ps.push(...nodePieces(n, 0, n.nodeValue.length, ps.length ? ps[ps.length - 1].g + 1 : 0));
    }
    return parts.join(" ").replace(/\s+/g, " ").trim(); };
  const headPieces = [];
  const headings = [...document.querySelectorAll("h1,h2,h3")].filter(visible)
    .map((h) => { const ps = [], t = maskText(visibleTextOf(h, ps)); if (t) headPieces.push(finish(ps, " ").slice(0, MAX_HEAD_PIECES)); return t; })
    .filter(Boolean).slice(0, MAX_HEADINGS);
  headPieces.splice(MAX_HEADINGS);
  // R9-01: the selection is rebuilt from the page's own text nodes inside the selected ranges. Text selected inside a
  // field (an input's or textarea's value, a select, a contenteditable) is that field's value and is never copied;
  // only the fact that such a selection exists is reported (selection_withheld).
  // R10-01 / R11-01: the same per-text-node visibility rule as the page text above (hidden, aria-hidden, tiny,
  // transparent, off-screen, clipped, indented-away, covered and script/style/noscript/template text is never copied
  // into the selection).
  const shownText = (n) => {
    if (!n.nodeValue.trim()) return true;
    const ok = textVisible(n);
    if (!ok) bump("hidden_text");
    return ok;
  };
  const selectionOf = () => {
    const s = window.getSelection ? window.getSelection() : null;
    if (!s) return { text: "", withheld: false, pieces: [] };
    let withheld = false; const parts = [], ps = [];
    for (let i = 0; i < s.rangeCount; i++) {
      const r = s.getRangeAt(i);
      if (r.collapsed) continue;
      const root = r.commonAncestorContainer;
      if (inField(root)) { withheld = true; continue; }
      const nodes = [];
      if (root.nodeType === 3) { if (shownText(root)) nodes.push(root); }
      else {
        const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
        for (let n = w.nextNode(); n; n = w.nextNode()) {
          if (!r.intersectsNode(n)) continue;
          if (n.nodeType === 1) { if (n.matches(FIELD)) withheld = true; continue; }
          if (inField(n)) { withheld = true; continue; }
          if (!shownText(n)) continue;
          nodes.push(n);
        }
      }
      for (const n of nodes) {
        const a = n === r.startContainer ? r.startOffset : 0, b = n === r.endContainer ? r.endOffset : n.nodeValue.length;
        parts.push(n.nodeValue.slice(a, b));
        if (b > a && ps.length < MAX_SEL_PIECES) ps.push(...nodePieces(n, a, b, ps.length ? ps[ps.length - 1].g + 1 : 0));
      }
    }
    const text = parts.join("").replace(/\s+/g, " ").trim();
    // Anything the browser reports as selected that is not page text (a field's inner editor) is withheld.
    if (!text && String(s).trim()) withheld = true;
    return { text, withheld, pieces: text ? finish(ps.slice(0, MAX_SEL_PIECES), "") : [] };
  };
  const selected = selectionOf();
  const sel = maskText(selected.text.slice(0, 4000));
  // Every text that leaves the page passes maskText (title, headings, labels, placeholders and the whole URL too).
  // R1-04: the userinfo (user:password@) is removed and the value of every query or fragment key that names a secret
  // (the field-name rules above, a key ending in code / pin / key, sig / signature / sid) is masked whatever its
  // length (same rule as redact_url in redact.py).
  const secretKey = (k) => { let d = k; try { d = decodeURIComponent(k); } catch (e) { /* keep as is */ }
    const j = joined(d);
    return secretName(d) || (CODE_END.test(j.replace(READABLE, "")) && !CODE_EXCLUDE.test(j)) || /^(sig|signature|sid)$/.test(j); };
  const maskUrl = (href) => {
    let out = maskText(String(href)).replace(/^([a-z][a-z0-9+.-]*:\/\/)[^\/?#@\s]*@/i, (m, sch) => { bump("url_userinfo"); return sch; });
    const at = out.search(/[?#]/);
    if (at >= 0) out = out.slice(0, at) + out.slice(at).replace(/([?#&;])([^=&#;?\s]*)=([^&#;\s]*)/g, (m, p, k, v) =>
      v && v !== "[redacted]" && secretKey(k) ? (bump("query_secret"), `${p}${k}=[redacted]`) : m);
    return out;
  };
  const url = maskUrl(location.href);

  return {
    schema: "uri.assist.dom.v1", url, title: maskText(document.title.slice(0, 500)), lang: document.documentElement.lang || "",
    selection: sel, selection_source: "page_text", selection_withheld: selected.withheld, headings, text: chunks.join("\n").slice(0, MAX_TEXT), fields, sensitive_rects: sensitiveRects,
    redactions: counts, device_pixel_ratio: dpr,
    // D10 / R13-01: what URI may send as page text, selection and headings, each piece naming its text units.
    pieces: { text: textPieces, selection: selected.pieces, headings: headPieces }, units,
    viewport: { w: innerWidth, h: innerHeight },
  };
})();
