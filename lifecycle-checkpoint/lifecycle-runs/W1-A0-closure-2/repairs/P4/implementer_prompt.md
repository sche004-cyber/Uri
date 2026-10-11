These findings RECUR after earlier repairs. Do not repeat the earlier approach. A separate diagnosis (verbatim, untrusted) says:
{
 "root_cause": "R3-01: the candidate regex _BARE (uri_web/untrusted.py:64, unchanged since f370064) only accepts a top-level label of 2-24 letters ([^\\W\\d_]{2,24}) and forbids a hyphen or word character after it ((?![\\w-])). A punycode/ACE TLD such as 'xn--p1ai' (digits and hyphens) never produces a match, so _is_domain, which repair 3 made fail closed, is never called. _OTHER and _PHONE don't catch it either, so has_link_or_contact, verify(), extractive(), mask_links and build_surface all let it through. R3-02: _excerpt.gap_ok (uri_web/synthesize.py:166-167) still lets the source drop one determiner plus up to MAX_GAP_WORDS=2 words that aren't function words, and match() (synthesize.py:180) lets the claim omit the determiner. Qualifiers and adverbs sit exactly in that slot ('a roughly decennial cycle', 'a near unanimous decision', 'a barely positive profit'), so whether the claim gets quoted still depends on states_quantity recognising the word. This contradicts the docstring's 'fails closed' claim.",
 "why_earlier_repairs_failed": "Every repair patched the reported strings and the layer the reviewer pointed at, not the permissive structure. R3-01: f370064 introduced _BARE with a letters-only TLD group plus a TLD allow-list in _is_domain. 462be42 rewrote only _is_domain to fail closed (diff touches _is_domain, _DOT, _PHONE, _SENTENCE_WORDS; the _BARE line is byte-identical in both commits), so anything _BARE can't match is still missed. Its regression LINKS list (tests/web/test_w1_r3_review_regressions.py:24-28) has only letter-only TLDs and spaced or phone forms, with no digit, hyphen or xn-- TLD. R3-02: f370064 replaced _in_order with a gap rule allowing any 2 skipped content words and kept states_quantity as the guard. 462be42 narrowed that to 'determiner + 2 non-function words' and added more words to _QUANTITY (doubling, ...tupled, biweekly), but kept the noun-phrase-modifier carve-out. It even added test_r3_02_noun_phrase_modifiers_may_still_be_left_out (test file:104-106), which requires 'after [a long public] consultation' to be skippable. Its invented-word tests only cover qualifiers before verbs, never qualifiers inside a noun phrase after a determiner, so the hole was codified, not closed.",
 "evidence": [
  "uri_web/untrusted.py:64 _BARE tld group (?P<tld>[^\\W\\d_]{2,24})(?![\\w-]); `git show f370064:uri_web/untrusted.py` line 52 is identical, so 462be42 did not change it",
  "uri_web/untrusted.py:120-132 _is_domain fails closed but is only reached via _BARE.finditer (untrusted.py:137)",
  "probe /tmp/d3/probe.py: has_link_or_contact -> False for 'Claim at refunds.xn--p1ai now', 'Refunds-Portal.XN--P1AI', 'bank.xn--vermgensberatung-pwb', 'x.xn--p1ai/claim', 'claim at a1.xn--90ais'; True for 'refundsportal.Cash'",
  "probe: SY.verify('Claim your energy rebate refund at refundsportal.xn--p1ai before the deadline [1].',[src]) -> claim kept (quoted=True) with the link in it, dropped=[]",
  "uri_web/surface.py:38 masks via U.mask_links, whose _spans (untrusted.py:135-140) relies on the same _BARE",
  "uri_web/synthesize.py:166-167 gap_ok: skipped[0] in _DETERMINERS and len(skipped)-1 <= MAX_GAP_WORDS and no function words -> skip allowed regardless of meaning",
  "uri_web/synthesize.py:180 claim may omit a determiner the source has",
  "probe: verify('The national census is held on decennial cycle [1].',['The national census is held on a roughly decennial cycle.']) -> quoted=False; same for 'a near unanimous decision', 'a roughly quinquennial schedule', and non-quantity cases 'a barely positive profit' -> 'profit', 'a hardly popular plan' -> 'plan'",
  "tests/web/test_w1_r3_review_regressions.py:104-106 requires _excerpt('approved the rules after consultation', '... after a long public consultation.') to be True, which locks in the hole",
  "tests/web/test_w1_r3_review_regressions.py:24-28 LINKS contain no xn--/digit/hyphen TLDs"
 ],
 "proposed_fix": "R3-01: in _BARE, make the TLD group fail closed on its shape, not on letters: (?P<tld>(?i:xn--[a-z0-9-]{1,59})|[^\\W\\d_][\\w-]{1,62}) with the end anchored (?![\\w-]) after the whole label, requiring at least one letter. In _is_domain, treat any host label or TLD starting with 'xn--' (case-insensitive) as a link before the _SENTENCE_WORDS/CJK exceptions. Keep the existing exceptions unchanged so the ordinary-text test still passes. Add a self-contained parametrised regression over 'refundsportal.xn--p1ai', 'Refunds-Portal.XN--P1AI', 'bank.xn--vermgensberatung-pwb', 'x.xn--p1ai/claim' through has_link_or_contact, verify (claim dropped), extractive (not picked) and build_surface (masked, require_valid passes). R3-02: in gap_ok, allow a gap only when every skipped token is a determiner (delete the 'determiner + MAX_GAP_WORDS modifiers' branch). Any skipped modifier means the source sentence is quoted instead, which D7 says is always safe since over-quoting only costs fluency. Optionally also stop the claim from dropping a determiner the source has, when it is followed by a skipped word. Replace test_r3_02_noun_phrase_modifiers_may_still_be_left_out with its inverse (the long-public-consultation pair must come out quoted, or _excerpt False), and add regression pairs that must yield quoted=True with text == source: decennial/'a roughly decennial cycle', 'a near unanimous decision', 'a roughly quinquennial schedule', plus invented-word 'a seldom zorby plan' -> 'zorby plan' to show it doesn't rely on the word list. Add decennial|centennial|septennial|quinquennial|\\w+ennial(ly)?|unanimous(ly)? to _QUANTITY only as a secondary check.",
 "needs_owner": false
}
Address the root cause it names, or report the finding as not repaired.

You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 462be42c992c273155e83801b32dc01580a897ef.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 462be42c992c273155e83801b32dc01580a897ef and PASSES after
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
- graphify: do NOT run `graphify update` (or any graphify command that writes) in this working tree, and do not delete or edit anything under graphify-out/: those files are tracked and outside the permitted paths, so the change would be refused. The repository rule 'run graphify update after modifying code' is satisfied by the coordinator, who rebuilds the graph outside the repository. For code navigation use read-only queries: `graphify query "..." --graph /home/user/uri-wt/graphs/W1-A0/graphify-out/graph.json` (also `path`, `explain`).

Findings (from the reviewer, verbatim):
[
 {
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
 },
 {
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
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
