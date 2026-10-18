# BRAIN-QC-20261018 independent review R3 (focus: R2 repairs)

Reviewer: independent subagent, read-only. Repo `D:/uri-dev/uri-brain-quick-controls`, HEAD verified `57b4e589`, working tree clean before and after.

## Verdict: ACCEPT WITH FINDINGS (2 LOW doc-record, 2 INFO)

The R2-01 and R2-02 code repairs are correct and their tests are meaningful. R2-03 and R2-05 are fully repaired. R2-04 is mostly repaired. The gate evidence is pinned to 9ea83b24, and that commit is code-identical to ce5c2fe0 and 57b4e589. The boundaries are unchanged. One problem remains: the qualification record (QC-9 and QC-10) and the report's gates section still give the R1-era gate numbers at 25701f51. They do not give the numbers measured at 9ea83b24.

## Acceptance criteria (defined first)
- A1: The R2-01 fix is correct, the test fails without the fix, and the fix brings no new loop, extra-call or stuck-state risk.
- A2: The R2-02 LRU is correct and the test is meaningful. The notice wording and the QC-F7 disclosure are accurate.
- A3: The R2-03/04/05 record corrections are accurate against the primary evidence.
- A4: The gates are pinned to 9ea83b24, the code diffs are empty, and the numbers match the logs.
- A5: The boundaries are unchanged.
- A6: There is no overstated claim, especially about live evidence.

## Results
- **A1: MET.**
  - The new condition `|| brainStatus['switching'] == true` is at `oi_conversation.dart:287`.
  - **Ran:** I copied `uri_ui` to scratch and reverted only that condition in the copy. The R2-01 test then FAILS at line 245 (`Expected 'READY', Actual 'STARTING'`). With the fix in the repo, all 18 tests in `brain_quick_controls_test.dart` pass.
  - **Risk analysis (read):**
    - The extra `brain_status` call happens only while the stored status is masked. The `switching` key is produced only by the UI mask; no backend emits it (grep).
    - The first successful read with no pending switch clears the mask. There is no loop.
    - If reads keep failing, the header stays "STARTING". This is the conservative direction and never a false READY. Worker death is handled by the liveness monitor.
    - `refreshStatus` assigns an unmasked status, but it calls `refreshHealth(notify:false)` before it notifies, so the mask is re-applied.
  - Nit: the new test is a plain `test()`, not a `testWidgets`. The report calls it a "Widget test".
- **A2: MET with INFO.**
  - The pop-before-insert at `worker_bridge.py:292` makes the dict order least recently used.
  - **Read/reasoned:** without the pop, `long` would keep its first-insert position and be evicted when `new` is added. The assert `"long" in b._context_tokens` would then fail. The test is meaningful.
  - **Ran:** pytest `tests/oi tests/ws`: 763 passed, 23 skipped, exit 0.
  - The notice is accurate in substance: the refusal uses `_largest_context()` across all held sessions, and Restart URI replaces the worker. See R3-03 and R3-04.
- **A3: MET except R3-02.**
  - **IC-1:** it names the three files. I verified that `fa0a70e6` and `4d782ef1` touch `run_uri_integrated_worker.py` and `brain_health.py`, and that `ws_brain_host.py` is in the original five. `c3fc8bbc` exists, is not an ancestor of HEAD, and its SELECTABLE is {frozen, (65536, off, False), (32768, gpu, False)}. The note also states the rebase/merge, the gates and the live round trip.
  - **AT_RISK:** the qc-1..qc-5 `summary.json` verdict margins are -294.5, -335.3, -332.3, -336.6 and -299.3, so the range -294.5..-336.6 is correct. Some per-sample `fit_margin_mib` values go down to -345.8, but the summary verdicts are the cited measure.
  - **Other numbers:** stop `since_stop_s` is 3.5-3.6 (matches). The decode peak after the switch is 147.6-151.3 in qc-2..qc-5 (matches "147-151"). "4817" and constant pids are present in qc-1..qc-5.
  - **Record fields:** `not_qualified` states that there was no live run on ce5c2fe0. `open_findings` lists QC-F1..F8 plus IC-1.
- **A4: MET for the evidence itself; the record is stale (R3-01).**
  - All five `.head` files contain `9ea83b24`.
  - Both `git diff ce5c2fe0 9ea83b24 -- . ':!docs'` and `git diff ce5c2fe0 57b4e589 -- . ':!docs'` are empty (0 bytes).
  - The logs show:
    - pytest: 763 passed, 23 skipped;
    - flutter test: 779 passed, 5 skipped, exit 0;
    - flutter analyze: 4 info messages, exit 1 because infos are fatal, all in files this milestone did not touch;
    - release build: built `uri_ui.exe`, exit 0;
    - `frozen_check.json`: ok true, with no unapproved changes.
  - **Ran:** I re-ran `ws_frozen_check` at HEAD (ok true, `unapproved_drift` [] and `unapproved_protected_changes` []), and re-ran pytest (763/23, as above).
  - **Not run:** the full flutter suite, analyze and the release build. For these I read the logs only.
- **A5: MET.**
  - `git diff f3d5eb29 57b4e589` on `runtime_profiles.py`, `runtime_profile_selection.py`, `runtime_v1.py` and `model_lab/` is empty.
  - The UI V2 frozen files against 7893aaed are additive only: `oi_conversation.dart` +98/0 and `living_composer.dart` +37/0. The stored patch is byte-equal to a fresh `git diff`.
- **A6: MET.**
  - "Live evidence after R2" correctly says that no new live run was made, and that qc-4/qc-5 ran on 78db55f6/578f7c40, before ce5c2fe0.
  - `candidate_code_commit` says the same.
  - No live claim is made for the R2 changes.

## Findings
- **R3-01 LOW (record staleness).**
  - **Location:** `BRAIN_QC_QUALIFICATION.json` QC-10 says "at 25701f51: pytest 762/23 skipped, flutter test 778, ...". QC-9 says "ws_frozen_check ok at 25701f51; UI V2 frozen files +96/0". `BRAIN_QC_REPORT.md` "Gates at `25701f51`" gives 762/778/+96. The R2 section says only that the gates were "run again on the commit named in `.head`", and gives no numbers.
  - **Fact:** the evidence at 9ea83b24 shows 763/23, 779 and +98/0.
  - **Fix:** update QC-9 and QC-10 to 9ea83b24 (code = ce5c2fe0) with 763/23, 779 (+5 skipped), analyze 4 infos, release OK, frozen ok and +98/0/+37/0. Add a "Gates at 9ea83b24" line to the R2 section of the report, and keep the 25701f51 section as history.
- **R3-02 LOW (doc accuracy, R2-02 verification column).**
  - **Location:** the R2 table in the report, row R2-02, says "widget test (the notice text)".
  - **Fact:** no test was added or changed for the new wording. The existing R1-02 widget test asserts only `about 30000 tokens` and `Keep the larger context`, which the old wording also contained. Reverting the wording would not fail any test.
  - **Fix:** either assert the new worker-wide phrase (for example `textContaining('since it started')` and `until URI is restarted`), or reword the row to say the existing test still passes with the new text.
- **R3-03 INFO (QC-F7 / notice precision).**
  - **Location:** QC-F7 and the code comment at `worker_bridge.py:84-86`.
  - **Fact:** they say the sizes "are never cleared", but the 64-entry LRU evicts the least recently used session. A long conversation can therefore stop blocking after more than 64 newer sessions, not only after a restart. The conservative direction is unaffected.
  - **Fix:** use "never cleared except by LRU eviction beyond 64 sessions".
- **R3-04 INFO (notice grammar).**
  - **Location:** `oi_conversation.dart:835`.
  - **Fact:** the text reads "a conversation URI holds since it started", which is awkward.
  - **Fix:** use "a conversation URI has held since it started". This is cosmetic only.

## Ran vs read
- **Ran:**
  - HEAD and diff checks;
  - the R2-01 widget test file on the repo (18/18) and on a scratch copy with the fix reverted (fails at the expected assert);
  - pytest `tests/oi tests/ws` (763 passed, 23 skipped);
  - `ws_frozen_check` (ok);
  - boundary diffs;
  - the frozen-files patch against a fresh diff (byte-equal);
  - greps of the qc-1..qc-5 evidence for margins, stop times, decode, 4817 and pids.
- **Read:**
  - the code diffs and the LRU test (I reasoned through its failure without the fix rather than running it);
  - the R2 report;
  - the report and JSON diffs;
  - the gate logs for flutter test full, analyze and the release build (not re-run);
  - the runtime-profiles plan at c3fc8bbc and the commit stats of fa0a70e6 and 4d782ef1.
- **Not done:** no Brain, no GPU, no app launch, no live run.

The findings do not affect the verdict: R3-01 and R3-02 are record and documentation corrections, and the code and gate evidence support acceptance.
