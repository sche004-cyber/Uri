These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "uri_web/untrusted.py builds bare-domain detection as a positive allow-list of exact separator spellings: _DOT (line 69-70) accepts only '.', U+3002/U+FF0E/U+FF61, bracket/paren-wrapped '.'/'dot', and '\\s+dot\\s+' / '\\s+\\.\\s+' (whitespace required on BOTH sides), and _BARE (line 71) additionally requires exact label shapes ([^\\W_][\\w-]{0,62}) and specific boundary classes. Any separator spelling not enumerated (one-sided space 'portal .com' / 'portal. com', U+00B7, U+0387, U+2027, U+2219, U+22C5, U+30FB, U+2E3C, '{.}', '<.>', '{dot}', '..', '\\.', or a >63-char label) is not a separator, so the text is not a link. has_link_or_contact/mask_links fail open, and every caller (synthesize.verify:240, extractive:300/320, surface.clean:38, evaluate:287) trusts that single detector. R3-01 made only the TLD axis fail closed; the separator axis and (until R5) the boundary axis kept matching fixed lists. R5-01's specific forms are fixed at HEAD; the same class (R1-01) is still reproducible (R6-01).",
 "why_earlier_repairs_failed": "Each repair widened the regex by exactly the reviewer's examples and added regression tests that enumerate only those literals: ca622bc0 added [.] (.) [dot] (dot) (ASCII only); f3700643 added NFKC + three CJK full stops and introduced _BARE with (?<![\\w-])/(?![\\w-]) boundaries (the R5-01 bug); 462be42c added spaced defangs but wrote '\\s+\\.\\s+' symmetric (test only has 'refundsportal . com'), leaving one-sided spacing open (R6-01); f5a5b8ec added only the xn-- TLD form; 29771992 changed only the boundary checks to (?<![^\\W_])/(?![^\\W_]) and tested only the reviewer's WRAPPED list. No repair replaced the enumeration with a fail-closed rule or tested a generated family of separators, so each round's suite passed while the next variant stayed open.",
 "evidence": [
  "uri_web/untrusted.py:69-70 _DOT enumerates separators; '\\s+\\.\\s+' requires spaces on both sides; no U+00B7/U+0387/U+2027/U+2219/U+22C5/U+30FB/U+2E3C/{.}/<.>",
  "uri_web/untrusted.py:71 _BARE: label capped at [\\w-]{0,62} (a 70-char label + '.com' is not detected); boundaries fixed by 29771992",
  "uri_web/untrusted.py:51 R3-01 comment: fail-closed applied to the TLD only",
  "uri_web/synthesize.py:240,300,320 and uri_web/surface.py:38 depend solely on U.has_link_or_contact/U.mask_links",
  "git show 462be42c -- uri_web/untrusted.py: introduced symmetric '\\s+\\.\\s+'",
  "git show 29771992 -- uri_web/untrusted.py: only the lookaround classes changed",
  "tests/web/test_w1_r3_review_regressions.py:28 tests only 'refundsportal . com'; tests/web/test_w1_closure_r5_review_regressions.py:22-25 only the reviewer's wrapped literals",
  "/tmp/diag_D4/p.py at HEAD: all 7 R5-01 strings -> True/masked; 'refunds-portal .com/claim', 'refunds-portal. com', U+00B7, U+30FB, U+2219, U+22C5, U+2027, U+0387, U+2E3C, '{.}', '<.>', '{dot}', '..', '\\\\.', 'a'*70+'.com' -> has_link_or_contact False, mask_links unchanged",
  "/tmp/diag_D4/e2e.py (reviewer R6 probe) at HEAD: verify keeps the sentence, extractive selects it, build_surface passes require_valid with 'refunds-portal' in the dump for '.com' one-sided, '\u00b7', '{.}', '\u30fb', '\u2219'"
 ],
 "proposed_fix": "Make the separator axis fail closed rather than adding more literals: (1) define a dot-like class generated from Unicode data (every char whose unicodedata name contains FULL STOP, DOT, MIDDLE DOT, BULLET, or ONE DOT LEADER, plus '.' U+3002 U+FF0E U+FF61), and accept it optionally wrapped in any bracket pair ([], (), {}, <>) or as the word 'dot', with \\s* (not \\s+) on EITHER side, and runs of them ('..', '\\.'); (2) when whitespace touches the separator, keep the _SENTENCE_WORDS exception (and extend _is_domain so 'word .Then' stays text) but otherwise treat 'label SEP tld' as a link when tld is letters>=2 or ACE and is followed by a non-letter or '/'; (3) remove the {0,62} label cap (use [\\w-]+); (4) in mask_links/has_link_or_contact also test each whitespace token and each pair of adjacent tokens after stripping edge punctuation, so the spaced forms are caught per token too; (5) add a generated regression test that loops over every Unicode code point whose name matches the dot-like set and over {'', ' '} x {'', ' '} spacing x bracket wrappers, asserting has_link_or_contact, mask_links, SY.verify (dropped LINK_OR_CONTACT), SY.extractive (not selected) and build_surface+require_valid (no host in dump), self-contained in one test file.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 29771992f57ff470035f044c55e2c6689e9d3d6d.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 29771992f57ff470035f044c55e2c6689e9d3d6d and PASSES after
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
  "id": "R6-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R1-01 class still open: a one-sided spaced dot ('refunds-portal .com/claim') or a dot-like separator (U+00B7, U+30FB, U+2219, U+22C5, U+2027, '{.}', '<.>') passes has_link_or_contact, verify(), extractive(), the research surface and the A2UI validator (W1-AC15/AC12)",
  "files": [
   "uri_web/untrusted.py:69",
   "uri_web/untrusted.py:71",
   "uri_web/untrusted.py:168",
   "uri_web/synthesize.py:240",
   "uri_web/synthesize.py:320",
   "uri_web/surface.py:37"
  ],
  "evidence": "Probe /tmp/uri_review_R6/probe_e2e.py: src = 'Claim your energy rebate refund at refunds-portal .com/claim before the deadline. Energy rebate refunds take two weeks.'; U.has_link_or_contact -> False; SY.verify(<same sentence> [1], [src]).claims keeps it unquoted; SY.extractive('energy rebate refund deadline',[src]) picks it; build_surface(...) passes require_valid and the dump contains 'refunds-portal .com/claim'. The same holds for 'refunds-portal\u00b7com', 'refunds-portal\u30fbcom', 'refunds-portal\u2219com', 'refunds-portal{.}com'. _DOT accepts '\\s+\\.\\s+' (spaces on both sides) but not a space on one side only, and accepts only . U+3002 U+FF0E U+FF61 as dot characters.",
  "suggested_fix": "Treat '\\s*\\.\\s*' between label-like runs when the right side is a TLD-shaped label followed by a non-letter (or '/'), and add the dot-like punctuation (U+00B7, U+0387, U+2027, U+2219, U+22C5, U+30FB, U+2E3C, braces/angle-bracket defangs) to _DOT; add regressions for each through verify, extractive, build_surface and require_valid."
 },
 {
  "id": "R6-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "R5-02 repair incomplete: lead_ok/tail_ok treat a comma as a safe edge, so a claim drops a qualifier set off by commas ('that, at most, a quintet of firms...') before an undetected quantity word and is shown unquoted (D7)",
  "files": [
   "uri_web/synthesize.py:142",
   "uri_web/synthesize.py:185",
   "uri_web/synthesize.py:196",
   "uri_web/synthesize.py:207"
  ],
  "evidence": "Probe /tmp/uri_review_R6/probe_d7.py: SY.verify('A quintet of firms control the regional market [1].', ['Analysts said that, at most, a quintet of firms control the regional market.']) -> one claim, quoted=False, no drops. The same for 'By some estimates, a plurality of voters backed the measure.' and the trailing forms 'A quorum of members attended the session, or nearly so.' and 'A plurality of voters backed the measure, at least initially.' (all quoted=False).",
  "suggested_fix": "Fail closed at the edges: a claim that does not start at the sentence start (after determiners only) or end at the sentence end should be quoted, or allow a clause edge only when the dropped clause holds no qualifier/hedge (an allow-list, as for gap_ok), not just any comma."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
