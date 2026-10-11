You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit f604e7cd73ba15a567b31e9b4360e2a4ef7de892.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on f604e7cd73ba15a567b31e9b4360e2a4ef7de892 and PASSES after
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
  "id": "R7-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R1-01 link class still open: a dot in a non-ASCII bracket/quote pair with spaces ('refunds-portal \u3010.\u3011 com/claim', '\u300c.\u300d', '\u3014.\u3015', '\u00ab.\u00bb', '\u27e8.\u27e9', '\".\"'), a spaced dot run ('refunds-portal . . com/claim') or a So-category bullet ('\u25e6' U+25E6, '\u25cf') passes has_link_or_contact, verify(), extractive(), the research surface and the A2UI validator (W1-AC15/AC12, within D13 'any bracketed dot')",
  "files": [
   "uri_web/untrusted.py:134",
   "uri_web/untrusted.py:162",
   "uri_web/untrusted.py:163",
   "uri_web/untrusted.py:165",
   "uri_web/synthesize.py:255",
   "uri_web/surface.py:37"
  ],
  "evidence": "Probe /tmp/uri_review_R7/p3.py, with SENT='Claim your energy rebate refund at {} before the deadline.' and link='refunds-portal \u3010.\u3011 com/claim': U.has_link_or_contact(src) is False; SY.verify(SENT[:-1]+' [1].',[src]) keeps the claim 'Claim your energy rebate refund at refunds-portal \u3010.\u3011 com/claim before the deadline .'; SY.extractive('energy rebate refund deadline',[src]) returns the same sentence; build_surface plus require_valid accept it and the surface JSON contains 'refunds-portal'. Same for '\u300c.\u300d', '\u3014.\u3015', '\u00ab.\u00bb', '\u27e8.\u27e9', '\".\"', \"'.'\", ' . . ', '\u25e6', '\u25cf', '(d o t)'. ASCII '[ . ]' and fullwidth '\uff3b.\uff3d' are caught. Cause: the bracket alternative at :163 accepts only [({< and ])}>; the spaced alternative at :165 excludes a run that begins with _OPENING (Ps/Pi); _DOTLIKE+ at :162 allows no space between dots; _is_dotlike (:134) excludes category So, so U+25E6 WHITE BULLET is not dot-like despite its name. The R7 regression test file only generates tight, doubled or left-spaced single marks. Comments also self-declare 'portal, com'/'portal: com' as residual limits, which the owner ledger (D13) does not record; 'refunds-portal; com/claim' and 'refunds-portal! com/claim' also pass.",
  "suggested_fix": "Treat any Ps/Pi..Pe/Pf pair (Unicode bracket and quote pairs) around a dot-like mark or 'dot' as a separator, with optional spaces; allow spaces inside a dot-like run ('. . .'); widen _is_dotlike to name-matched So characters (BULLET, DOT, CIRCLE OPERATOR/SPOT as decided). Add generated tests for '<space><open><dot><close><space>' over all bracket/quote pairs and for spaced dot runs, end to end through verify/extractive/surface."
 },
 {
  "id": "R7-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Verifier keeps a reversed-meaning claim in the Brain's words: an added or dropped determiner turns 'a little' into 'little' (and back), and the claim keeps its citation",
  "files": [
   "uri_web/synthesize.py:171",
   "uri_web/synthesize.py:196",
   "uri_web/synthesize.py:209",
   "uri_web/synthesize.py:72"
  ],
  "evidence": "Probe /tmp/uri_review_R7/p4.py: SY.verify('Little progress was made on the energy rebate bill this session [1].', ['A little progress was made on the energy rebate bill this session.']) keeps the claim unquoted (quoted=False) citing [1]; the reverse also passes, as do 'Lawmakers expect little support ...' against 'expect a little support ...' and 'found a little evidence of fraud' against 'found little evidence of fraud'. _excerpt lets the claim add a determiner (synthesize.py:209) and lets the source drop leading or mid-sentence determiners (lead_ok :196, gap_ok :171); 'little' is not in _QUANTITY and not in _NEG/_ANTONYMS. Scarcity versus presence is reversed, while the citation says the source states it (R1-06 / D7 class).",
  "suggested_fix": "Do not let an added or skipped determiner sit directly before a quantifier (little, few, bit, lot, number, deal, ...), or add 'little' (and similar determiner-sensitive quantifiers) to _QUANTITY so such claims are quoted; more generally, require the claim's determiners to equal the source's in place."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
