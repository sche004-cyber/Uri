You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R2-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 2,
  "finding": {
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
 },
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
 }
]
Earlier repair commits: [{"repair": 1, "commit": "16f75d8e2e5f537749b32b1d754c347cbebdfc36", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04"]}, {"repair": 2, "commit": "627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede", "addresses": ["R2-01"]}]

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
