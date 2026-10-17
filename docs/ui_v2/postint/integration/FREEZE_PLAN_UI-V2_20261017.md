# UI V2 conditional freeze: approval and verification plan (2026-10-17)

## Owner decision (verbatim summary)

"OWNER DECISION — UI V2 CONDITIONAL FREEZE APPROVAL. I approve freezing UI V2 once UIV2P-SCOPE-1 is fixed and verified
on canonical." Expected sequence: Office completes live verification and independent review; Office integration needs
the owner's separate approval; after integration, verify UIV2P-SCOPE-1 on canonical; if the scope tests pass and no
relevant regressions exist, freeze UI V2; record the final qualification evidence and freeze receipt.

Constraints: do not repeat the full UI V2 live checks unless changes invalidate their evidence; do not modify the frozen
Brain; do not interfere with Office GPU testing; no Ember V2.1 integration before UI V2 is qualified; Thinking, Vision
and Context quick controls stay a separate follow-up; no bypass of security, provenance or independent review.

## Acceptance criteria for the freeze (all required)

1. **Canonical contains the repair.** `integration/git-sync-20261008` on `uri-repo` (ls-remote) is a descendant of
   `25048709` and of the repair commit `3e202efc` (or an equivalent commit whose `ALLOWED_NEW` lists the four paths).
2. **Scope tests pass on canonical.** In a runtime materialized from the canonical tip
   (`scripts/oi_materialize_test_runtime.py`), `tests/phase2a/test_frozen_core.py` and `tests/phase2b/test_boundary.py`
   pass with 0 failures. Baseline at `25048709`: see "Scope baseline" below.
3. **Independent acceptance of the exact tip.** The canonical tip carries a driver-counted independent ACCEPT or
   ACCEPT WITH FINDINGS (the Office integration review) with no open blocking finding, plus the owner's integration
   approval. UI V2's own acceptance: Codex ACCEPT on `25048709` (UI-V2-POSTINT-c6).
4. **No relevant regression.** On the canonical tip: Flutter suite and analyze, and the Python suites the integration
   driver runs, show no new failure against the accepted baseline. Frozen-file integrity (`ws_frozen_check`) passes.
5. **UI V2 live evidence still valid.** The diff `25048709..<tip>` is classified per path. If the diff leaves the UI V2
   shell, companions, settings, navigation and Brain wiring unchanged, the live set pi4/pi5/pi6 (main 68/68, returning
   12/12, perf 3/3 on `25048709`, owner override, frozen Brain) stays valid; the Office session's live runs on the
   integrated Office code cover Office surfaces. If shared UI V2 files changed, only the affected journeys are re-run.
6. **Freeze receipt.** `FREEZE_RECEIPT_UI-V2_<date>.json` with the exact commit, tree, `uri_ui` subtree hash, evidence
   list and limitations; annotated tag `accepted/ui-v2-freeze-<date>` on the frozen commit (existing convention, e.g.
   `accepted/runtime-v1-freeze-20261007`), pushed to `uri-repo`.

## Known limitations to carry into the receipt

- The frozen Brain does not fit by budget on the current desktop (margin -554 to -754 MiB); the UI V2 live passes ran
  under the owner's override (UI V2 only) and depended on placement.
- Input was automated (Flutter TestTextInput and synthesized keys); physical keyboard, mouse and microphone are not
  qualified.
- Separate follow-ups, not part of this freeze: Thinking, Vision and Context quick controls; UIV2-F5 visual fidelity
  (deferred by the owner); DRV-4 (control digest includes `.git/info/*`).

## Scope baseline at canonical `25048709` (measured 2026-10-17)

Runtime materialized from `25048709` at `D:/uri-dev/uri-ui-v2-freeze/rt-25048709` (`oi_materialize_test_runtime.py`,
venv copied from `D:/uri-dev/uri-o2i-live/runtime/.venv`). `tests/phase2a/test_frozen_core.py` +
`tests/phase2b/test_boundary.py`: 13 passed, 2 failed (`test_nothing_changed_outside_checkpoint_and_phase2a_paths`,
`test_phase2a_frozen_core_tests_still_hold`). In a plain checkout 3 more tests fail by design (byte identity and base
commit need the materialized runtime), so a plain checkout is not a valid place to run these tests.

The stray set (`evidence_post_integration_20261017/scope_unlisted_25048709.txt`, computed with the test's own logic by
`scope_list_unlisted.py`) has **89** paths, not 4: 82 Office O2 / devices paths (in canonical since `eaeb10c1`), 3 FCV-R
tests (`test_fcv_ux_repairs.py`, `test_ws_answer_context.py`, `test_ws_clarification_context.py`) and the 4 UI-V2-POSTINT
tests (UIV2P-SCOPE-1). `ALLOWED_NEW` in the Office candidate `3e202efc` (394 globs) covers all 89 (0 uncovered).
