These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "Both protections fail open: text is let through by default and only blocked when a list recognises it. (1) Links: untrusted._is_domain (uri_web/untrusted.py:98-104) treats an ASCII 'label.Tld' as a link only if the TLD is all-lower or all-upper, is in a hard-coded ~200-entry _TLDS list, is followed by '/', or the host has a hyphen or digit. Every other mixed-case real gTLD ('Refundsportal.Cash', '.Lol', '.CaSh', '.Exchange', '.Deals') counts as 'not a link'. Spaced defangs ('[.]' with spaces, ' dot ') and phone numbers have no pattern at all. surface.clean, verify() and extractive() all call this one detector, so a miss passes all three (W1-AC15/AC12). The default exists so that 'rose.The' and 'so.Then' are not flagged, and tests enforce that, so the detector cannot fail closed without changing those tests. (2) D7: synthesize._excerpt (uri_web/synthesize.py:141-176) lets a claim skip up to MAX_GAP_WORDS=2 content words, plus any number of function words, as long as gap_ok's states_quantity(text) check finds no quantity in the skipped text. So a qualifier ('nearly', 'possibly', 'about', 'barely', 'rarely') can be dropped next to any quantity or meaning word the _QUANTITY/_ORDINAL lists don't know ('doubling', 'halving', 'quintupled', 'biweekly', ...). The shortened claim is then shown unquoted in the Brain's words. D7 still depends on the word list, even though the code comment says it rests on _excerpt.",
 "why_earlier_repairs_failed": "Each repair turned the reviewer's examples into more list entries and kept the 'allow if unknown' default. ca622bc (R1-01/R1-02): added a bare-domain regex limited to all-lower/all-upper TLDs so that 'rose.The' still passes, and added tenfold/decade/couple to _QUANTITY. It also added _in_order, which allowed unlimited gaps. f370064 (R2-01/R2-02): canonicalised Unicode, which is correct and general, then decided ambiguous title-case TLDs with a finite _TLDS/_IDN_TLDS list and special cases, and kept the precision tests (test_w1_r16_review_regressions.py:47, test_w1_r2_review_regressions.py:43-48) that require 'rose.The', 'so.Then' and 'rose.\u00c9t\u00e9' not to be flagged. For D7 it replaced the unlimited gaps with a 2-content-word gap whose only quantity guard is states_quantity(), the same list the comment says D7 no longer depends on. It also added more list words (hourly, basis points, ...). Neither repair removed the default that lets unrecognised forms through, so the next unlisted form (R3-01: '.Cash', 'dot com', phone numbers; R3-02: 'doubling', 'biweekly', or plain qualifiers) passes again.",
 "evidence": [
  "uri_web/untrusted.py:98-104 _is_domain: ASCII TLD is a link only if islower/isupper/in _TLDS/has path/host has [-\\d]; probe: has_link_or_contact('Refundsportal.Cash')==False, 'refundsportal.CaSh'==False, 'refundsportal.Lol'==False, 'refundsportal [.] com'==False, 'refundsportal dot com'==False, 'call 1800 555 0199'==False; 'refundsportal.cash'==True",
  "uri_web/untrusted.py:51 _DOT has no spaced forms (' [.] ', ' dot '); _OTHER (line 53) has no phone pattern",
  "uri_web/surface.py:38 clean() -> U.mask_links; probe: clean('Refundsportal.Exchange') returns it unchanged",
  "uri_web/synthesize.py:282 extractive keeps 'Claim your energy rebate refund at Refundsportal.Cash before the deadline.' (quoted=False); synthesize.py:202 verify keeps it with dropped=[]",
  "tests/web/test_w1_r2_review_regressions.py:43-48 and tests/web/test_w1_r16_review_regressions.py:47 require 'The fee rose.The board', 'He said so.Then left.' and 'Caf\u00e9 prices rose.\u00c9t\u00e9' NOT be links; those tests are why the detector can't fail closed",
  "uri_web/synthesize.py:138 MAX_GAP_WORDS = 2; synthesize.py:154-160 gap_ok counts only non-function skipped words and calls states_quantity(text) as the only quantity guard; synthesize.py:149 leaves function words out of the claim sequence",
  "probe: states_quantity False for doubling/halving/tripling/quintupled/sextupled/biweekly/bimonthly/semiannual/triennial/multiplied/\u2030/pct/ppm",
  "probe: verify('Rents in the capital are doubling under the new rules [1].',['Rents in the capital are nearly doubling under the new rules.']) -> quoted=False; same for 'possibly halving'->'halving', 'Rents are about doubling'->'Rents are doubling' (function word skipped), 'Rents barely rose'->'Rents rose', 'The fee is rarely waived'->'The fee is waived'",
  "git show ca622bc: _in_order is a plain subsequence test; _QUANTITY gains \\w+fold|decades?|couples?; LINK_PATTERN TLD is (?:[a-z]{2,24}|[A-Z]{2,24})",
  "git show f370064 uri_web/untrusted.py: adds _TLDS/_IDN_TLDS lists and keeps the 'rose.The' carve-out; uri_web/synthesize.py: _excerpt with gap_ok relying on states_quantity, plus more _QUANTITY words"
 ],
 "proposed_fix": "Make both checks fail closed and keep the lists as an extra check only. (A) untrusted._is_domain: any ASCII 'label<dot>tld' with a 2+ letter alphabetic TLD is a link, in any case. Remove the case/_TLDS/hyphen heuristics. A missing space after a full stop ('rose.The') then counts as a link: verify/extractive drop or skip that sentence and the surface masks it. That only costs precision, never safety. Rewrite the precision tests at test_w1_r2_review_regressions.py:43-48 and test_w1_r16_review_regressions.py:47 so that 'rose.The', 'so.Then' and 'rose.\u00c9t\u00e9' are expected to be flagged, keeping the real non-link cases ('e.g.', 'U.S.', '4.5%', 'a.m.', 'Ph.D', CJK '\u3002'). Add spaced defangs to _DOT: \\s*\\[\\s*\\.\\s*\\]\\s*, \\s*\\(\\s*\\.\\s*\\)\\s*, \\s+dot\\s+ when followed by an alphabetic TLD. Add a phone/contact pattern (\\+?\\d[\\d\\s().-]{6,}\\d with \u22658 digits). Because surface.clean masks one whitespace-separated token at a time, it must also mask the spaced forms over the whole matched span, not only within one token. Self-contained regression tests: 'Refundsportal.Cash', 'refundsportal.Lol', 'refundsportal.CaSh', 'Refundsportal.Exchange', 'Refundsportal.Deals', 'refundsportal [.] com', 'refundsportal dot com', '1800 555 0199', each checked through has_link_or_contact, verify, extractive and build_surface+require_valid. (B) synthesize._excerpt: a non-quoted Brain sentence is shown only if its full token sequence, function words included, is a contiguous run of the supporting source sentence's tokens (MAX_GAP_WORDS=0 and no skipped function words). Otherwise quote_instead(). Do not call states_quantity inside gap_ok. Keep _QUANTITY only as the upfront 'always quote' check, and optionally add doubling/halving/-tupl(ed|ing)/multiplied/bi-?weekly/bi-?monthly/semi-?annual/tri-?ennial/\u2030/pct/ppm. Regression tests: the five R3-02 pairs plus 'about doubling', 'barely rose' and 'rarely waived' must give quoted=True (the source sentence) or be dropped, never quoted=False with the shortened text.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit f370064354ba678ec5fed956a709cd0e7626c269.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on f370064354ba678ec5fed956a709cd0e7626c269 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_web/**, uri_assist/**, tests/web/**, tests/assist/**, uri_ui/lib/living/**, uri_ui/test/living/**, docs/assist/**, scripts/run_uri_integrated_worker.py.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)
- Regression proof: the driver copies ONLY the files you list in regression_tests into a clean checkout of the pre-repair commit and runs them there; new fixture/helper files are NOT copied. Make each regression test self-contained (embed fixture HTML/JS in the test file and write it to tmp_path at run time). A test that is skipped on the pre-repair commit counts as NOT failing, so it must not skip for a missing fixture.
- graphify: do NOT run `graphify update` (or any graphify command that writes) in this working tree, and do not delete or edit anything under graphify-out/: those files are tracked and outside the permitted paths, so the change would be refused. The repository rule 'run graphify update after modifying code' is satisfied by the coordinator, who rebuilds the graph outside the repository. For code navigation use read-only queries: `graphify query "..." --graph /home/user/uri-wt/graphs/W1-A0/graphify-out/graph.json` (also `path`, `explain`).

Findings (from the reviewer, verbatim):
[
 {
  "id": "R3-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R2-01 repair still incomplete: title-case or mixed-case real gTLDs missing from the hard-coded _TLDS list pass the link detector, verify(), the extractive path and the research surface",
  "files": [
   "uri_web/untrusted.py:98",
   "uri_web/untrusted.py:101",
   "uri_web/untrusted.py:55",
   "uri_web/surface.py:42"
  ],
  "evidence": "has_link_or_contact() is False and surface.clean() leaves the text unchanged for: 'refundsportal.Cash', 'refundsportal.Lol', 'refundsportal.CaSh', 'Refundsportal.Exchange', 'Refundsportal.Deals' (all real registrable gTLDs). With the source 'Claim your energy rebate refund at Refundsportal.Cash before the deadline.': extractive() picks the sentence; verify('... at Refundsportal.Cash before the deadline [1].', [src]) keeps it with dropped=[]; build_surface() output contains 'Refundsportal.Cash'. _is_domain only accepts an ASCII TLD that is all-lower, all-upper, on the ~200-entry _TLDS list, followed by '/', or on a host with a hyphen or digit. Also not detected: 'refundsportal [.] com', 'refundsportal dot com', and phone numbers ('1800 555 0199').",
  "suggested_fix": "Do not decide a host by a TLD allow-list: treat any label.label form with an alphabetic TLD of 2+ letters as a link unless the first letter after the dot is upper case AND the preceding character ends a sentence-like token with no other host signals (or use the full IANA TLD list, case-insensitive). Add spaced-defang forms and phone-number contacts, with regression cases."
 },
 {
  "id": "R3-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "R2-02 repair incomplete: _excerpt lets a claim drop a qualifier next to an undetected quantity word (doubling, halving, quintupled, biweekly), so a changed quantity is shown in the Brain's words",
  "files": [
   "uri_web/synthesize.py:72",
   "uri_web/synthesize.py:138",
   "uri_web/synthesize.py:154",
   "uri_web/synthesize.py:244"
  ],
  "evidence": "states_quantity() is False for 'doubling', 'halving', 'tripling', 'quintupled', 'sextupled', 'biweekly', 'bimonthly', 'semiannual', 'triennial', 'multiplied', '\u2030', 'pct', 'ppm'. verify('Rents in the capital are doubling under the new rules [1].', ['Rents in the capital are nearly doubling under the new rules.']) keeps the claim unquoted (quoted=False). It is the same for 'possibly halving' -> 'halving', 'almost quintupled' -> 'quintupled', 'barely sextupled' -> 'sextupled' and 'roughly biweekly' -> 'biweekly'. The gap rule (MAX_GAP_WORDS=2) allows skipping the qualifier because the skipped word is not a quantity.",
  "suggested_fix": "Make D7 not depend on the word list: either allow no skipped content word at all (claim = contiguous run of source tokens apart from function words), or quote whenever any source word is skipped; add the listed forms and -ing/-ed forms of multiplicatives to _QUANTITY as the secondary check."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
