You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit d5a9b41c79b4c9d0be83ab7c43e61f106177d022.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R11-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 11,
  "finding": {
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
 },
 {
  "round": 12,
  "finding": {
   "id": "R12-01",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "In-page hidden-text filter still misses fully invisible text (filter:opacity(0), -webkit-text-fill-color:transparent, non-leading/other clip-path insets and shapes, transparent mask-image, closed <details> content, near-zero opacity); injected instructions reach the Brain request as 'Visible text' and 'Selected text' (R11-01 class not closed)",
   "files": [
    "uri_assist/browser_extension/snapshot.js:57",
    "uri_assist/browser_extension/snapshot.js:63",
    "uri_assist/browser_extension/snapshot.js:87",
    "uri_assist/browser_extension/snapshot.js:126",
    "uri_assist/browser_extension/snapshot.js:120",
    "uri_assist/bridge.py:61",
    "docs/assist/03_PERMISSION_AND_DATA_FLOW.md:77"
   ],
   "evidence": "Real Chromium (Playwright, viewport 1000x900, Ctrl+A), page with <div style='filter:opacity(0)'>FILTEROPACITY-PAYLOAD-B</div>, <div style='-webkit-text-fill-color:transparent'>TEXTFILL-PAYLOAD-C</div>, <div style='clip-path:inset(0 0 100% 0)'>\u2026D</div>, clip-path:circle(0) \u2026E, mask-image:linear-gradient(transparent,transparent) \u2026H, clip-path:polygon(0 0,0 0,0 0) \u2026I, clip-path:inset(0 100% 0 0) \u2026Q, clip-path:inset(60%) \u2026R, <details><summary>Sum</summary>DETAILS-PAYLOAD-S</details>. A screenshot shows none of them rendered, yet snapshot.text and snapshot.selection contain all of them (hidden_text count 8 covers only other cases). Feeding that snapshot through tests.assist.test_a0_access_perception mk()/grant(observe)/ask_and_wait gives status COMPLETE and each payload occurs twice in FakeClient.bodies. Root cause: visible() relies on checkVisibility(opacityProperty) which only catches opacity:0 (not filter/mask/near-zero opacity); the clip-path regex /inset\\(\\s*(50%|100%)/ only matches a leading 50%/100% inset; textVisible checks only alpha(color), not -webkit-text-fill-color; closed-details slot content returns client rects. None of these are in the documented 'Not covered' list, and docs/assist/03 row claims opacity, transparent text colour and clip-path inset are covered.",
   "suggested_fix": "Treat effective opacity (product of ancestor opacity and filter:opacity) below a small threshold as hidden; treat -webkit-text-fill-color alpha 0 like transparent colour; for clip-path parse every inset side (and treat circle/ellipse/polygon with zero area, or any non-inset shape conservatively) and check mask-image/-webkit-mask; exclude text inside a closed <details> other than its <summary>; add these cases to a self-contained Chromium regression test and make the docs/03 coverage claims match the code exactly."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "16f75d8e2e5f537749b32b1d754c347cbebdfc36", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04"]}, {"repair": 2, "commit": "627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede", "addresses": ["R2-01"]}, {"repair": 3, "commit": "16155129b72685f25eca48a65252f6cd51fa47e4", "addresses": ["R3-01"]}, {"repair": 4, "commit": "52e852dcce592e15fc2098bc1e169a7e009eb26a", "addresses": ["R4-01", "R4-02", "R4-03"]}, {"repair": 5, "commit": "08a4569908d7b9db2e22366cada632e5ebe40639", "addresses": ["R5-01", "R5-02"]}, {"repair": 6, "commit": "87720d6dcd765e7e08ae3f44b4e141aa6c2b3bf0", "addresses": ["R6-01", "R6-02", "R6-03"]}, {"repair": 7, "commit": "20a646fd3fe8c48367bdc1cc995df5d09c3e7dab", "addresses": ["R9-01", "R9-02", "R9-03", "R9-04", "R9-05", "R9-06", "R9-07", "R9-08"]}, {"repair": 11, "commit": "2de591eca07d9410f691ac20ff71242d3befc6f6", "addresses": ["R10-01"]}, {"repair": 12, "commit": "d5a9b41c79b4c9d0be83ab7c43e61f106177d022", "addresses": ["R11-01"]}]

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)
- Regression proof: the driver copies ONLY the files you list in regression_tests into a clean checkout of the pre-repair commit and runs them there; new fixture/helper files are NOT copied. Make each regression test self-contained (embed fixture HTML/JS in the test file and write it to tmp_path at run time). A test that is skipped on the pre-repair commit counts as NOT failing, so it must not skip for a missing fixture.

End with:
DIAGNOSIS_BEGIN
{"root_cause": "...", "why_earlier_repairs_failed": "...", "evidence": ["path:line ..."], "proposed_fix": "...",
 "needs_owner": false}
DIAGNOSIS_END
