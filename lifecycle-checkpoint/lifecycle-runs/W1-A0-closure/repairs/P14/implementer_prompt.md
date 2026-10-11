These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "At HEAD fcfb465 the boundary against hidden page text (owner decision D10) covers only snapshot.pieces (page text, selection, headings), and its pixel test checks only that some ink exists inside a piece's rectangles. Two defects follow. (1) Unchecked channel: form-field labels are built in snapshot.js labelOf() from label.innerText (which keeps screen-reader-only clip, transparent and other undrawn text), aria-labelledby targets' innerText (even for [hidden] elements) and the aria-label attribute. bridge._context_block also falls back to the name and id attributes. All of these go to the Brain under 'Form fields' with no visibility check and no pixel check. Fields that are not shown but count as sensitive (type=hidden) are kept with their labels. (2) Pixel test not tied to the text: onscreen.Screen.check counts horizontal colour edges in the rectangle, so hidden text placed over visible text (z-index:-1 under the ancestor's background, or white on white without a selection) passes because of the other text's ink and is sent labelled 'pixel-checked'. Real Chromium probe (/tmp/uri_diag_D7/probe.py, mk/grant/ask_and_wait, real screenshot): status COMPLETE; the Brain body contains LABELSR-PAYLOAD (the R11 sr-only clip:rect technique, as a <label>), ARIALABEL-PAYLOAD, ARIALB-PAYLOAD (span hidden), NAMEATTR-PAYLOAD and HIDDENINPUT-PAYLOAD under 'Form fields', and ZOVER-PAYLOAD under 'On-screen text (pixel-checked)' and 'Selected text (pixel-checked)'; WHITEOVER-PAYLOAD as well without a selection. redactions={} without a selection and {'selection_withheld': 1} after Ctrl+A. None of these payloads is readable in the screenshots, except WHITEOVER once the Ctrl+A highlight repaints it.",
 "why_earlier_repairs_failed": "d5a9b41 (R11) and d029f60 (R12) each extended the in-page list of CSS hiding techniques and tested only the payloads the reviewer had named (12 and 24 PAYLOAD lines in their tests); every later round found techniques outside the list (R12: filter/text-fill/clip-path shapes/mask/details; R13: negative z-index under the ancestor's background, SVG fill, -webkit-mask-box-image). fcfb465 (D10) changed the approach to a screenshot pixel check, but applied it only to the new pieces arrays. Field labels, aria-label, aria-labelledby, name and id, which also carry page-authored text to the Brain, were left on the old path, which has no per-text visibility check at all (labelOf uses innerText and attributes). The pixel check also measures ink in the rectangle rather than ink belonging to the text, so overlapping visible ink vouches for hidden text. D10 documented this as residual L-A0-5, yet the text is still labelled 'pixel-checked'. The D10 test page (test_a0_d10_pixel_checked_text.py PAGE) has no form fields and no hidden text placed over visible text, so neither gap was exercised.",
 "evidence": [
  "uri_assist/browser_extension/snapshot.js:332-343 labelOf(): label[for].innerText, closest('label').innerText, aria-labelledby -> getElementById(id).innerText, aria-label attribute; no textVisible()/pieces/rects",
  "uri_assist/browser_extension/snapshot.js:6 SENSITIVE_TYPES includes 'hidden'; :378 `if (!shown && !isSensitive) continue` keeps unshown sensitive fields, :381 `label: maskText(label)` sends their label",
  "uri_assist/perception.py:113 field label/name/id copied through _s() only (no onscreen.keep)",
  "uri_assist/bridge.py:56 `f.get('label') or f.get('name') or f.get('id')` emitted under 'Form fields:' (bridge.py:65) with no pixel check",
  "uri_assist/onscreen.py:65-95 Screen.check: passes when edge density >= MIN_EDGE_DENSITY (:87) and total edges >= EDGES_PER_CHAR*chars*height (:93); any ink in the rect counts, whichever element drew it",
  "uri_assist/browser_extension/snapshot.js:221-224 covered(): `e.contains(p)` returns false, so a z-index:-1 child under its ancestor's opaque background is kept in-page (R13 class) and only the not-content-bound pixel check stands behind it",
  "docs/assist/03_PERMISSION_AND_DATA_FLOW.md:83 and docs/assist/A0_QUALIFICATION.md (A0-AC8 row) present page text as pixel-checked; field labels are not mentioned as an unchecked channel",
  "/tmp/uri_diag_D7/probe.py output: no_selection and ctrl_a both COMPLETE; body contains LABELSR/ARIALABEL/ARIALB/NAMEATTR/HIDDENINPUT/ZOVER payloads (WHITEOVER also without a selection); screenshots /tmp/uri_diag_D7/shot_*.png show none of them readable, except WHITEOVER under the Ctrl+A highlight",
  "git show d5a9b41 / d029f60: snapshot.js technique additions plus tests limited to reviewer-listed payloads; git show fcfb465: pixel check wired only to pieces.text/selection/headings in perception.normalise"
 ],
 "proposed_fix": "(1) snapshot.js: build field labels only from text nodes that pass textVisible() inside label[for], the wrapping label and aria-labelledby targets, and emit them as label pieces with rects (pieces.labels[i]). Stop emitting aria-label, name, id and placeholder as display text (send them only to the in-page sensitivity test). Never emit a label for a field that is not shown (count it instead). (2) perception.normalise: run onscreen.keep on label pieces like headings; a field whose label is not drawn keeps type/required/has_value and gets a neutral name ('text field N'). bridge._context_block must not fall back to name/id. (3) onscreen.py: tie the check to the text at least for stacked text, by dropping any piece whose rects overlap another piece's rects beyond a small fraction (or, in-page, any text node that is not the topmost at its rect centre via elementsFromPoint, including when the hit element is its own ancestor). Otherwise state in docs that overlapping-ink text is unverified and stop labelling it 'pixel-checked'. (4) Add a self-contained Chromium regression test (embed the probe page: sr-only label, aria-label, aria-labelledby to hidden span, name-only input, type=hidden aria-label, z-index:-1 and white text over a visible line; with and without Ctrl+A; real screenshot) that asserts no *-PAYLOAD string appears in FakeClient.bodies and that visible text still does. (5) Correct docs/assist/03 and A0_QUALIFICATION to list the field-label channel and the remaining limits exactly.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit fcfb465ad34fd450107908b18ef2d9d3af15ec82.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on fcfb465ad34fd450107908b18ef2d9d3af15ec82 and PASSES after
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
  "blocking": true,
  "category": "security",
  "evidence": "Real Chromium (Playwright) run of HEAD snapshot.js on a page with: <div style='background:#fff'><span style='position:relative;z-index:-1'>ZNEG-PAYLOAD-A</span></div>; <svg><text fill='transparent'>SVGFILL-PAYLOAD-B</text></svg>; <svg><text fill-opacity='0'>SVGFO-PAYLOAD-C</text></svg>; <svg><text fill='none'>SVGNONE-PAYLOAD-D</text></svg>; <div style='-webkit-mask-box-image:linear-gradient(transparent,transparent)'>MASKBOX-PAYLOAD-E</div>. A screenshot without selection shows none of them, yet all five appear in snapshot.text and snapshot.selection, and after mk(snap)/grant(observe)/ask_and_wait the FakeClient request body contains all five (probe /tmp/uri_review_R13/test_r13_hidden.py fails: AssertionError ['ZNEG-PAYLOAD','SVGFILL-PAYLOAD','SVGFO-PAYLOAD','SVGNONE-PAYLOAD','MASKBOX-PAYLOAD']; the probe imports FakeClient/ask_and_wait/grant/mk from tests/assist/test_a0_access_perception.py and must sit in tests/assist with a relative import to run there). Cause: covered() returns false whenever the hit element contains the text node (e.contains(p)), so text painted beneath its own ancestor's opaque background is kept; the paint check reads only webkitTextFillColor/color, never SVG fill/fill-opacity; masked() reads only maskImage/webkitMaskImage, not webkitMaskBoxImage. None of these is in the documented 'Not covered' list.",
  "files": [
   "uri_assist/browser_extension/snapshot.js:107",
   "uri_assist/browser_extension/snapshot.js:224",
   "uri_assist/browser_extension/snapshot.js:239",
   "uri_assist/browser_extension/snapshot.js:225",
   "uri_assist/bridge.py:61",
   "uri_assist/bridge.py:66",
   "docs/assist/03_PERMISSION_AND_DATA_FLOW.md:77"
  ],
  "id": "R13-01",
  "owner_decision": false,
  "severity": "MEDIUM",
  "suggested_fix": "For SVG text, use the computed fill (none/transparent counts as hidden) and fill-opacity multiplied by stroke presence in the paint-alpha check. Treat any non-'none' -webkit-mask-box-image (and mask-border) as masked unless proven opaque. In covered(), when the hit element is an ancestor of the text, also test whether the text or an ancestor below the hit element has a negative z-index (or check elementsFromPoint ordering against an opaque ancestor background). Add these cases to the Chromium regression page and update docs/assist/03 accordingly.",
  "title": "In-page hidden-text filter still misses fully invisible text: negative z-index under an ancestor background, SVG <text> with fill transparent/none or fill-opacity 0, and -webkit-mask-box-image; injected instructions reach the Brain request as 'Visible text' and 'Selected text' (R12-01 class not closed)"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
