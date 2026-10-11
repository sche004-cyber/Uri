// URI Assist page snapshot (schema uri.assist.dom.v1). Injected only by an explicit user click (activeTab).
// Read-only: it never changes the page, never submits, never reads cookies or storage.
// Private values are removed HERE, inside the page, before the snapshot exists; URI redacts again on receipt.
(() => {
  const MAX_TEXT = 40000, MAX_FIELDS = 200, MAX_HEADINGS = 60, MAX_VALUE = 2000;
  const SENSITIVE_TYPES = new Set(["password", "hidden"]);
  const SENSITIVE_AC = new Set(["current-password", "new-password", "one-time-code", "cc-number", "cc-csc", "cc-exp",
    "cc-exp-month", "cc-exp-year", "cc-name", "cc-type"]);
  // Same rules as uri_assist/redact.py (kept in sync; tests/assist checks both on one fixture).
  const SENSITIVE_WORDS = /\b(pass|pw|pwd|[a-z]*otp|mfa|2 ?fa|pin(?! ?code)|mpin|tpin|cvv|cvc|ccv|csc|cvn|ssn|pan|iban|secret|token|cookie|session|auth|password|passwd|passcode|passphrase|apikey|aadhar|aadhaar)\b|\bapi ?key\b|\bone ?time\b|\btwo ?factor\b|\bverification ?code\b|\bsecurity ?(code|answer)\b|\bauth ?code\b|\bcard ?(number|num|no|expiry|exp|expiration)\b|\bacct ?(number|num|no)\b|\bcc ?(num|number|no)\b|\baccount ?(number|num|no)\b|\bsocial ?security\b|\bpan ?(number|no)\b|\bprivate ?key\b/;
  // Run-together lowercase names (see _RUN_TOGETHER in redact.py; same pattern).
  const RUN_TOGETHER = /password|passwd|passcode|passphrase|pwd|cvv|cvc|ccv|\b(mpin|tpin)|(mpin|tpin)\b|\botp|otp\b|otp(code|value|val|number|num|no|input|field|digit|box|text|entry|pin|token)|(upi|atm|card|security|secure|login|user|txn|transaction|account|acct|debit|credit|bank|access|mobile|wallet|new|old|confirm|current|verify|secret)pin(number|num|no)?\b|\bpin(number|num|no|entry|input|field|value)\b|(user|login|admin|account|acct|new|old|confirm|current|root|wifi|txn|master|secret|db)pass\b|(verify|verif|sms|email|access|activation|confirmation|confirm|login|signin)code\b/;
  // Secret stems inside run-together words, and short codes in fields whose name ends in code / pin (see _STEMS,
  // _CODE_END and _CODE_EXCLUDE in redact.py; same patterns).
  const STEMS = /otp(?![ahlo])|mfa|2fa|\btfa|onetime|twofactor|verification|authenticat|cvv|cvc|ccv|token|secret(?!ar)|password|passwd|passcode|passphrase|pwd/;
  const CODE_END = /(code|pin)(number|num|no)?$/, CODE_EXCLUDE = /postal|zip|postcode|pincode|country|area|promo|coupon|voucher|referral|barcode|sortcode|ifsc|swift/;
  const tokens = (v) => String(v).replace(/(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])/g, " ").replace(/[^A-Za-z0-9]+/g, " ").toLowerCase();
  const joined = (v) => String(v).toLowerCase().replace(/[^a-z0-9]+/g, "");
  const shortCodeLabel = (v) => !POSTAL.test(v) && !CODE_EXCLUDE.test(joined(v)) &&
    (CODE_LABEL.test(words(v)) || CODE_END.test(joined(v)));
  const words = (v) => String(v).replace(/(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])/g, " ").replace(/[_\-.:/]+/g, " ").toLowerCase();
  const SHORT_CODE = /^\s*\d{3,8}\s*$/, CODE_LABEL = /\bcode\b/, POSTAL = /postal|zip|post ?code|pin ?code/i;
  const counts = {};
  const bump = (k) => { counts[k] = (counts[k] || 0) + 1; };
  const luhn = (d) => { let t = 0, alt = false; for (let i = d.length - 1; i >= 0; i--) { let n = +d[i];
    if (alt) { n *= 2; if (n > 9) n -= 9; } t += n; alt = !alt; } return t % 10 === 0; };
  const TEXT_RULES = [
    ["jwt", /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g],
    ["bearer", /\bbearer\s+[A-Za-z0-9._~+/=-]{16,}/gi],
    ["api_key", /\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bxox[abpr]-[A-Za-z0-9-]{10,}\b|\btvly-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{30,}\b/g],
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
  const sensitive = (el, label, value) => {
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (SENSITIVE_TYPES.has(type)) return true;
    const named = [label, el.name, el.getAttribute("placeholder"), el.getAttribute("aria-label")].filter(Boolean);
    if (SHORT_CODE.test(value || "") && named.some(shortCodeLabel)) return true;
    const ac = (el.getAttribute("autocomplete") || "").toLowerCase().split(/\s+/);
    if (ac.some((t) => SENSITIVE_AC.has(t))) return true;
    return [el.name, el.id, label, el.getAttribute("placeholder"), el.getAttribute("aria-label")]
      .some((v) => v && (SENSITIVE_WORDS.test(words(v)) || RUN_TOGETHER.test(words(v)) || STEMS.test(tokens(v))));
  };

  const fields = [], sensitiveRects = [];
  for (const el of document.querySelectorAll("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) {
    if (fields.length >= MAX_FIELDS) break;
    const type = (el.getAttribute("type") || el.tagName).toLowerCase();
    if (["submit", "button", "reset", "image", "file"].includes(type)) continue;
    const label = labelOf(el);
    let value = "";
    if (el.tagName === "SELECT") value = el.selectedOptions[0] ? el.selectedOptions[0].text : "";
    else if (el.isContentEditable) value = el.innerText;
    else if (type === "checkbox" || type === "radio") value = el.checked ? "checked" : "unchecked";
    else value = el.value || "";
    const isSensitive = sensitive(el, label, value);
    const shown = visible(el);
    if (!shown && !isSensitive) continue;          // invisible ordinary fields are not part of what the user sees
    const f = {
      id: maskText(el.id || ""), tag: el.tagName.toLowerCase(), type, name: maskText(el.getAttribute("name") || ""),
      label: maskText(label), autocomplete: el.getAttribute("autocomplete") || "",
      placeholder: maskText(el.getAttribute("placeholder") || ""),
      required: !!el.required || el.getAttribute("aria-required") === "true", readonly: !!el.readOnly || !!el.disabled,
      visible: shown,
    };
    if (shown) f.rect = rectOf(el);
    if (isSensitive) {
      f.sensitive = true; f.has_value = !!value; f.value = "";
      if (value) bump("sensitive_field");
      if (shown) sensitiveRects.push(f.rect);
    } else {
      f.sensitive = false; f.value = maskText(String(value).slice(0, MAX_VALUE));
    }
    fields.push(f);
  }

  // Visible text only: hidden, aria-hidden, zero-size, transparent and off-screen text is skipped.
  const chunks = []; let total = 0;
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  const cache = new Map();
  for (let n = walker.nextNode(); n && total < MAX_TEXT; n = walker.nextNode()) {
    const t = n.nodeValue.replace(/\s+/g, " ").trim();
    if (!t) continue;
    const p = n.parentElement;
    if (!p || p.closest("input,textarea,select,[contenteditable]:not([contenteditable='false'])")) continue;
    let ok = cache.get(p);
    if (ok === undefined) { ok = visible(p); cache.set(p, ok); }
    if (!ok) { bump("hidden_text"); continue; }
    chunks.push(maskText(t)); total += t.length + 1;
  }
  const headings = [...document.querySelectorAll("h1,h2,h3")].filter(visible)
    .map((h) => maskText(h.innerText.replace(/\s+/g, " ").trim())).filter(Boolean).slice(0, MAX_HEADINGS);
  const sel = maskText(String(window.getSelection ? window.getSelection() : "").slice(0, 4000));
  // Every text that leaves the page passes maskText (title, headings, labels, placeholders and the whole URL too).
  const url = maskText(location.href).replace(/([?&](?:access_?token|token|api_?key|key|secret|password|pwd|sig|signature|code)=)(?!\[redacted\])[^&#]*/gi,
    (m, k) => { bump("query_secret"); return k + "[redacted]"; });

  return {
    schema: "uri.assist.dom.v1", url, title: maskText(document.title.slice(0, 500)), lang: document.documentElement.lang || "",
    selection: sel, headings, text: chunks.join("\n").slice(0, MAX_TEXT), fields, sensitive_rects: sensitiveRects,
    redactions: counts, device_pixel_ratio: dpr,
  };
})();
