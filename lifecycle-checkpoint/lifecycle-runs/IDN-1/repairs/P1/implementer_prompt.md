You are the IMPLEMENTER repairing URI milestone IDN-1 at commit 21ad94099cbaaec5dbd82b80847be1b8c6c983b2.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 21ad94099cbaaec5dbd82b80847be1b8c6c983b2 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_web/netpolicy.py, uri_web/pipeline.py, uri_web/search.py, uri_web/surface.py, uri_web/untrusted.py, uri_web/safe_fetch.py, uri_web/feeds.py, uri_web/social.py, tests/web/**, docs/web/**, docs/governance/OWNER_DECISIONS_20261011.md.
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
  "id": "R1-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "KELVIN SIGN (U+212A) bypasses HOST_NON_ENGLISH because non-ASCII is tested after urlsplit lower-cases the host",
  "files": [
   "uri_web/netpolicy.py:111",
   "uri_web/netpolicy.py:131",
   "uri_web/netpolicy.py:151"
  ],
  "evidence": "parts.hostname lower-cases '\\u212aelvin.com' to ASCII 'kelvin.com', so non_ascii=False. U+212A is the only code point whose lower() is ASCII. check_url('http://\\u212aelvin.com/') returns OK host=kelvin.com. In ResearchJob with a mock fetcher, the user URL, the Tavily search hit and a 302 Location to it all resolved and contacted kelvin.com; status COMPLETED_WITH_RESULT, blocked_non_english=0, no note. Plan Scope says 'a host name with any character outside ASCII ... is refused'. Practical impact is low (the contacted host and the displayed label are the genuine ASCII kelvin.com), but the review focus names Unicode that maps to ASCII as a blocking bypass.",
  "suggested_fix": "Compute non_ascii from the raw authority, e.g. `non_ascii = not parts.netloc.isascii()` (or from urlsplit(url).netloc before lower-casing), and add http://\\u212aelvin.com/ to the IDN_URLS tests."
 },
 {
  "id": "R1-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "blocked_non_english counts hits and refused fetches, not sites: one blocked site is double counted",
  "files": [
   "uri_web/search.py:117",
   "uri_web/search.py:123",
   "uri_web/pipeline.py:152",
   "uri_web/pipeline.py:179"
  ],
  "evidence": "Probes (mock fetcher and providers), each with a single blocked site, gave blocked_non_english=2 and the note 'Blocked 2 sites: ...': (a) one provider returning b\u00fccher.de/1 and b\u00fccher.de/2; (b) provider A returning only \u0440\u0430\u0443\u0440\u0430l.com (NO_RESULTS, so the loop continues) and provider B returning the same \u0440\u0430\u0443\u0440\u0430l.com; (c) user URL http://b\u00fccher.de/ plus the same URL as a search hit; (d) two user URLs hop1/hop2.example both redirecting to b\u00fccher.de. The review criterion requires 'no double counting of one site'.",
  "suggested_fix": "Have _hit_refusal / attempts report the refused host (e.g. urlsplit(url).hostname), collect the hosts in a job-level set across search providers, user URLs, feeds and redirects, and set blocked_non_english = len(set). Add regression tests for cases (a)-(d)."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
