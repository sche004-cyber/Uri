You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 0fcc39d4bf06655b0c45b05b65be46b70a07248a.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 0fcc39d4bf06655b0c45b05b65be46b70a07248a and PASSES after
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
  "id": "R28-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R27-01 repair incomplete: Latin look-alike letters whose Unicode name has no A-Z letter (U+0251 LATIN SMALL LETTER ALPHA '\u0251', U+0269 LATIN SMALL LETTER IOTA '\u0269', U+0196 '\u0196') are not folded, so 'refunds-portal b\u0269z/claim' (core domain, plain space), 'refunds-portal \u0269o/claim', 'refunds-portal ~ c\u0251sh', '~ \u0251pp' and '~ \u0269nfo' pass has_link_or_contact and mask_links; the probed '~ c\u0251sh', 'c\u0251sh/claim', '~ \u0269nfo', '~ \u0251pp' and '\u0251pp/claim' forms also pass verify(), extractive() and the research surface (W1-AC12/AC15, D16)",
  "files": [
   "uri_web/untrusted.py:499",
   "uri_web/untrusted.py:506",
   "uri_web/untrusted.py:517",
   "uri_web/untrusted.py:544",
   "uri_web/surface.py:38",
   "uri_web/synthesize.py:238",
   "uri_web/synthesize.py:341"
  ],
  "evidence": "has_link_or_contact('Claim at refunds-portal b\\u0269z/claim now') -> False, while 'refunds-portal biz/claim' -> True. False also for 'refunds-portal \\u0269o/claim', 'refunds-portal ~ c\\u0251sh', '~ \\u0251pp', '~ \\u0269nfo'; mask_links leaves all five unchanged. For the probed '~ c\\u0251sh', 'c\\u0251sh/claim', '~ \\u0269nfo', '~ \\u0251pp' and '\\u0251pp/claim' forms, verify('Claim your energy rebate refund at refunds-portal ~ c\\u0251sh before the deadline [1].', [src]) keeps the claim with its citation, extractive() keeps the sentence, and surface.clean() returns it unmasked. _LATIN_NAME only maps names ending in a single letter A-Z with an optional 'WITH ...' tail; 135 Latin letters below U+2C00 have no mapping (ALPHA, IOTA, GAMMA, AE, OE, ETH, TONE SIX ...), and _latin_fold returns '' for the whole word when any letter is unmapped.",
  "suggested_fix": "Fold ending candidates through a confusables skeleton for Latin-script words too (as already done for non-Latin scripts), plus an explicit map for Latin letters named after Greek letters (alpha->a, iota->i, ...), and add regression cases for 'b\u0269z', '\u0269o', 'c\u0251sh', '\u0251pp'."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
