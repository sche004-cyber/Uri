You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 74909458161186edead2642957332ce50655f558.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 74909458161186edead2642957332ce50655f558 and PASSES after
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
  "id": "R26-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R24-01/R25-01 class still open: a listed top-level domain with a diacritic that NFKC composes into a precomposed letter ('c\u0301om' -> '\u0107om', 'o\u0300rg', 's\u0323hop' -> '\u1e63hop', 'sho\u0301p', 'ca\u0301sh', Cyrillic '\u0435\u0301\u0444') is not an ending, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D16)",
  "files": [
   "uri_web/untrusted.py:502",
   "uri_web/untrusted.py:508",
   "uri_web/untrusted.py:476",
   "uri_web/untrusted.py:255",
   "uri_web/untrusted.py:672",
   "uri_web/surface.py:38"
  ],
  "evidence": "normalise() applies NFKC, which composes base+combining mark into a precomposed letter; _tld_match removes only Mn/Me from the composed text, so the accent survives inside the letter. Sentence 'Claim your energy rebate refund at {X} before the deadline.': X='refunds-portal c\\u0323om/claim' -> has_link_or_contact True (no precomposed form exists), but X='refunds-portal c\\u0301om/claim' -> False; mask_links leaves it unchanged; SY.verify(sentence+' [1].', [src]) keeps the claim; SY.extractive('energy rebate refund deadline', [src]) keeps the sentence. Also False/kept: 'refunds-portal o\\u0300rg/claim', 'refunds-portal ~ s\\u0323hop', 'refunds-portal ~ sho\\u0301p', 'refunds-portal ~ ca\\u0301sh', 'refunds-portal ~ \\u0435\\u0301\\u0444'. surface.build_surface with this text in answer/conflict/title builds (Surface validation via uri_a2ui.validate accepts) and contains 'refunds-portal' 3 times. Probes: /tmp/uri_review_R26/p2.py, p3.py. The _tld_match docstring claims combining marks are ignored, which holds only when no precomposed form exists.",
  "suggested_fix": "In _tld_match and _bare, decompose (NFD) each word before removing marks, then recompose or compare against NFC/NFD forms of the list. Also run _ending_spans on the skeleton (mapped back as _all_spans does for _spans). Add self-contained regression tests with the composed forms above."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
