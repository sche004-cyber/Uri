You are the IMPLEMENTER repairing URI milestone SSRF-1 at commit f44f70a58e49d9ebe9559004bc81b7c62c0d8fe7.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on f44f70a58e49d9ebe9559004bc81b7c62c0d8fe7 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_core/tools/fetch_url.py, uri_web/safe_fetch.py, tests/ssrf/**, docs/ssrf/**.
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
  "category": "code",
  "owner_decision": false,
  "title": "Every REFUSED status, including DNS failure, port refusal and invalid URL, is reported as a 'private or local network' address",
  "files": [
   "uri_core/tools/fetch_url.py:147",
   "uri_web/safe_fetch.py:259"
  ],
  "evidence": "fetch_url maps rec.fetch_status == REFUSED to the fixed message 'URI will not fetch that address (private or local network).' SafeFetcher also uses REFUSED for DNS_FAILED, DNS_EMPTY, PORT_REFUSED, URL_INVALID and HOST_INVALID. Probe with a resolver raising socket.gaierror for 'http://typo-domain-xyz.com/' returned {'status':'unavailable','message':'URI will not fetch that address (private or local network).','refusal_code':'DNS_FAILED'}. The production tool gives the same for a host of 5x63-char labels (DNS_FAILED), and 'https://example.com:8443/x' gives PORT_REFUSED with the same message. The baseline reported an unresolvable host as 'URI could not reach that URL.' The module docstring promises to report the real reason; a typo'd or offline domain is now told to the user as a private-network address.",
  "suggested_fix": "Use the private/local message only for address-class codes (ADDRESS_NOT_PUBLIC, ADDRESS_TRANSITION_REFUSED, HOST_LOCAL_NAME, HOST_NUMERIC_AMBIGUOUS, USERINFO_REFUSED). Map DNS_FAILED and DNS_EMPTY to 'URI could not reach that URL.', and PORT_REFUSED, SCHEME_REFUSED and URL_INVALID to accurate wording. Keep refusal_code and do not add the address. Add tests for DNS failure and port refusal messages."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
