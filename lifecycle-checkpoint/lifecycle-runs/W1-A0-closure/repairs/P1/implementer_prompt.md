You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 8019d41b77bae91598fa45b5ea827ab54d1cf64c.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 8019d41b77bae91598fa45b5ea827ab54d1cf64c and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_web/**, uri_assist/**, tests/web/**, tests/assist/**, uri_ui/lib/living/**, uri_ui/test/living/**, docs/assist/**, scripts/run_uri_integrated_worker.py.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)

Findings (from the reviewer, verbatim):
[
 {
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
 },
 {
  "blocking": true,
  "evidence": "_words() splits only lower->Upper and [_-.:/], not acronym->Word or letter<->digit, and \\b fails before a digit. field_is_sensitive({'type':'text','name':n,'value':'12345678'}) is False for OTPCode, SMSOTP, cvv2, CVV2, cvc2, ccv, mpin, MPIN, tpin, acctNumber, acct_no, cardExpiry, passcode2, pwd1. Real Chromium snapshot of <input name=\"OTPCode\" value=\"482913\"> and <input name=\"cvv2\" value=\"123\"> returns sensitive:false with the values; AssistCommands assist_ask with a FakeAdapter sends '482913' and '123' into the Brain request body.",
  "expected": "A0-AC7: OTP, card (CVV) and password/PIN fields have their values removed before anything leaves the adapter.",
  "files": [
   "uri_assist/redact.py:32",
   "uri_assist/redact.py:98",
   "uri_assist/browser_extension/snapshot.js:11"
  ],
  "id": "R1-02",
  "severity": "MEDIUM",
  "suggested_minimal_fix": "In both layers split names also at acronym->Word ('OTPCode'->'otp code') and letter<->digit ('cvv2'->'cvv 2'); add cvv2/cvc2/ccv/mpin/tpin/acct; add these names to tricky_fields.html and the parity test.",
  "title": "Redaction name matching still misses common OTP/CVV/PIN/password field names (F5 repair incomplete), in both Python and in-page JS"
 },
 {
  "blocking": false,
  "evidence": "asking => askId != null && answer == null (added in 1844b48); revoke() sets answer=null but leaves askId. Flutter probe test (3.47.7): grant -> ask -> assist.answer COMPLETE -> revoke -> grant: printed 'after re-grant: active=true asking=true answer=null'; the Ask button (enabled only when !a.asking) stays disabled, 'URI is reading what you shared\u2026' is shown, and no poll or event ever clears it until the worker restarts.",
  "expected": "After Stop and a new grant the user can ask again; no 'reading' indicator without a running ask.",
  "files": [
   "uri_ui/lib/living/assist/assist_controller.dart:52",
   "uri_ui/lib/living/assist/assist_controller.dart:171",
   "uri_ui/lib/living/assist/assist_mode_view.dart:305"
  ],
  "id": "R1-03",
  "severity": "MEDIUM",
  "suggested_minimal_fix": "In revoke() (and grant()) also set askId = null when no ask is running, or track asking with an explicit flag cleared in _finishAnswer/_resetForNewWorker; add a widget test for ask -> stop -> share -> ask.",
  "title": "After an answered question, Stop then a new grant leaves Ask permanently disabled (introduced by the F4 UI repair)"
 },
 {
  "blocking": false,
  "evidence": "Real Chromium on a page with <title>Reset eyJ...JWT... 4111 1111 1111 1111</title>, <h1>Card 4111 1111 1111 1111 key sk-abcdefghijklmnopqrstuv</h1>, label 'Name ghp_abcdef...1234', placeholder 'AKIAABCDEFGHIJKLMNOP': the snapshot returned all of these verbatim (only body text was masked). Python normalise() masks them afterwards, so the Brain prompt is clean, but the script's comment 'Private values are removed HERE, inside the page' and the doc's 'MET in both layers' are false.",
  "expected": "Parity: every text that leaves the page passes maskText, as Python's redact_text/redact_field do.",
  "files": [
   "uri_assist/browser_extension/snapshot.js:65",
   "uri_assist/browser_extension/snapshot.js:94",
   "uri_assist/browser_extension/snapshot.js:124",
   "uri_assist/browser_extension/snapshot.js:126",
   "uri_assist/browser_extension/snapshot.js:130",
   "docs/assist/A0_QUALIFICATION.md"
  ],
  "id": "R1-04",
  "severity": "MEDIUM",
  "suggested_minimal_fix": "Apply maskText to title, headings, label, placeholder and the full URL in snapshot.js; extend the Chromium parity test to compare title/headings/labels.",
  "title": "In-page snapshot layer does not mask title, headings, labels, placeholders or URL path; docs claim AC7 'MET in both layers'"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
