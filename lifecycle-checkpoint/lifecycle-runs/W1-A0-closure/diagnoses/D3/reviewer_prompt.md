You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 52e852dcce592e15fc2098bc1e169a7e009eb26a.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R1-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 1,
  "finding": {
   "blocking": true,
   "evidence": "_NUMBER = re.compile(r\"(?<![\\w.])(\\d...\") -> numbers('Rs.500')==set(), numbers('approx.900')==set(), numbers('No.5')==set(). verify('Prices in the city market rose sharply and onions now cost Rs.900 per kilogram this week [1].', ['Prices in the city market rose sharply and onions now cost Rs.500 per kilogram this week.']) -> claim KEPT, dropped=[]. Same for 'approx.900' vs 'approx.100'. EV.evaluate on two pages 'Rs.500' vs 'Rs.900' -> conflicts 0 (with 'Rs 500'/'Rs 900' -> conflicts 1). Surface still says 'citations checked against the sources (wording, numbers, negation)'.",
   "expected": "W1-AC10: a sentence whose numbers do not occur in the cited source is dropped; W1-AC11: differing numbers are reported as a conflict.",
   "files": [
    "uri_web/evaluate.py:14",
    "uri_web/synthesize.py:163",
    "uri_web/synthesize.py:172"
   ],
   "id": "R1-01",
   "severity": "MEDIUM",
   "suggested_minimal_fix": "Extract digit runs regardless of a preceding letter or dot (e.g. lookbehind (?<![\\d,]) only, or a separate pass that pulls every \\d+(?:[.,]\\d+)* token), and add regression cases for 'Rs.500', 'approx.900', 'No.5'.",
   "title": "Citation verifier and conflict detector ignore numbers preceded by a letter or dot (e.g. 'Rs.500'), so an unsupported number survives verify"
  }
 },
 {
  "round": 5,
  "finding": {
   "id": "R5-01",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "Citation verifier and conflict detector mis-parse Indian lakh/crore digit grouping, space-grouped thousands and minus signs, so a claim with a different amount survives verify (R1-01/R4-02 class not closed)",
   "files": [
    "uri_web/evaluate.py:19",
    "uri_web/evaluate.py:69",
    "uri_web/synthesize.py:99",
    "uri_web/evaluate.py:162"
   ],
   "evidence": "_NUMBER only groups commas as \\d{1,3}(,\\d{3})+, ignores spaces as group separators and drops any sign. numbers('Rs 5,00,000')={'5','00000'} and numbers('Rs 5,00,00,000')={'5','00','00000'}, a superset, so verify('The state subsidy for each rural household is Rs 5,00,000 under the new housing scheme [1].', ['...is Rs 5,00,00,000 under the new housing scheme.']) -> KEPT (5 lakh vs 5 crore), and evaluate() on the two sentences -> conflicts 0 (subset rule at evaluate.py:162). Same with \u20b9. '1 000 000 euros' vs source '1 500 000 euros' -> KEPT, 0 conflicts. '-3.2%' vs '3.2%', '\u22123.2%' vs '3.2%' and '-12 degrees' vs '12 degrees' -> KEPT, 0 conflicts. Probes: /tmp/uri_review_R5/p_num.py, p_num2.py. W1-AC10 requires dropping sentences whose numbers do not occur in the cited source; W1-AC11 requires flagging different numbers. The module targets Rs/lakh/crore usage (R4-02 repair), where lakh grouping is the normal written form.",
   "suggested_fix": "Tokenise whole numerals first: accept Indian grouping (\\d{1,2}(,\\d{2})*,\\d{3}) and space/thin-space/NBSP grouping (\\d{1,3}([ \\u00a0\\u2009\\u202f]\\d{3})+), strip the separators to one canonical integer, and keep a leading '-'/'\u2212' (or 'minus') as part of the value. Add regressions for 5,00,000 vs 5,00,00,000, 1 000 000 vs 1 500 000 and -3.2% vs 3.2% in verify and find_conflicts."
  }
 },
 {
  "round": 5,
  "finding": {
   "id": "R5-02",
   "severity": "MEDIUM",
   "blocking": false,
   "category": "security",
   "owner_decision": false,
   "title": "Redaction misses common API-key formats (Stripe sk_live_/rk_live_, GitHub github_pat_, GitLab glpat-, npm_, hf_, SendGrid SG.) and Authorization/TAN fields in both layers; values reach the Brain request (documented residual risk L-A0-2)",
   "files": [
    "uri_assist/redact.py:10",
    "uri_assist/redact.py:88",
    "uri_assist/redact.py:51",
    "uri_assist/browser_extension/snapshot.js:35",
    "docs/assist/A0_QUALIFICATION.md:45"
   ],
   "evidence": "The api_key rule needs '(sk|pk|rk)-' with a hyphen, and long_secret cannot match across '_'. redact_text leaves sk_live_4eC39HqLyjWDarjtT1zdp7dc, rk_live_..., github_pat_11ABC..._..., glpat-..., npm_..., hf_..., SG.x.y unchanged. field_is_sensitive is False for name 'authorization' (value 'Basic dXNlcjpwYXNzd29yZA=='), 'smsTan'/'mTAN'/'tan' (value '482913'), 'otc', '2sv' and 'twoStep'. Real Chromium (snapshot.js on /tmp/uri_review_R5/fx/p.html) returns the sk_live_ and github_pat_ text and the authorization/smsTan values with sensitive:false. AssistCommands assist_ask with FakeAdapter puts 'dXNlcjpwYXNzd29yZA==', '482913' and 'sk_live_4eC39HqLyjWDarjtT1zdp7dc' in the Brain request body (p_brain.py). Non-blocking only because L-A0-2 documents that free-text secrets and fields without a secret signal may pass and AC7 is declared PATTERN-BASED, not MET. The redact.py docstring still claims 'common API-key prefixes' are masked.",
   "suggested_fix": "Extend the api_key rule in both layers to (sk|rk|pk)_(live|test)_[A-Za-z0-9]{16,}, github_pat_[A-Za-z0-9_]{40,}, glpat-[A-Za-z0-9_-]{20,}, npm_[A-Za-z0-9]{36}, hf_[A-Za-z0-9]{30,} and SG\\.[\\w-]{16,}\\.[\\w-]{16,}. Add 'authoriz' and a whole-word 'tan'/'mtan'/'smstan' to the stems and a 'Basic <base64>' rule. Add these cases to the parity corpus."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "16f75d8e2e5f537749b32b1d754c347cbebdfc36", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04"]}, {"repair": 2, "commit": "627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede", "addresses": ["R2-01"]}, {"repair": 3, "commit": "16155129b72685f25eca48a65252f6cd51fa47e4", "addresses": ["R3-01"]}, {"repair": 4, "commit": "52e852dcce592e15fc2098bc1e169a7e009eb26a", "addresses": ["R4-01", "R4-02", "R4-03"]}]

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
