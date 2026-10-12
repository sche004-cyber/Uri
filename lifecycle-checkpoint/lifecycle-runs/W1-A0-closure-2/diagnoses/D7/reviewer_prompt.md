You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 68feb3e70e9ee1ec019f8d543d552b5b2d95d116.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R19-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 19,
  "finding": {
   "blocking": true,
   "category": "security",
   "evidence": "_letter() counts category M as a letter, so ' \\u0323\\u0307\\u0308 ' becomes a word with script COMMON. _separator_word: not single, not in _STROKES, script != the TLD's, and 3 distinct > _MAX_FOREIGN, so it is taken as the NAME. The gap to 'shop' is a plain space (_PROSE_GAP) and 'shop' is not in _CORE, so line 586 skips it. _BARE/_RUN only match '\\s'+COMB+ when a letter follows directly. Probe: has_link_or_contact('Claim your energy rebate refund at refunds-portal \\u0323\\u0307\\u0308 shop before the deadline.') == False; also '... \\u0323\\u0307\\u0308\\u0304 shop', '... cash'. mask_links leaves it unchanged; SY.verify keeps the claim with its citation; SY.extractive returns the sentence; surface.build_surface shows it in the Answer and Sources cards and Surface.__post_init__ (A2UI validation) accepts it. With 1 or 2 distinct marks the same text is caught.",
   "files": [
    "uri_web/untrusted.py:450",
    "uri_web/untrusted.py:463",
    "uri_web/untrusted.py:547",
    "uri_web/untrusted.py:562",
    "uri_web/untrusted.py:583",
    "uri_web/untrusted.py:586",
    "uri_web/surface.py:38"
   ],
   "id": "R19-01",
   "owner_decision": false,
   "severity": "HIGH",
   "suggested_fix": "Treat a word made only of combining marks (or with no base letter) as part of the gap or separator, whatever its length. Better: remove combining marks that do not follow a base letter before splitting into words, so they count as non-prose gap characters.",
   "title": "R1-01 link class still open: a run of three or more distinct combining dot marks on a space ('refunds-portal \u0323\u0307\u0308 shop') is read as the name, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D13/D16)"
  }
 },
 {
  "round": 21,
  "finding": {
   "id": "R21-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "R20-01 repair regressed R19-01: a run of three or more non-'COMBINING'-named marks on a space (Devanagari nukta/candrabindu/anusvara, Tibetan, Arabic, Thai, Telugu signs) between name and a non-core TLD is read as the name, so the link passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator (W1-AC12/AC15, D13/D16)",
   "files": [
    "uri_web/untrusted.py:472",
    "uri_web/untrusted.py:580",
    "uri_web/untrusted.py:581",
    "uri_web/untrusted.py:589",
    "uri_web/surface.py:38",
    "uri_web/synthesize.py"
   ],
   "evidence": "SENT='Claim your energy rebate refund at {} before the deadline.'. For 'refunds-portal \\u093c\\u0901\\u0902 shop', 'refunds-portal \\u0f39\\u0f37\\u0f35 shop', 'refunds-portal \\u0650\\u065c\\u0655 shop', 'refunds-portal \\u0e31\\u0e34\\u0e47 shop', 'refunds-portal \\u0c3c\\u0c00\\u0c01 shop': at 68feb3e7 U.has_link_or_contact -> False, U.mask_links leaves the text unchanged, SY.verify(sentence+' [1].', [src]) keeps the claim, SY.extractive('energy rebate refund deadline', [src]) returns the sentence, and surface.build_surface shows it unmasked in the answer and source title (Surface built without validation error). At eb4d676d all five are detected and masked (True / claim dropped / extractive empty / surface masked). Cause: _separator_word now computes base=_bare(w[2]), and _bare strips only marks whose Unicode name starts with 'COMBINING', so these script marks remain, base has 3 distinct characters, and the old 'all category M -> separator' rule (R19-01) no longer fires.",
   "suggested_fix": "In _separator_word, keep the R19-01 rule before stripping: if every character of w[2] is category M, return True; then use _bare for words that have a base letter. Add the five cases above to the regression tests."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "ca622bc0354a960c82acd7a33ecc6de5bb9f360a", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04", "R1-05", "R1-06"]}, {"repair": 2, "commit": "f370064354ba678ec5fed956a709cd0e7626c269", "addresses": ["R2-01", "R2-02", "R2-03"]}, {"repair": 3, "commit": "462be42c992c273155e83801b32dc01580a897ef", "addresses": ["R3-01", "R3-02"]}, {"repair": 4, "commit": "f5a5b8ecbb5c524b3b768cc09ae71dfa2bcc068b", "addresses": ["R4-01", "R4-02"]}, {"repair": 5, "commit": "f604e7cd73ba15a567b31e9b4360e2a4ef7de892", "addresses": ["R6-01", "R6-02"]}, {"repair": 6, "commit": "474adb8440ffcf946384edd23c15245c3061eee5", "addresses": ["R7-01", "R7-02"]}, {"repair": 7, "commit": "7b1252f79efe62a7a4eff2c2275a7984e5048f1e", "addresses": ["R9-01"]}, {"repair": 8, "commit": "fe77015a8cd20a09b0cd0d6b5115d3edc79df5cb", "addresses": ["R14-01"]}]

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
