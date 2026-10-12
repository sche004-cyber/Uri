You are the IMPLEMENTER repairing URI milestone GRAPHIFY-LEAK-1 at commit 9ae7c60cd02b3a7be87a465db4170705d28f9d72.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 9ae7c60cd02b3a7be87a465db4170705d28f9d72 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_core/app/server.py, tests/graphify/**, docs/graphify/**.
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
  "category": "test",
  "owner_decision": false,
  "title": "conftest placeholders leak into other tests in the same run (server and uri_core.services stay bound to MagicMock Google modules; credential secret persists)",
  "files": [
   "tests/graphify/conftest.py:36",
   "tests/graphify/conftest.py:40",
   "tests/graphify/conftest.py:41"
  ],
  "evidence": "conftest imports uri_core.app.server while the placeholders are installed, then deletes only google*/googleapiclient*/google_auth_* entries from sys.modules. uri_core.app.server and uri_core.services.gmail_service (etc.) remain imported with MagicMock bindings: a probe test run after tests/graphify sees type(uri_core.services.gmail_service.build) == MagicMock. Repro on this host (Google packages not installed): `pytest tests/test_m31_model_brain_ux.py` -> 1 collection error; `pytest tests/graphify tests/test_m31_model_brain_ux.py` -> 25 passed. Same for test_decision_engine.py (error alone; 60 passed with tests/graphify). tests/graphify sorts before tests/test_* in a plain `pytest tests` run. os.environ.setdefault('URI_EXTERNAL_CREDENTIAL_SECRET', ...) at module level also persists for the session. This contradicts the conftest docstring ('no other test in the same run can see them') and review focus 5.",
  "suggested_fix": "Isolate the placeholder import: snapshot sys.modules before it and, on teardown of tests/graphify (session/module fixture or pytest_unconfigure-scoped hook), remove every module added during the placeholder window (including uri_core.*), or use pytest.importorskip / run the tests in a subprocess. Set the credential secret with monkeypatch inside a fixture rather than at import time."
 },
 {
  "id": "R1-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Lookups edit the view's shared records without a lock: concurrent lookups and the capability refresh raise KeyError/RuntimeError",
  "files": [
   "uri_core/app/server.py:248",
   "uri_core/app/server.py:255",
   "uri_core/app/server.py:257",
   "uri_core/app/server.py:665",
   "uri_core/core/graphify_index.py:346"
  ],
  "evidence": "_sync_memory calls graphify_index.refresh(scope='memory'), which deletes then re-adds keys in self.records in place, on every get/list_all/relevant_subset. /ask is a sync endpoint, so FastAPI runs it in its thread pool; the no-login view is shared by all no-login requests. Probe (/tmp/uri_review_R1/conc/test_conc.py; 300 memories, sys.setswitchinterval(1e-6)): two threads calling view.relevant_subset raise KeyError('memory:...') out of relevant_subset (the error comes from _sync_memory, outside relevant_subset's own try). With list_all readers: RuntimeError 'dictionary changed size during iteration'. A concurrent refresh(view, scope='capabilities') (as in refresh_user_external_lifecycle, server.py:665) raised RuntimeError 1466 times in 8 s; external_lifecycle_lock does not cover Brain-turn lookups, so a capability republish can abort before multi_action_dispatch is swapped. decision_engine catches the relevant_subset error, so in a Brain turn this drops the hint for that turn. Before this change, lookups only read.",
  "suggested_fix": "Build the merged record dict (non-memory plus freshly indexed memory) in a local variable and assign self.records once, under a per-view lock that the capability/service refresh path also takes (or have that refresh replace records atomically under the same lock). Catch any exception in _sync_memory so a lookup never raises."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
