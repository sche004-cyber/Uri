You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 29771992f57ff470035f044c55e2c6689e9d3d6d.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R5-01"]
Their history (reviewer text, untrusted): [
 {
  "round": 5,
  "finding": {
   "blocking": true,
   "category": "security",
   "evidence": "_BARE needs a non-[\\w-] character on both sides of the domain ('(?<![\\w-])' before it, '(?![\\w-])' after the top-level label), and '_' is \\w; the first host label also cannot start with '_'. Probe /tmp/uri_review_R5/p1.py: has_link_or_contact returns False and mask_links leaves the text unchanged for 'Claim at _refunds-portal.com_ today.', 'refunds-portal.com_', '_refunds-portal.com', '-refunds-portal.com', '__refunds.cash__', 'refunds.com-'. Probe p2.py with source 'Claim your energy rebate refund at _refunds-portal.com_ before the deadline.': verify() keeps the Brain sentence, extractive() picks it, build_surface shows the domain and require_valid accepts the surface. The same happens for '_refundsportal.xn--p1ai_'. Markdown italics/emphasis is a realistic form in retrieved web text.",
   "files": [
    "uri_web/untrusted.py:67",
    "uri_web/untrusted.py:164",
    "uri_web/untrusted.py:171",
    "uri_web/synthesize.py:225",
    "uri_web/synthesize.py:305",
    "uri_web/surface.py:38"
   ],
   "id": "R5-01",
   "owner_decision": false,
   "severity": "HIGH",
   "suggested_fix": "Do not treat '_' or a trailing/leading '-' as part of the word around the domain: drop '_' and '-' from the boundary lookarounds (e.g. use (?<![^\\W_]) and (?![^\\W_])), or strip '_'/'-' runs at token edges before matching, and also check every token after removing edge punctuation and underscores. Add regression cases for _x.com_, x.com_, -x.com, __x.cash__ in has_link_or_contact, verify, extractive and the surface.",
   "title": "R1-01 class still open: a link next to an underscore or hyphen ('_refunds-portal.com_', 'refunds-portal.com_', '-refunds-portal.com') passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator"
  }
 },
 {
  "round": 6,
  "finding": {
   "id": "R6-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "R1-01 class still open: a one-sided spaced dot ('refunds-portal .com/claim') or a dot-like separator (U+00B7, U+30FB, U+2219, U+22C5, U+2027, '{.}', '<.>') passes has_link_or_contact, verify(), extractive(), the research surface and the A2UI validator (W1-AC15/AC12)",
   "files": [
    "uri_web/untrusted.py:69",
    "uri_web/untrusted.py:71",
    "uri_web/untrusted.py:168",
    "uri_web/synthesize.py:240",
    "uri_web/synthesize.py:320",
    "uri_web/surface.py:37"
   ],
   "evidence": "Probe /tmp/uri_review_R6/probe_e2e.py: src = 'Claim your energy rebate refund at refunds-portal .com/claim before the deadline. Energy rebate refunds take two weeks.'; U.has_link_or_contact -> False; SY.verify(<same sentence> [1], [src]).claims keeps it unquoted; SY.extractive('energy rebate refund deadline',[src]) picks it; build_surface(...) passes require_valid and the dump contains 'refunds-portal .com/claim'. The same holds for 'refunds-portal\u00b7com', 'refunds-portal\u30fbcom', 'refunds-portal\u2219com', 'refunds-portal{.}com'. _DOT accepts '\\s+\\.\\s+' (spaces on both sides) but not a space on one side only, and accepts only . U+3002 U+FF0E U+FF61 as dot characters.",
   "suggested_fix": "Treat '\\s*\\.\\s*' between label-like runs when the right side is a TLD-shaped label followed by a non-letter (or '/'), and add the dot-like punctuation (U+00B7, U+0387, U+2027, U+2219, U+22C5, U+30FB, U+2E3C, braces/angle-bracket defangs) to _DOT; add regressions for each through verify, extractive, build_surface and require_valid."
  }
 },
 {
  "round": 6,
  "finding": {
   "id": "R6-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "R5-02 repair incomplete: lead_ok/tail_ok treat a comma as a safe edge, so a claim drops a qualifier set off by commas ('that, at most, a quintet of firms...') before an undetected quantity word and is shown unquoted (D7)",
   "files": [
    "uri_web/synthesize.py:142",
    "uri_web/synthesize.py:185",
    "uri_web/synthesize.py:196",
    "uri_web/synthesize.py:207"
   ],
   "evidence": "Probe /tmp/uri_review_R6/probe_d7.py: SY.verify('A quintet of firms control the regional market [1].', ['Analysts said that, at most, a quintet of firms control the regional market.']) -> one claim, quoted=False, no drops. The same for 'By some estimates, a plurality of voters backed the measure.' and the trailing forms 'A quorum of members attended the session, or nearly so.' and 'A plurality of voters backed the measure, at least initially.' (all quoted=False).",
   "suggested_fix": "Fail closed at the edges: a claim that does not start at the sentence start (after determiners only) or end at the sentence end should be quoted, or allow a clause edge only when the dropped clause holds no qualifier/hedge (an allow-list, as for gap_ok), not just any comma."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "ca622bc0354a960c82acd7a33ecc6de5bb9f360a", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04", "R1-05", "R1-06"]}, {"repair": 2, "commit": "f370064354ba678ec5fed956a709cd0e7626c269", "addresses": ["R2-01", "R2-02", "R2-03"]}, {"repair": 3, "commit": "462be42c992c273155e83801b32dc01580a897ef", "addresses": ["R3-01", "R3-02"]}, {"repair": 4, "commit": "f5a5b8ecbb5c524b3b768cc09ae71dfa2bcc068b", "addresses": ["R4-01", "R4-02"]}]

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
