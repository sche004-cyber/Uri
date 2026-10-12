You are DIAGNOSING a recurring defect in URI milestone W1-A0-closure at commit f370064354ba678ec5fed956a709cd0e7626c269.
Earlier repairs did not resolve it. Read-only: do not edit files, commit or change refs; probes go to /tmp.
Find the root cause and why the earlier repairs missed it (`git show <commit>` for each), with exact evidence.

Recurring findings (ids): ["R1-01", "R1-02", "R2-01", "R2-02"]
Their history (reviewer text, untrusted): [
 {
  "round": 1,
  "finding": {
   "id": "R1-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "Link/contact text from untrusted sources reaches the research surface; A2UI validator accepts it (W1-AC15/AC12)",
   "files": [
    "uri_web/untrusted.py:38",
    "uri_web/surface.py:20",
    "uri_web/surface.py:24",
    "uri_a2ui/validate.py:19"
   ],
   "evidence": "has_link_or_contact() is False for 'refunds-portal.net/claim', 'xhttps://evil.example/pay', 'hxxps://evil[.]example', 'bursar\uff20evil-mail.com', 'https\uff1a//evil.example/claim' (scheme regex anchored with \\b, no bare-domain pattern, no NFKC). Probe /tmp/uri_review_R1/web/p2_links.py end to end: extractive answer and verify() keep them; build_surface renders a1 'Hostel fee refunds are handled by the bursar, see xhttps://evil.example/pay for the hostel fee form. [2]'; require_valid passes with '://' in the dump (contradicting the invariant asserted in tests/web/test_w1_pipeline_citations_injection.py:225). Source titles 'Refunds at refunds-portal.net' are rendered unmasked. Prior R1-06 is still open.",
   "suggested_fix": "NFKC-normalise before matching; match '://' without a leading \\b; add bare-domain (label.label.tld[/path]), hxxp and [.] patterns; apply the same pattern in surface._LINK and validate._URLISH; regression tests with these five strings."
  }
 },
 {
  "round": 1,
  "finding": {
   "id": "R1-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "D7 (quantities quoted verbatim) bypassed by quantity words the detector misses (tenfold, decade, percentage points, couple)",
   "files": [
    "uri_web/synthesize.py:72",
    "uri_web/synthesize.py:95",
    "uri_web/synthesize.py:177"
   ],
   "evidence": "verify('Rents in Texas rose tenfold [1].', ['Wages in Ohio rose tenfold over the period while rents in Texas also rose sharply.']) -> claim shown quoted=False 'Rents in Texas rose tenfold .' (reproduced by the reviewer). The pipeline (p3_pipeline.py) renders surface a0 'Rents in Texas rose tenfold . [1]' via Brain synthesis. The bag-of-words support check (synthesize.py:177) passes because every word appears in the source.",
   "suggested_fix": "Extend _QUANTITY (\\w+fold, percentage, decades?, centur(y|ies), couple, pair, dual, single-letter roman numerals after Phase/Part/Class) and/or require non-quoted sentences to be an in-order span of the supporting source sentence."
  }
 },
 {
  "round": 2,
  "finding": {
   "id": "R2-01",
   "severity": "HIGH",
   "blocking": true,
   "category": "security",
   "owner_decision": false,
   "title": "R1-01 repair incomplete: link forms with zero-width space, title-case TLD, IDN host, soft hyphen or U+3002 pass the detector, verify(), the extractive path and the research surface",
   "files": [
    "uri_web/untrusted.py:44",
    "uri_web/untrusted.py:51",
    "uri_web/surface.py:26",
    "uri_web/surface.py:42"
   ],
   "evidence": "LINK_PATTERN's bare-domain branch accepts only [A-Za-z0-9-] labels and an all-lower or all-upper TLD; NFKC keeps U+200B, U+00AD and U+3002, and clean() strips only chars < 32. With H='Hostel fee refunds are handled by the bursar, see {} for the hostel fee form.', U.has_link_or_contact is False, verify(H+' [1]',[H+...]) keeps the claim, and build_surface(...) passes require_valid with the domain in the messages for each of: 'refunds-portal.Net/claim', 'refunds-portal\\u200b.net/claim', 'refunds-p\\u00f6rtal.net', 'refunds\\u00adportal.n\\u00adet', 'refunds-portal\\u3002net/claim', 'refunds-portal.\\u0441om'. End to end: ResearchJob(use_brain=False) on a page '<p>... see refunds-portal&#8203;.net/claim for the hostel fee refund form today.</p>' returns COMPLETED_WITH_RESULT with that sentence in answer[0], and the surface (valid) contains it; same for 'refunds-portal.Net/claim' and 'refunds-p&#246;rtal.net/claim'. W1-AC15 (no URLs in the surface) and W1-AC12 are unmet.",
   "suggested_fix": "Before matching, strip default-ignorable/format characters (Cf: U+200B-U+200D, U+2060, U+00AD, U+FEFF) and map U+3002/U+FF61 to '.'; allow Unicode letters in labels; accept any-case TLD when followed by '/' or when the TLD is in a known-TLD list; apply the same cleaned text in surface.clean() so the displayed text has no invisible characters."
  }
 },
 {
  "round": 2,
  "finding": {
   "id": "R2-02",
   "severity": "MEDIUM",
   "blocking": true,
   "category": "code",
   "owner_decision": false,
   "title": "R1-02 repair incomplete: _in_order is a subsequence test, so a claim cut from one sentence restates a quantity in the Brain's own words, and the quantity-word list still misses common forms",
   "files": [
    "uri_web/synthesize.py:125",
    "uri_web/synthesize.py:198",
    "uri_web/synthesize.py:74"
   ],
   "evidence": "verify('The tax in Texas was cut by an order of magnitude [1].', ['The tax in Texas was cut by basis points while the levy in Ohio was cut by an order of magnitude.']) -> claims [('The tax in Texas was cut by an order of magnitude .', quoted=False)]; d7_invariant.only_source_quotes -> False. The same holds for 'Wages in Texas rose hourly' from '...rose quarterly while rents in Ohio rose hourly', and for 'over a fortnight' and 'in the nineties'. states_quantity is False for 'order of magnitude', 'hourly', 'quarterly', 'nightly', 'per annum', 'fortnight', 'semester', 'biennially', 'last year', 'in the nineties', 'basis points', 'handful', 'nil'. D7 (quantities quoted verbatim) is not enforced.",
   "suggested_fix": "Require the claim's content words to be a contiguous run of the source sentence (allowing function words only), or quote whenever the claim is not a verbatim substring after normalisation; extend the quantity detector (time-period adverbs, 'order of magnitude', 'basis points', decades, seasons, relative dates)."
  }
 },
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
 }
]
Earlier repair commits: [{"repair": 1, "commit": "ca622bc0354a960c82acd7a33ecc6de5bb9f360a", "addresses": ["R1-01", "R1-02", "R1-03", "R1-04", "R1-05", "R1-06"]}, {"repair": 2, "commit": "f370064354ba678ec5fed956a709cd0e7626c269", "addresses": ["R2-01", "R2-02", "R2-03"]}]

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
