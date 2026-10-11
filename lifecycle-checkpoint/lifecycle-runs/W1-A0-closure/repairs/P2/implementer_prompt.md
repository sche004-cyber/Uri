You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 16f75d8e2e5f537749b32b1d754c347cbebdfc36.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 16f75d8e2e5f537749b32b1d754c347cbebdfc36 and PASSES after
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
  "id": "R2-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Redaction still misses lowercase run-together OTP/CVV/PIN/password field names (R1-02 class not closed), in both Python and in-page JS",
  "files": [
   "uri_assist/redact.py:26",
   "uri_assist/redact.py:34",
   "uri_assist/browser_extension/snapshot.js:10",
   "uri_assist/browser_extension/snapshot.js:11"
  ],
  "evidence": "_words() splits only on case changes, letter/digit changes and _-.:/, and _SENSITIVE_WORDS requires \\b around otp/cvv/pin/password, so a lowercase run-together name never matches (only [a-z]*otp at the END of a word is handled). field_is_sensitive({'type':'text','name':n,'value':'482913'}) is False for otpcode, smsotpcode, otpvalue, otpnumber, cvvcode, cvvnumber, cardcvv, cardcvc, userpassword, newpassword, confirmpassword, loginpassword, txnpassword, upipin, atmpin, cardpin, securitypin, loginpwd, userpass, verifycode. Real Chromium (run_snapshot.cjs + snapshot.js) on <input name=otpcode value=482913>, <input name=cvvcode value=123>, <input name=newpassword type=text value=Hunter2Secret!>, <input name=upipin value=4321> returned sensitive:false with all four values. AssistCommands.assist_ask with a fake browser adapter put all four values into the stream_chat body (probe /tmp/uri_review_R2/probe_brain.py). popup.html promises one-time codes are removed in the page; A0_QUALIFICATION marks A0-AC7 MET.",
  "suggested_fix": "In both layers also match sensitive stems as substrings of a run-together token, with an explicit list of harmless words to skip (e.g. (otp|cvv|cvc|ccv|password|passwd|passcode|pwd|mpin|tpin|upipin|atmpin) anywhere, 'pin' only as a suffix of a known prefix), keeping pincode/spinner/hotpot readable; add these names to tricky_fields.html and the Python/JS parity test."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
