These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "uri_web/untrusted.py _words() counts any category-M character as a letter (_letter, line 449-450), so a run of marks with no base letter after a space becomes a 'word' tagged with the marks' own script. Commit 68feb3e7 changed _separator_word (line 580-582) to classify base=_bare(w[2]) and treat the word as a separator only if base is empty or one letter. _bare (line 472-476) removes only marks whose Unicode name starts with 'COMBINING', so script marks (U+093C DEVANAGARI SIGN NUKTA, U+0901/0902, U+0F39/0F37/0F35, U+0650/065C/0655, U+0E31/0E34/0E47, U+0C3C/0C00/0C01) stay in base. base then has 3 distinct characters (more than _MAX_FOREIGN=2), its script differs from the TLD's and it is not in _STROKES, so the mark run is taken as the NAME. The gap before 'shop' is a plain space and 'shop' is not in _CORE, so line 614 drops the match. has_link_or_contact returns False and mask_links, verify, extractive, the surface and the A2UI check all let it through.",
 "why_earlier_repairs_failed": "eb4d676d (R19-01) added a correct, script-agnostic rule: all(unicodedata.category(ch)[0]=='M' for ch in w[2]) returns True. Its tests (tests/web/test_w1_closure_r19_review_regressions.py:16-17) only used marks named 'COMBINING ...' (U+0323/0307/0308/0304), copied from the reviewer's probe. 68feb3e7 (R20-01) replaced that rule with `not base` after _bare(), which narrowed 'all category M' to 'all named COMBINING'. The R19 tests still passed, so the regression was not caught. Both repairs targeted the reviewer's exact characters, not the cause: _words makes words out of marks that have no base letter. The earlier repairs ca622bc0..fe77015a predate the mark-only word case.",
 "evidence": [
  "uri_web/untrusted.py:449-450 _letter treats category M as a letter, so a mark run becomes a word",
  "uri_web/untrusted.py:472-476 _bare strips only marks whose name starts with 'COMBINING'",
  "uri_web/untrusted.py:580-582 base=_bare(w[2]); `if not base or len(base)==1` replaced eb4d676d's all-category-M test (git show 68feb3e7)",
  "uri_web/untrusted.py:589 len(set(base.casefold())) <= _MAX_FOREIGN is False for 3 distinct script marks, so the run is taken as the name",
  "uri_web/untrusted.py:611-614 plain-space gap and non-_CORE 'shop' -> continue (no span)",
  "probe at 68feb3e7: has_link_or_contact(S.format('refunds-portal \\u093c\\u0901\\u0902 shop'))==False; same for \\u0f39\\u0f37\\u0f35, \\u0650\\u065c\\u0655, \\u0e31\\u0e34\\u0e47, \\u0c3c\\u0c00\\u0c01 and '\\u093c\\u0901\\u0902\\u0903 cash'; the COMBINING-named '\\u0323\\u0307\\u0308 shop' is True",
  "probe: _words gives ('\\u093c\\u0901\\u0902','DEVANAGARI') and _bare leaves it unchanged; for '\\u0323\\u0307\\u0308' _bare gives ''",
  "tests/web/test_w1_closure_r19_review_regressions.py:16-17 LINKS cover only U+0323/0307/0308/0304 (COMBINING-named)",
  "git show eb4d676d: `if _single(w) or all(unicodedata.category(ch)[0] == \"M\" for ch in w[2])`; git show 68feb3e7 removes it in favour of _bare"
 ],
 "proposed_fix": "In _separator_word, restore the script-agnostic rule before any stripping: `if all(unicodedata.category(ch)[0] == 'M' for ch in w[2]): return True`, then apply base=_bare(w[2]) for words that have a base letter. More robust: in _words, treat category-M characters that do not follow a base letter as gap characters, so mark-only words are never produced. Add regression cases (as \\u escapes, self-contained): 'refunds-portal \\u093c\\u0901\\u0902 shop', '\\u0f39\\u0f37\\u0f35 shop', '\\u0650\\u065c\\u0655 shop', '\\u0e31\\u0e34\\u0e47 shop', '\\u0c3c\\u0c00\\u0c01 shop', '\\u093c\\u0901\\u0902\\u0903 cash'. Assert has_link_or_contact is True and mask_links removes 'refunds-portal'. Keep the R19 and R20 cases passing.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 68feb3e70e9ee1ec019f8d543d552b5b2d95d116.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 68feb3e70e9ee1ec019f8d543d552b5b2d95d116 and PASSES after
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
  "id": "R21-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R20-01 repair regressed R19-01: a run of three or more non-'COMBINING'-named marks on a space (Devanagari nukta/candrabindu/anusvara, Tibetan, Arabic, Thai, Telugu signs) between name and a non-core TLD is read as the name, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D13/D16)",
  "files": [
   "uri_web/untrusted.py:472",
   "uri_web/untrusted.py:580",
   "uri_web/untrusted.py:581",
   "uri_web/untrusted.py:589",
   "uri_web/surface.py:38",
   "uri_web/synthesize.py"
  ],
  "evidence": "SENT='Claim your energy rebate refund at {} before the deadline.'. For 'refunds-portal \\u093c\\u0901\\u0902 shop', 'refunds-portal \\u0f39\\u0f37\\u0f35 shop', 'refunds-portal \\u0650\\u065c\\u0655 shop', 'refunds-portal \\u0e31\\u0e34\\u0e47 shop', 'refunds-portal \\u0c3c\\u0c00\\u0c01 shop': at 68feb3e7 U.has_link_or_contact -> False, U.mask_links leaves the text unchanged, SY.verify(sentence+' [1].', [src]) keeps the claim, SY.extractive('energy rebate refund deadline', [src]) returns the sentence, and surface.build_surface shows it unmasked in the answer and source title (Surface built without validation error). At eb4d676d all five are detected and masked (True / claim dropped / extractive empty / surface masked). Cause: _separator_word now computes base=_bare(w[2]), and _bare strips only marks whose Unicode name starts with 'COMBINING', so these script marks remain, base has 3 distinct characters, and the old 'all category M -> separator' rule (R19-01) no longer fires.",
  "suggested_fix": "In _separator_word, keep the R19-01 rule before stripping: if every character of w[2] is category M, return True; then use _bare for words that have a base letter. Add the five cases above to the regression tests."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
