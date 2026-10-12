You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit da10d0b84cbd80f60be930295a01baed47b31110.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R13-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 13,
  "finding": {
   "blocking": true,
   "category": "security",
   "evidence": "With SENT='Claim your energy rebate refund at {} before the deadline.': U.has_link_or_contact is False and mask_links leaves the text unchanged for 'refunds-portal \u4e36\u4e3f shop/claim', 'refunds-portal \u318d\u11a2 shop/claim', 'refunds-portal \u0298\u0298 shop/claim', 'refunds-portal ~ \u0298\u0298 shop' and '\u043f\u0440\u0438\u043c\u0435\u0440 \u0298\u0298 shop'. SY.verify(SENT[:-1]+' [1].', [src]) keeps the claim with its citation. SY.extractive('energy rebate refund deadline', [src]) returns the sentence. build_surface plus require_valid accept it with the link text present. On 834c1c30 (git archive export), '\u4e36\u4e3f' and '\u318d\u11a2' forms returned True: R12 changed the walk so a foreign word with more than one distinct letter breaks as the NAME (line 529 `len(set(...)) > 1`), which contradicts the plan's own rule ('words of another script ... may stand between ... when they hold at most two distinct letters'). Same-script non-single words ('\u0298\u0298', the doubled form of the R11-01 '\u0298' look-alike) are always taken as the name (line 525 condition). The prose gap then applies and 'shop' is not core, so the match is dropped (line 544). Controls 'refunds-portal \u4e36\u4e36 shop' and 'refunds-portal \u0298 shop' are detected.",
   "files": [
    "uri_web/untrusted.py:525",
    "uri_web/untrusted.py:529",
    "uri_web/untrusted.py:542",
    "uri_web/untrusted.py:544",
    "uri_web/synthesize.py:252",
    "uri_web/synthesize.py:327",
    "uri_web/surface.py:38"
   ],
   "id": "R13-01",
   "owner_decision": false,
   "severity": "HIGH",
   "suggested_fix": "Restore the R11 rule that a word of at most _MAX_FOREIGN distinct letters from another script is separator, and handle the R12 name case another way (for example, a foreign word with 3 or more distinct letters, or one that is not composed of dot or stroke-like letters, is the name). Treat short same-script words made of non-ASCII letters (or of letters that are not ordinary alphabet letters, such as U+0298) as separator too. Add self-contained regression tests for the forms above through has_link_or_contact, verify, extractive and surface.",
   "title": "R12-01 repair regressed R11-01 and left a same-script variant open: two distinct dot-shaped letters ('\u4e36\u4e3f', '\u318d\u11a2') or a doubled same-script look-alike ('\u0298\u0298') between name and a non-core TLD are read as the name, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D16)"
  }
 },
 {
  "round": 14,
  "finding": {
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
 }
]
Earlier repair commits: [{"repair": 1, "commit": "ca622bc0354a960c82acd7a33ecc6de5bb9f360a", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04", "R1-05", "R1-06"]}, {"repair": 2, "commit": "f370064354ba678ec5fed956a709cd0e7626c269", "addresses": ["R2-01", "R2-02", "R2-03"]}, {"repair": 3, "commit": "462be42c992c273155e83801b32dc01580a897ef", "addresses": ["R3-01", "R3-02"]}, {"repair": 4, "commit": "f5a5b8ecbb5c524b3b768cc09ae71dfa2bcc068b", "addresses": ["R4-01", "R4-02"]}, {"repair": 5, "commit": "f604e7cd73ba15a567b31e9b4360e2a4ef7de892", "addresses": ["R6-01", "R6-02"]}, {"repair": 6, "commit": "474adb8440ffcf946384edd23c15245c3061eee5", "addresses": ["R7-01", "R7-02"]}, {"repair": 7, "commit": "7b1252f79efe62a7a4eff2c2275a7984e5048f1e", "addresses": ["R9-01"]}]

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)
- Regression proof: the driver copies ONLY the files you list in regression_tests into a clean checkout of the pre-repair commit and runs them there; new fixture/helper files are NOT copied. Make each regression test self-contained (embed fixture HTML/JS in the test file and write it to tmp_path at run time). A test that is skipped on the pre-repair commit counts as NOT failing, so it must not skip for a missing fixture.
- graphify: do NOT run `graphify update` (or any graphify command that writes) in this working tree, and do not delete or edit anything under graphify-out/: those files are tracked and outside the permitted paths, so the change would be refused. The repository rule 'run graphify update after modifying code' is satisfied by the coordinator, who rebuilds the graph outside the repository. For code navigation use read-only queries: `graphify query "..." --graph /home/user/uri-wt/graphs/W1-A0/graphify-out/graph.json` (also `path`, `explain`).

End with:
DIAGNOSIS_BEGIN
{"root_cause": "...", "why_earlier_repairs_failed": "...", "evidence": ["path:line ..."], "proposed_fix": "...",
 "needs_owner": false}
DIAGNOSIS_END
