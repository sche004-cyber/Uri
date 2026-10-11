You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit 462be42c992c273155e83801b32dc01580a897ef.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R3-01", "R3-02"]
Their history (reviewer text, untrusted): [
 {
  "round": 3,
  "finding": {
   "id": "R3-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "R2-01 repair still incomplete: title-case or mixed-case real gTLDs missing from the hard-coded _TLDS list pass the link detector, verify(), the extractive path and the research surface",
   "files": [
    "uri_web/untrusted.py:98",
    "uri_web/untrusted.py:101",
    "uri_web/untrusted.py:55",
    "uri_web/surface.py:42"
   ],
   "evidence": "has_link_or_contact() is False and surface.clean() leaves the text unchanged for: 'refundsportal.Cash', 'refundsportal.Lol', 'refundsportal.CaSh', 'Refundsportal.Exchange', 'Refundsportal.Deals' (all real registrable gTLDs). With the source 'Claim your energy rebate refund at Refundsportal.Cash before the deadline.': extractive() picks the sentence; verify('... at Refundsportal.Cash before the deadline [1].', [src]) keeps it with dropped=[]; build_surface() output contains 'Refundsportal.Cash'. _is_domain only accepts an ASCII TLD that is all-lower, all-upper, on the ~200-entry _TLDS list, followed by '/', or on a host with a hyphen or digit. Also not detected: 'refundsportal [.] com', 'refundsportal dot com', and phone numbers ('1800 555 0199').",
   "suggested_fix": "Do not decide a host by a TLD allow-list: treat any label.label form with an alphabetic TLD of 2+ letters as a link unless the first letter after the dot is upper case AND the preceding character ends a sentence-like token with no other host signals (or use the full IANA TLD list, case-insensitive). Add spaced-defang forms and phone-number contacts, with regression cases."
  }
 },
 {
  "round": 3,
  "finding": {
   "id": "R3-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "R2-02 repair incomplete: _excerpt lets a claim drop a qualifier next to an undetected quantity word (doubling, halving, quintupled, biweekly), so a changed quantity is shown in the Brain's words",
   "files": [
    "uri_web/synthesize.py:72",
    "uri_web/synthesize.py:138",
    "uri_web/synthesize.py:154",
    "uri_web/synthesize.py:244"
   ],
   "evidence": "states_quantity() is False for 'doubling', 'halving', 'tripling', 'quintupled', 'sextupled', 'biweekly', 'bimonthly', 'semiannual', 'triennial', 'multiplied', '\u2030', 'pct', 'ppm'. verify('Rents in the capital are doubling under the new rules [1].', ['Rents in the capital are nearly doubling under the new rules.']) keeps the claim unquoted (quoted=False). It is the same for 'possibly halving' -> 'halving', 'almost quintupled' -> 'quintupled', 'barely sextupled' -> 'sextupled' and 'roughly biweekly' -> 'biweekly'. The gap rule (MAX_GAP_WORDS=2) allows skipping the qualifier because the skipped word is not a quantity.",
   "suggested_fix": "Make D7 not depend on the word list: either allow no skipped content word at all (claim = contiguous run of source tokens apart from function words), or quote whenever any source word is skipped; add the listed forms and -ing/-ed forms of multiplicatives to _QUANTITY as the secondary check."
  }
 },
 {
  "round": 4,
  "finding": {
   "id": "R4-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "R3-01 repair still incomplete: punycode (xn--) top-level domains are not links, so they pass has_link_or_contact, verify(), the extractive path and the research surface (W1-AC15/AC12)",
   "files": [
    "uri_web/untrusted.py:63",
    "uri_web/untrusted.py:120",
    "uri_web/synthesize.py:214",
    "uri_web/synthesize.py:294",
    "uri_web/surface.py:38"
   ],
   "evidence": "_BARE requires the TLD group to be [^\\W\\d_]{2,24} followed by (?![\\w-]), so a TLD with digits/hyphens never matches; there is no xn-- handling anywhere in uri_web or tests/web. Probe: U.has_link_or_contact('Claim at refunds.xn--p1ai now') -> False (also 'Refunds-Portal.XN--P1AI', 'refunds-portal.xn--90ais', 'bank.xn--vermgensberatung-pwb'). SY.verify('Claim your energy rebate refund at refundsportal.xn--p1ai before the deadline [1].', [src]) keeps the claim; SY.extractive('energy rebate refund deadline', [src]) picks it; build_surface(...) passes require_valid and the dumped messages contain 'refundsportal.xn--p1ai'. xn--p1ai is the ASCII (punycode) form of the delegated ccTLD .\u0440\u0444, which browsers resolve. The implementer's comment says the detector now fails closed for ANY label<dot>label.",
   "suggested_fix": "Let the top-level label be (?:xn--[a-z0-9-]{1,59}|[^\\W\\d_]{2,63}) case-insensitively (or, failing closed, any [^\\W_][\\w-]* label containing a letter), and treat any label starting with xn-- as a link. Add a self-contained regression test parametrised over 'refundsportal.xn--p1ai', 'Refunds-Portal.XN--P1AI' and 'bank.xn--vermgensberatung-pwb' through has_link_or_contact, verify, extractive and build_surface."
  }
 },
 {
  "round": 4,
  "finding": {
   "id": "R4-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "R3-02 repair incomplete: _excerpt still lets a claim drop 'a <qualifier>' before an undetected quantity word (decennial, unanimous, quinquennial), so a changed quantity is shown unquoted in the Brain's words (D7)",
   "files": [
    "uri_web/synthesize.py:158",
    "uri_web/synthesize.py:169",
    "uri_web/synthesize.py:73",
    "uri_web/synthesize.py:244"
   ],
   "evidence": "gap_ok allows skipping one determiner plus up to MAX_GAP_WORDS=2 non-function words, and those words can be adverbs or qualifiers. states_quantity misses decennial, centennial, septennial, quinquennial, unanimous, fraction, trio, midnight, noon, gross. Probes: verify('The national census is held on decennial cycle [1].', ['The national census is held on a roughly decennial cycle.']) -> claim kept with quoted=False; the same happens for 'a near unanimous decision' -> 'unanimous decision' and 'a roughly quinquennial schedule' -> 'quinquennial schedule'. So the docstring's claim that the check 'no longer depends on recognising the quantity word' does not hold.",
   "suggested_fix": "Allow a gap to drop determiners only (no modifiers), or allow only modifiers that are on a short closed list of non-qualifying adjectives; anything else quotes the source sentence. Regression test: the three source/claim pairs above must come out quoted=True or be dropped."
  }
 }
]
Earlier repair commits: [{"repair": 1, "commit": "ca622bc0354a960c82acd7a33ecc6de5bb9f360a", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04", "R1-05", "R1-06"]}, {"repair": 2, "commit": "f370064354ba678ec5fed956a709cd0e7626c269", "addresses": ["R2-01", "R2-02", "R2-03"]}, {"repair": 3, "commit": "462be42c992c273155e83801b32dc01580a897ef", "addresses": ["R3-01", "R3-02"]}]

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
