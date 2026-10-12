You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 16155129b72685f25eca48a65252f6cd51fa47e4.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R3-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 3,
  "finding": {
   "id": "R3-01",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "Redaction still misses run-together OTP/CVV/PIN and token/secret field names (R2-01 class not closed), in both Python and the in-page JS; values reach the Brain request",
   "files": [
    "uri_assist/redact.py:35",
    "uri_assist/redact.py:61",
    "uri_assist/redact.py:101",
    "uri_assist/browser_extension/snapshot.js:12",
    "uri_assist/browser_extension/snapshot.js:14",
    "uri_assist/browser_extension/snapshot.js:73",
    "docs/assist/A0_QUALIFICATION.md:19"
   ],
   "evidence": "field_is_sensitive({'type':'text','name':n,'value':'482913'}) is False for emailverificationcode, mfacode, onetimecode, twofactorcode, 2facode, tfacode, authenticatorcode, authenticationcode, onetimepin, smspin, cardcode and cardverificationcode (also False with value '123'), and for authtoken, accesstoken, clientsecret and secretkey. \\bverification ?code\\b and \\bone ?time\\b need a word boundary that a prefix removes; _CODE_LABEL (\\bcode\\b) misses run-together '...code'; RUN_TOGETHER enumerates prefixes. Real Chromium (tests/assist/fixtures/run_snapshot.cjs on /tmp/uri_review_R3/leak.html) returned sensitive:false with values 482913/551203/660114/737/884205/9152 for emailverificationcode/mfacode/onetimecode/cardcode/twofactorcode/onetimepin. Feeding that snapshot through AssistCommands (FakeAdapter, FakeClient) and assist_ask put all six values into the Brain request body (/tmp/uri_review_R3/e2e_leak.py). The names cited in R1-02 and the R2 regression list are fixed. A0_QUALIFICATION still says AC7 is 'MET in both layers after the R1 repair'.",
   "suggested_fix": "Stop enumerating prefixes. In both layers: match otp|mfa|2fa|onetime|twofactor|verification|authenticat|cvv|cvc|token|secret as substrings of the joined word; treat a short all-digit value as a code when any name, label or placeholder word ENDS with code or pin (keeping the postal/zip/pincode/country/area exclusions); keep the JS pattern byte-identical to Python. Add these names to tricky_fields.html and the parity test, and correct the AC7 row."
  }
 },
 {
  "round": 4,
  "finding": {
   "id": "R4-01",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "Redaction still misses run-together API-key names and alphanumeric 2FA recovery codes in both Python and the in-page JS (R3-01 token/secret class not closed); values reach the Brain request",
   "files": [
    "uri_assist/redact.py:47",
    "uri_assist/redact.py:139",
    "uri_assist/browser_extension/snapshot.js:15",
    "uri_assist/browser_extension/snapshot.js:84",
    "docs/assist/A0_QUALIFICATION.md:19"
   ],
   "evidence": "_STEMS lacks apikey and other *key stems; 'apikey' matches only as a whole word in _SENSITIVE_WORDS. The short-code rule needs an all-digit value. field_is_sensitive({'type':'text','name':N,'value':'Zx9-kq_7Lm'}) is False for stripeapikey, openaiapikey, myapikey, userapikey, xapikey, accessKey, accesskey, signingkey, sessionkey, encryptionkey and masterkey, and for recovery_code/backup_code (label 'Recovery code') with value '7f3a9-2c1d8'. Real Chromium (run_snapshot.cjs) on a page with those inputs returned sensitive:false with the values. AssistCommands assist_ask (FakeAdapter fed the Chromium snapshot, FakeClient) put all four values (Zq81LmXv0PaT, Wk22HnRt9QbU, 7f3a9-2c1d8, Pp55TrEw3ZaQ) into the Brain request body. 'my', 'user', 'client' and 'access' are in the R3 test's own PREFIXES list, but 'apikey' is not among its STEMS. A0_QUALIFICATION again claims 'MET in both layers after the R3 repair'.",
   "suggested_fix": "Add apikey and (api|access|auth|private|secret|signing|encryption|master|session|client|hmac)key stems to _STEMS/STEMS. Treat recovery/backup code fields as sensitive whatever the value. Add these to the generated corpus and the Chromium parity test, and correct the A0_QUALIFICATION claim."
  }
 },
 {
  "round": 4,
  "finding": {
   "id": "R4-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "Citation verifier and conflict detector ignore magnitude suffixes (m/bn/k/M, lakh/crore, trillion), so a claim with a different magnitude survives verify",
   "files": [
    "uri_web/evaluate.py:15",
    "uri_web/synthesize.py:90",
    "uri_web/evaluate.py:129",
    "uri_web/surface.py:58"
   ],
   "evidence": "_NUMBER captures only %/percent/million/billion/thousand units. verify('The company raised $5bn in new funding from investors this year [1].', ['The company raised $5m in new funding from investors this year.']) -> KEPT. Also KEPT: $5k->$5M, '2 lakh'->'2 crore', 'Rs.500 crore'->'Rs.500 trillion', '5 km'->'5 miles'. EV.evaluate on two sources '$5m' vs '$5bn' -> 0 conflicts; '2 lakh' vs '2 crore' -> 0 conflicts ('Rs.500' vs 'Rs.900' -> 1). The surface states 'citations checked against the sources (wording, numbers, negation)'. W1-AC10/AC11.",
   "suggested_fix": "Normalise attached magnitude tokens (k, m, mn, bn, b, M, trillion, lakh, crore, and their plurals/abbreviations) into the number key, and treat a scale word next to a number as part of it. Add regression cases for $5m/$5bn, lakh/crore and trillion."
  }
 },
 {
  "round": 4,
  "finding": {
   "id": "R4-03",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "SafeFetcher total timeout and cancellation are not enforced while response headers or chunk framing arrive; a hostile server can hold a fetch (and the single research job) far beyond the budget",
   "files": [
    "uri_web/safe_fetch.py:233",
    "uri_web/safe_fetch.py:247",
    "uri_web/safe_fetch.py:248",
    "uri_web/bridge.py:95"
   ],
   "evidence": "The deadline and the cancel flag are checked only between body chunks. The httpx read timeout applies per socket read. Probe /tmp/uri_review_R4/ssrf/p4_sockets.py: a real local server drips header bytes every 0.3 s; SafeFetcher(read_timeout=1.0, total_timeout=2.0) with cancel at 1.0 s returned UNREACHABLE after 67.3 s (re-run by me). A chunk-extension drip returned CANCELLED only after 12.1 s with total_timeout 2.0. A server that drips under the 10 s default read timeout holds the fetch with no bound, and WebResearch stays busy (RESEARCH_IN_PROGRESS). W1-AC4 (total timeout) and W1-AC13 (cooperative cancellation) are unmet against a hostile page.",
   "suggested_fix": "Enforce a wall-clock deadline on the whole request, e.g. a watchdog timer that closes the response/transport at min(deadline, cancel), or per-read timeouts recomputed from the remaining budget. Add a slow-header regression test with a real socket."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "16f75d8e2e5f537749b32b1d754c347cbebdfc36", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04"]}, {"repair": 2, "commit": "627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede", "addresses": ["R2-01"]}, {"repair": 3, "commit": "16155129b72685f25eca48a65252f6cd51fa47e4", "addresses": ["R3-01"]}]

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)

End with:
DIAGNOSIS_BEGIN
{"root_cause": "...", "why_earlier_repairs_failed": "...", "evidence": ["path:line ..."], "proposed_fix": "...",
 "needs_owner": false}
DIAGNOSIS_END
