These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "The D17 'stroke and dot-shaped letters' allow-list _STROKES (uri_web/untrusted.py:516-517) is built from raw code points that never occur in the text it is checked against. normalise() applies NFKC first (untrusted.py:255), which maps every Kangxi radical U+2F00-U+2FD5 to its unified ideograph (U+2F00->U+4E00, U+2F01->U+4E28, ...). So the Kangxi range in _STROKES can never match: all 214 code points are NFKC-unstable and 211 of their normalised forms are absent from the set. The CJK Strokes range U+31C0-U+31E3 is category So, not a letter, so it never forms part of a word either. Only about 11 entries can match (\u4e36\u4e3f\u4e40\u4e41\u4e5a\u4e85\u119e\u11a2\u30fb\uff65\u3006\u3007), and the basic single-stroke radicals \u4e00 U+4E00, \u4e28 U+4E28, \u4e59 U+4E59 (and \u4e8c, \u4ea0, ...) are missing. _separator_word (line 549: len(letters)==1 or letters <= _STROKES) therefore returns False for '\u4e28\u4e36', '\u4e00\u4e36', '\u4e36\u4e00', '\u4e59\u4e36', '\u2f01\u2f02', '\u2f00\u2f02'. The walk at line 562 stops there and takes the word as the name; the gap is plain prose and 'shop' is not core, so the match is dropped at line 573, and the link passes has_link_or_contact, mask_links, verify, extractive, the surface and the A2UI validator.",
 "why_earlier_repairs_failed": "Repairs 1-7 (ca622bc0..7b1252f7) date from rounds R1-R9 and never touch _separator_word or _STROKES. The R13 repairs were coordinator commits. 842ad64d used the rule 'foreign word with <= _MAX_FOREIGN (2) distinct letters is a separator', which would have caught '\u4e28\u4e36'. da10d0b8 (owner loosening) replaced it with the _STROKES allow-list, written as raw Unicode block ranges without accounting for the NFKC/letter-category canonicalisation applied by normalise()/_words(). Its regression test (tests/web/test_w1_closure_r13_review_regressions.py LINKS) only replays the reviewer's literal strings (\u4e36\u4e3f, \u318d\u11a2, \u0298\u0298, \u01c3\u01c3), whose characters happen to be among the ~11 live members, so the 31 tests pass while the class stays open. The same pattern as R11->R12->R13: each patch matched the reviewer's specific strings instead of the rule.",
 "evidence": [
  "uri_web/untrusted.py:255 normalise() applies unicodedata.normalize('NFKC') before any check",
  "uri_web/untrusted.py:516-517 _STROKES includes range(0x2F00,0x2FD6) (all 214 NFKC-unstable; normalised forms such as \u4e00\u4e28\u4e59\u4e8c\u4ea0\u4eba missing) and range(0x31C0,0x31E4) (category So, never in a word); probe: 263 entries, 47 NFKC-stable, 36 of those non-letters",
  "uri_web/untrusted.py:549 return (len(letters) == 1 or letters <= _STROKES) and not _bracketed(...) -> False for '\u4e28\u4e36' (probe: _separator_word list [False, False, False, False] for words refunds/portal/\u4e28\u4e36/shop)",
  "uri_web/untrusted.py:562 walk stops at the non-separator foreign word and takes it as the name",
  "uri_web/untrusted.py:573 prose gap + non-core 'shop' -> continue (match dropped)",
  "probe /tmp/d6/p.py at da10d0b8: has_link_or_contact False for 'refunds-portal \u4e28\u4e36 shop/claim', '\u4e00\u4e36', '\u2f01\u2f02', '\u2f00\u2f02', '\u4e36\u4e00', '\u4e59\u4e36', '\u4e8c\u4e36', '\u4ea0\u4e36'; True for R13 forms \u4e36\u4e3f, \u318d\u11a2, \u0298\u0298, '~ \u0298\u0298', '\u043f\u0440\u0438\u043c\u0435\u0440 \u0298\u0298' and for \u4e00\u4e00, \u4e36\u4e36",
  "tests/web/test_w1_closure_r13_review_regressions.py:22 LINKS only lists reviewer literals; 31 passed at da10d0b8",
  "git show da10d0b8 -- uri_web/untrusted.py: replaced `len(set(w[2].casefold())) <= _MAX_FOREIGN` with the _STROKES allow-list"
 ],
 "proposed_fix": "Build _STROKES in canonical form: frozenset(normalise(ch) for ch in <listed chars> + Kangxi U+2F00-U+2FD5 + CJK Radicals Supplement U+2E80-U+2EF3), keeping only single-letter results (and the '\u119e' NFKC target of '\u318d'). Explicitly add the unified single- and few-stroke radicals \u4e00 U+4E00, \u4e28 U+4E28, \u4e59 U+4E59, \u4e85 U+4E85, \u4e5a, \u4e8c U+4E8C, \u4ea0 U+4EA0. Drop the non-letter U+31C0 range (it already acts as non-letter gap). Add a module-level assertion or test that every member satisfies normalise(c)==c and _letter(c). Add a self-contained regression test that checks every 2-letter combination of the stroke set (incl. Kangxi spellings) through has_link_or_contact, mask_links, SY.verify, SY.extractive, build_surface + require_valid, with controls '\u4e2d\u56fd' (owner-accepted residual) and 'Tokyo \u6771\u4eac is big' (must stay readable).",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit da10d0b84cbd80f60be930295a01baed47b31110.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on da10d0b84cbd80f60be930295a01baed47b31110 and PASSES after
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
  "id": "R14-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R13-01 repair incomplete: two distinct CJK stroke/dot radicals between name and TLD ('\u4e28\u4e36', '\u4e00\u4e36', '\u4e36\u4e00', '\u4e59\u4e36', Kangxi '\u2f01\u2f02', '\u2f00\u2f02') are read as the name, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D17)",
  "files": [
   "uri_web/untrusted.py:516",
   "uri_web/untrusted.py:255",
   "uri_web/untrusted.py:548",
   "uri_web/untrusted.py:556"
  ],
  "evidence": "_STROKES lists the Kangxi Radicals block U+2F00-U+2FD5, but check text is NFKC-normalised first (untrusted.py:255), mapping every Kangxi radical to its unified ideograph (U+2F01->U+4E28, U+2F00->U+4E00), so that range never matches; the unified single-stroke radicals \u4e00 U+4E00, \u4e28 U+4E28, \u4e59 U+4E59 are absent from _STROKES. _separator_word therefore returns False for '\u4e28\u4e36' (letters not single, not subset of _STROKES) and the word becomes the name. Probe /tmp/uri_review_R14/test_r14_probe.py (same harness as tests/web/test_w1_closure_r13_review_regressions.py) with SENT='Claim your energy rebate refund at {} before the deadline.' and links 'refunds-portal \u4e28\u4e36 shop/claim', 'refunds-portal \u4e00\u4e36 shop/claim', 'refunds-portal \u2f01\u2f02 shop/claim', 'refunds-portal \u2f00\u2f02 shop/claim', 'refunds-portal \u4e36\u4e00 shop/claim', 'refunds-portal \u4e59\u4e36 shop': 18/18 fail - has_link_or_contact False, mask_links keeps 'refunds-portal', verify() keeps the cited claim, build_surface output contains 'refunds-portal \u4e59\u4e36 shop' and require_valid accepts it. These are stroke and dot radicals, which D17 names as separators; they are neither a bracketed gloss nor a real short foreign word (the only owner-accepted residuals).",
  "suggested_fix": "Build _STROKES from the NFKC forms of U+2F00-U+2FD5 (or normalise the set the same way as the text) and add \u4e00 U+4E00, \u4e28 U+4E28, \u4e59 U+4E59, \u4e85 U+4E85 explicitly; add a self-contained regression test covering the forms above at every layer."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
