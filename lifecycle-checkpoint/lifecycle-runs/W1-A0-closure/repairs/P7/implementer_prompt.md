You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 3dd9cde91818cfcf2db48067e8d4b56a1bda62f4.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 3dd9cde91818cfcf2db48067e8d4b56a1bda62f4 and PASSES after
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
  "id": "R9-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Text selected inside a withheld or sensitive field (OTP, CVV, any form field) is copied into the snapshot 'selection' and sent to the Brain as 'Selected text', bypassing D8 field withholding in both layers",
  "files": [
   "uri_assist/browser_extension/snapshot.js:156",
   "uri_assist/perception.py:121",
   "uri_assist/bridge.py:61",
   "docs/assist/A0_QUALIFICATION.md:19",
   "uri_assist/browser_extension/manifest.json:5"
  ],
  "evidence": "Real Chromium (/tmp/uri_review_R9/d8/sel_probe2.cjs, sel_probe3.cjs, sel_probe4.cjs). For <input name=otp autocomplete=one-time-code value=482913>, double-click gives snapshot.selection=\"482913\" while the field itself reports withheld=sensitive. For <input name=cvv autocomplete=cc-csc value=417>, selection=\"417\", and it still does after the element is blurred and the page loses focus. A selected email or address in a not_shared field leaks the same way. Python normalise passes selection through redact_text only, so bridge._context_block prints 'Selected text: 417' next to '- Security code (CVV): [private field, value hidden]' (/tmp/uri_review_R9/d8/py_ctx.py). Password inputs are protected only because Chromium returns bullets. A0_QUALIFICATION marks A0-AC7 'MET fail-closed'.",
  "suggested_fix": "In snapshot.js, drop the selection when its anchor/focus lies in a field (document.activeElement is input/textarea/select/contenteditable, or the selection range intersects a withheld field). Report only a has_selection flag in that case. Mirror this in Python by not accepting a selection unless the adapter marks it as page text. Add Chromium plus Brain-body regression tests."
 },
 {
  "id": "R9-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "D7 quantity detection is a word list: ordinals beyond 'tenth', -th forms of scale words, Unicode vulgar fractions and Roman numerals are not detected, so a Brain sentence with a changed value is shown in the Brain's words (R1-01 class not closed under D7)",
  "files": [
   "uri_web/synthesize.py:71",
   "uri_web/synthesize.py:110",
   "docs/assist/W1_QUALIFICATION.md:22"
  ],
  "evidence": "/tmp/uri_review_R9/d7_probe2.py runs synthesize() with a fake Brain against one source stating 'eleventh', 'hundredth', '\u00bc' and 'Chapter VII'. Shown, quoted=False, method=brain, dropped=[]: 'The runner finished twelfth in the final race...', 'The museum celebrated its thousandth anniversary...', 'Regulators said the levy rose by \u00be...', 'Officials said the company filed for Chapter XI protection...'. states_quantity() is False for each. W1_QUALIFICATION claims 'MET by construction for quantities (digits, number words, fractions, ordinals ...)'.",
  "suggested_fix": "Do not decide by a list. For a Brain sentence, show it only if every token absent from its best supporting sentence is a function word from a small allow-list; otherwise quote the source sentence or drop it. Or quote every Brain sentence. At minimum, add \\w+(th|st|nd|rd) ordinals, *th forms of scale words, the Unicode No/Nl categories (vulgar fractions, Roman numeral letters) and Roman-numeral tokens, with class tests."
 },
 {
  "id": "R9-03",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "HEAD regression: normalise() drops the adapter's has_value, so every withheld DOM field gets has_value=False; unlocated_sensitive no longer refuses screenshots for visible withheld fields without a usable rect, and filled required fields are reported REQUIRED_EMPTY",
  "files": [
   "uri_assist/perception.py:94",
   "uri_assist/redact.py:198",
   "uri_assist/perception.py:63",
   "uri_assist/checks.py:62"
  ],
  "evidence": "snapshot.js sends withheld fields as value:'' with has_value:true. perception.normalise copies only id/tag/type/name/label/autocomplete/placeholder/required/readonly/value/visible, and redact_field then sets has_value=bool('')=False. /tmp/uri_review_R9/assist/probe_required.py prints 'has_value after normalise: False' and findings [('REQUIRED_EMPTY','Roll number')] for a filled required field. probe_assist.py P2 prints unlocated_sensitive False for a visible withheld field with a value and an invalid or missing rect (True before HEAD), and P2b shows the screenshot ask completes with the image sent.",
  "suggested_fix": "In normalise, carry has_value = bool(value) or f.get('has_value') is True. In unlocated_sensitive, treat a missing has_value as unknown (unlocated). Add tests that feed the real snapshot.js output through normalise and checks."
 },
 {
  "id": "R9-04",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Brain answers derived from observed content survive revoke and re-grant: assist_ask_status returns them with no grant check and _answers is never cleared (A0-AC4 derived data after revoke)",
  "files": [
   "uri_assist/bridge.py:82",
   "uri_assist/bridge.py:236",
   "uri_assist/bridge.py:248"
  ],
  "evidence": "_answers is filled at bridge.py:236-239 and read at :251 with no access check; no grant/pause/revoke path clears it (grep shows only lines 82, 237-239, 251). /tmp/uri_review_R9/assist/probe_assist.py P1: after revoke, assist_ask_status returns FINISHED COMPLETE 'SECRET-DERIVED ANSWER about the page' with the observation summary (title, location); the same after a new grant.",
  "suggested_fix": "Clear _answers in revoke, pause and grant. Store each answer's stamp and refuse or blank the content in _assist_ask_status unless check_unchanged passes."
 },
 {
  "id": "R9-05",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Assist UI controller keeps findings and lastObservation through pause/resume and a new grant, and an ask() reply arriving after Stop restores the old observation",
  "files": [
   "uri_ui/lib/living/assist/assist_controller.dart:156",
   "uri_ui/lib/living/assist/assist_controller.dart:170",
   "uri_ui/lib/living/assist/assist_controller.dart:194"
  ],
  "evidence": "grant() clears only askId/answer; pause() and resume() clear nothing; ask() writes askId and lastObservation after the await with no stop/grant epoch check. A sub-review Flutter probe (/tmp/uri_review_R9/assist/uri_ui_copy/test/living/assist_probe_r9_test.dart, 2 passed) printed 'after Stop: state=OFF ... askId=ask-old lastObservation={title: OLD bank page...}' and 'new grant tab-news (no suggest): ... findings=1 lastObservation=OLD bank page'.",
  "suggested_fix": "Clear findings, lastObservation, answer and askId in grant/pause/resume. Capture an epoch before each await in ask()/check() and drop the reply if a stop or grant happened. Add widget tests."
 },
 {
  "id": "R9-06",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "SafeFetcher DNS resolution runs outside the total timeout watchdog and cancel (R4-03 class): a slow or hostile authoritative DNS server holds a fetch beyond its budget, twice with robots",
  "files": [
   "uri_web/safe_fetch.py:227",
   "uri_web/safe_fetch.py:283",
   "uri_web/safe_fetch.py:325"
  ],
  "evidence": "_resolve_checked calls self.resolver synchronously before _one starts the _Watchdog; cancel is checked only before resolve. /tmp/uri_review_R9/ssrf/p2_fetch.py with a 3 s resolver and total_timeout=1: 'slow_dns(3s)+robots status=TIMED_OUT elapsed=6.05s' (re-run by me). With getaddrinfo this is bounded only by the system resolver's timeouts and retries.",
  "suggested_fix": "Resolve in a worker thread joined for min(remaining, connect_timeout) while polling cancel; return TIMED_OUT or CANCELLED. Skip the page lookup when robots has used the budget."
 },
 {
  "id": "R9-07",
  "severity": "MEDIUM",
  "blocking": false,
  "category": "security",
  "owner_decision": false,
  "title": "Screenshot masking covers only fields that snapshot.js sees (no shadow DOM, no iframes) and never masks text-redacted secrets, so a vision ask can send a visible IBAN, card number or API key",
  "files": [
   "uri_assist/browser_extension/snapshot.js:105",
   "uri_assist/vision.py:47"
  ],
  "evidence": "Sub-review probes /tmp/uri_review_R9/assist/probe_shadow.py and probe_text_iframe.py (real snapshot.js in Chromium, then assist_ask with screenshot): 'fields seen by snapshot.js: [] sensitive_rects: []', status COMPLETE vision, IBAN pixel not blacked out; a card number in an iframe and '4111 1111 1111 1111'/'sk-...' in page text appear in the sent image. Non-blocking only because vision is disabled by default and the browser channel is not built (A0-AC9 application path NOT VERIFIED).",
  "suggested_fix": "Fail closed: refuse a screenshot when the page has iframes or shadow hosts that were not walked, or text redactions without rectangles. Or compute Range client rects for text redactions and walk open shadow roots."
 },
 {
  "id": "R9-08",
  "severity": "MEDIUM",
  "blocking": false,
  "category": "code",
  "owner_decision": true,
  "title": "Conflict detector still misses differences written as number words or currency only (R8-02/R8-03 conflict half); documented in HEAD as an owner-decision (D7) limitation",
  "files": [
   "uri_web/evaluate.py:282",
   "docs/assist/W1_QUALIFICATION.md:23"
  ],
  "evidence": "/tmp/uri_review_R9/conf.py: 'killed five passengers' vs 'killed seven passengers' gives 0 conflicts; '$500' vs 'Rs 500' gives 0 conflicts; the digit control '600' vs '500' gives 1. W1-AC11 requires conflicts with 'different number/date' to be identified. The answer itself is protected by D7 quoting.",
  "suggested_fix": "Owner to confirm that W1-AC11 is narrowed to 'heuristic candidates'. Otherwise parse number words and attach currency to values in numbers()."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
