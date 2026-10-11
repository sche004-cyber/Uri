These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "The link detector in uri_web/untrusted.py is still a list of known separator shapes, not a rule. _BARE (untrusted.py:78) matches a bare domain only when the labels are joined by _DOT (untrusted.py:76), and _DOT accepts only the 14 characters in _DOTCH (untrusted.py:75), certain bracket pairs and a spaced 'dot'. Any other separator a reader would take as a dot makes has_link_or_contact return False. Probes at HEAD 806dcd12 found: 'refunds..com/claim', 'refunds\u2026com', U+060C, U+0964, U+0589, U+06D4, U+2E31, U+0701, U+16EB, U+1362, U+0F0B, U+A789, U+02D9, ',', ':', ' d0t ', '_dot_', '-dot-', 'refunds-portal.c om'. Each of these is kept unquoted by verify() (synthesize.py:238), picked by extractive() (synthesize.py:318), shown by build_surface via clean/mask_links (surface.py:38) and accepted by require_valid. The literal R5-01 strings ('_refunds-portal.com_' and the others) are fixed at HEAD by 29771992's (?<![^\\W_])...(?![^\\W_]) lookarounds. What recurs is the class (R1-01/R5-01/R6-01): a link next to a separator the list does not cover. A second, smaller path: the sentence splitter (evaluate.py:38 _SENT) splits 'refunds-portal . Com' / 'refunds-portal. Com/claim' into two sentences that are each link-free, and verify/extractive keep the halves.",
 "why_earlier_repairs_failed": "Each repair added the shapes the reviewer had just reported and wrote regression tests for those exact strings. ca622bc0 added [.]/(.)/[dot]. f3700643 added U+3002/U+FF0E/U+FF61. 462be42c added spaced bracket defangs. f5a5b8ec added the ACE 'xn--' top-level label. 29771992 (the R5-01 repair, not in the listed repairs) changed only the '_'/'-' lookarounds. 806dcd12 (D13, 'mask any dot-joined word') turned the owner's rule into another fixed set, _DOTCH, which leaves out most Unicode full stops and dot-like marks (Po/Sk), repeated dots and the ellipsis, ASCII ',' and ':', and spelled forms like 'd0t', '_dot_' and '-dot-'. The tests (e.g. tests/web/test_w1_closure_r5_review_regressions.py:23 WRAPPED) list fixed strings, so the next unlisted separator always passes. None of the repairs looked at the splitter running before the per-sentence check.",
 "evidence": [
  "uri_web/untrusted.py:75 _DOTCH lists 14 dot characters; U+060C/U+0964/U+0589/U+06D4/U+2E31/U+0701/U+16EB/U+1362/U+0F0B/U+A789/U+02D9, ',' and ':' are missing",
  "uri_web/untrusted.py:76 _DOT accepts exactly one _DOTCH character (so '..' and NFKC('\u2026')='...' fail) or brackets/spaced 'dot' (so 'd0t', '_dot_' and '-dot-' fail)",
  "uri_web/untrusted.py:78 _BARE requires host+_DOT+tld, so every unlisted separator gives no match",
  "uri_web/untrusted.py:65-74 the R5-01 and D13 comments describe the fail-closed intent, which the code does not deliver",
  "uri_web/synthesize.py:238 verify uses has_link_or_contact(body); probe: 'Claim your energy rebate refund at refunds-portal\u060ccom before the deadline [1].' is kept as a claim",
  "uri_web/synthesize.py:318 extractive uses the same detector and picks the link sentence",
  "uri_web/surface.py:38 clean -> mask_links leaves it; probe /tmp/d5/p3.py: build_surface plus require_valid pass and the dump contains 'refunds-portal\u060ccom', 'refunds..com/claim', 'refunds-portal d0t com', 'refunds-portal,com/claim', 'refunds-portal:com', 'refunds-portal_dot_com', 'refunds-portal\u2e31com'",
  "uri_web/evaluate.py:38 _SENT splits at '. ' + capital, so for 'refunds-portal . Com' verify keeps 'Com before the deadline .' and extractive keeps '... at refunds-portal .'",
  "/tmp/d5/p1.py: all literal R5-01 strings now return True (fixed by 29771992)",
  "git show 806dcd12/29771992/f5a5b8ec/462be42c/f3700643/ca622bc0 -- uri_web/untrusted.py: each diff extends _DOT/_BARE by the reported shapes only",
  "tests/web/test_w1_closure_r5_review_regressions.py:23 regression tests are fixed string lists"
 ],
 "proposed_fix": "In untrusted.py, replace the enumerated _DOTCH/_DOT with a category-based separator. Inside a whitespace-separated token (on the normalised text and the skeleton), any run of characters whose Unicode category is P* or S* (Sk included) counts as a dot, except a single word-internal '-', \"'\" or '\\u2019', and '/'. So do 'dot'/'d0t' in any wrapper or spacing ('_dot_', '-dot-', '{dot}', ' d0t '), and an optional space on either side of a dot-like mark. The match counts when the right-hand label is 2-63 letters or an ACE label. Keep the existing precision-only exceptions (a full stop, comma or colon plus space plus capitalised word; 'rose.The'; the CJK '\u3002' break; abbreviations). Also run has_link_or_contact on the whole unsplit source paragraph and on the joined answer text, and quote or drop any sentence next to a LINK_OR_CONTACT hit, so splitter-split links ('portal . Com') cannot survive in halves. Replace string-list regressions with generated ones: every code point in categories Po/Pd/Ps/Pe/Sk/Sm placed between 'refunds-portal' and 'com' (and doubled), through has_link_or_contact, mask_links, verify, extractive, build_surface and require_valid, with tests embedded in the test file.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 806dcd12816b3944f78324f06aaf3aa366cec96a.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 806dcd12816b3944f78324f06aaf3aa366cec96a and PASSES after
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
  "blocking": true,
  "category": "security",
  "evidence": "Probe /tmp/uri_review_R6/probe_e2e.py: src = 'Claim your energy rebate refund at refunds-portal .com/claim before the deadline. Energy rebate refunds take two weeks.'; U.has_link_or_contact -> False; SY.verify(<same sentence> [1], [src]).claims keeps it unquoted; SY.extractive('energy rebate refund deadline',[src]) picks it; build_surface(...) passes require_valid and the dump contains 'refunds-portal .com/claim'. The same holds for 'refunds-portal\u00b7com', 'refunds-portal\u30fbcom', 'refunds-portal\u2219com', 'refunds-portal{.}com'. _DOT accepts '\\s+\\.\\s+' (spaces on both sides) but not a space on one side only, and accepts only . U+3002 U+FF0E U+FF61 as dot characters.",
  "files": [
   "uri_web/untrusted.py:69",
   "uri_web/untrusted.py:71",
   "uri_web/untrusted.py:168",
   "uri_web/synthesize.py:240",
   "uri_web/synthesize.py:320",
   "uri_web/surface.py:37"
  ],
  "id": "R6-01",
  "owner_decision": false,
  "severity": "HIGH",
  "suggested_fix": "Treat '\\s*\\.\\s*' between label-like runs when the right side is a TLD-shaped label followed by a non-letter (or '/'), and add the dot-like punctuation (U+00B7, U+0387, U+2027, U+2219, U+22C5, U+30FB, U+2E3C, braces/angle-bracket defangs) to _DOT; add regressions for each through verify, extractive, build_surface and require_valid.",
  "title": "R1-01 class still open: a one-sided spaced dot ('refunds-portal .com/claim') or a dot-like separator (U+00B7, U+30FB, U+2219, U+22C5, U+2027, '{.}', '<.>') passes has_link_or_contact, verify(), extractive(), the research surface and the A2UI validator (W1-AC15/AC12)"
 },
 {
  "blocking": true,
  "category": "code",
  "evidence": "Probe /tmp/uri_review_R6/probe_d7.py: SY.verify('A quintet of firms control the regional market [1].', ['Analysts said that, at most, a quintet of firms control the regional market.']) -> one claim, quoted=False, no drops. The same for 'By some estimates, a plurality of voters backed the measure.' and the trailing forms 'A quorum of members attended the session, or nearly so.' and 'A plurality of voters backed the measure, at least initially.' (all quoted=False).",
  "files": [
   "uri_web/synthesize.py:142",
   "uri_web/synthesize.py:185",
   "uri_web/synthesize.py:196",
   "uri_web/synthesize.py:207"
  ],
  "id": "R6-02",
  "owner_decision": false,
  "severity": "MEDIUM",
  "suggested_fix": "Fail closed at the edges: a claim that does not start at the sentence start (after determiners only) or end at the sentence end should be quoted, or allow a clause edge only when the dropped clause holds no qualifier/hedge (an allow-list, as for gap_ok), not just any comma.",
  "title": "R5-02 repair incomplete: lead_ok/tail_ok treat a comma as a safe edge, so a claim drops a qualifier set off by commas ('that, at most, a quintet of firms...') before an undetected quantity word and is shown unquoted (D7)"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
