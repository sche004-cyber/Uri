You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 2de591eca07d9410f691ac20ff71242d3befc6f6.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 2de591eca07d9410f691ac20ff71242d3befc6f6 and PASSES after
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

Findings (from the reviewer, verbatim):
[
 {
  "id": "R11-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "In-page hidden-text filter misses screen-reader-only (clip), overflow-clipped, text-indent and covered text; injected hidden instructions reach the Brain request as 'Visible text' and 'Selected text' (R10-01 class not closed)",
  "files": [
   "uri_assist/browser_extension/snapshot.js:54",
   "uri_assist/browser_extension/snapshot.js:63",
   "uri_assist/browser_extension/snapshot.js:146",
   "uri_assist/browser_extension/snapshot.js:159",
   "uri_assist/bridge.py:61",
   "docs/assist/03_PERMISSION_AND_DATA_FLOW.md:77"
  ],
  "evidence": "Real Chromium (Playwright, /opt/pw-browsers), page with <div style='position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)'>SRONLY-PAYLOAD-1</div>, <div style='height:0;overflow:hidden'><p>CLIPPED-PAYLOAD-2</p></div>, <div style='text-indent:-9999px'>INDENT-PAYLOAD-5</div>, <div style='max-height:0;overflow:hidden'><span style='display:block'>MAXH-PAYLOAD-7</span></div>, and text under an absolutely positioned opaque overlay (COVERED-PAYLOAD-8). None of them is visible in the page screenshot. After Ctrl+A, page.evaluate(snapshot.js) returns all of them in snap.text and snap.selection with redactions={} (no hidden_text count). Feeding that snapshot through tests.assist helpers mk/grant(observe)/ask_and_wait gives status COMPLETE, and each payload appears twice in FakeClient.bodies (under 'Visible text' and 'Selected text: Welcome back SRONLY-PAYLOAD-1 CLIPPED-PAYLOAD-2 ...'). Cause: visible() only checks closest([hidden],[aria-hidden],...), checkVisibility, own rect >=1px, font-size<2, clip-path inset, and off-left/top. It ignores the legacy clip property, ancestor overflow clipping, text-indent and occlusion. The data-flow doc claims 'hidden text dropped in page'. Probe: /tmp/uri_review_R11/hidden.html, run.cjs, probe_brain.py.",
  "suggested_fix": "Decide visibility per text node, not per element: use a Range over the text node and check that its client rects intersect the viewport/document and every ancestor's overflow clip box (walk ancestors with overflow != visible, plus clip/clip-path). Treat clip:rect(0,0,0,0) and 1x1 overflow-hidden boxes as hidden. Optionally sample elementFromPoint at the rect centre to detect occlusion. Apply the same rule to page text, headings and the selection, and add a self-contained Chromium regression test with these patterns that checks the Brain body. Otherwise, correct the doc claim to list exactly what the filter covers."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
