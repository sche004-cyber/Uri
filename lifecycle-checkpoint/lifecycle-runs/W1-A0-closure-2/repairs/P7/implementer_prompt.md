You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 66a4765a3897a1c3c460576645c12da68edc9bd3.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 66a4765a3897a1c3c460576645c12da68edc9bd3 and PASSES after
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
  "id": "R9-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R1-01 link class still open: spaced dot look-alikes U+2027 HYPHENATION POINT ('refunds-portal \u2027 shop'), U+0660/U+06F0 Arabic-Indic zero ('refunds-portal \u0660 com/claim') and U+4E36/U+2F02 dot stroke ('refunds-portal \u4e36 shop') pass has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D13 'with or without spaces')",
  "files": [
   "uri_web/untrusted.py:105",
   "uri_web/untrusted.py:115",
   "uri_web/untrusted.py:342",
   "uri_web/untrusted.py:390",
   "uri_web/untrusted.py:396"
  ],
  "evidence": "Probes /tmp/uri_review_R9/p1.py, p2.py, p5.py on 66a4765: for SENT='Claim your energy rebate refund at {} before the deadline.', has_link_or_contact is False and mask_links leaves the text unchanged for 'refunds-portal \u2027 cash', 'refunds-portal \u2027 cash/claim', 'refunds-portal \u0660 com/claim', 'refunds-portal \u0660 com', 'refunds-portal \u06f0 com', 'refunds-portal \u0966 com'. Also has_link_or_contact('Claim at refunds-portal \u2027 shop today.') is False, and the same holds for \u4e36, \u2f02 and \u0660. SY.verify keeps the cited claim and SY.extractive returns the sentence. build_surface output contains 'portal', and require_valid accepts it. Causes: (a) U+2027's name 'HYPHENATION POINT' does not match _DOT_NAME, so it is not _DOTLIKE; the spaced-both-sides form only matches alternatives that need a dot-like run, and _unusual treats it as COMMON because U+2010-205E is in _ORDINARY. (b) U+0660, U+06F0, U+4E36 and U+0966 are letters or digits of a listed script, so a lone token holds one script family, is alphanumeric and is not unusual, and no neighbour span is added. U+2027 was in R6-01 and U+0660 in R8-01; only the no-space forms were repaired. Not covered by the D15 residual (spelt-out letters or words).",
  "suggested_fix": "Treat U+2027 (and every Po/Sm character in the _ORDINARY ranges that is drawn as a dot: HYPHENATION POINT, CARET INSERTION POINT, DOTTED CROSS, ...) as _DOTLIKE. Treat a whitespace-separated token made of a single non-Latin letter, digit or mark between two Latin words (a digit zero, a dot stroke, an anusvara or nukta on a space) as a separator: span both neighbours, as is already done for tokens with no allowed letter. Add the spaced forms to the regressions."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
