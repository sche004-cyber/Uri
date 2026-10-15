# Independent review R1 - findings and repairs

- **Reviewer:** a fresh general-purpose subagent that did not write the code, working read-only, on 2026-10-15.
- **Scope:** `git diff 89ccf461..279a961e`.
- **Verdict: ACCEPT WITH FINDINGS**, with no BLOCKING findings.
- **Not lifecycle acceptance.** The lifecycle driver is unavailable because the Claude CLI is logged out
  (`claude_cli_auth_status.txt`).
- **Source:** the findings below are transcribed from the reviewer's hand-back message. The harness kept no
  transcript.

## What the reviewer verified independently

- **Diff scope:** no Core, Runtime v1 or Brain file is touched. The changes to accepted files are disclosed.
- **No merge or push:** the only ref is the local branch, and V1 is untouched.
- **Tests:**
  - targeted suites: +97, all pass;
  - its own full `flutter test`: 578 / 5 / 0;
  - `flutter analyze` is clean.
- **Code:** the blink and frame contract and the disposal paths are correct.
- **Assets and evidence:**
  - Every blink source and rect in the shipped manifest is in bounds.
  - The perf table matches `summary.json`.
  - The live blink timings and tok/s figures match the observations.
  - The PRE-1 logs show 0 assertions against 12.
  - The fidelity verdict is honest (NOT MET), and the threshold was not lowered.

## Findings and repairs (commit after `279a961e`)

| ID | Severity | Finding | Repair | Verified by |
|---|---|---|---|---|
| R1-01 | MEDIUM | The success hold survived a later failed finish or a new turn, so "Done" could show for a turn that did not succeed | `oi_sources.dart`: any new finish cancels the hold, which restarts only for `ok`. A new active turn other than the celebrated one cancels the hold. | New test "a failed turn or a new turn ends the success hold at once (review R1-01)". It **fails on the pre-repair file** (Expected idle, Actual success) and passes after. |
| R1-02 | MEDIUM | A partial export (`export_v2.py <clip>`) dropped `blink_atlas`. This could break the manifest or misplace lids | `blink_atlas` is carried over from the previous manifest | Code reading. The shipped assets were verified in bounds by the reviewer. |
| R1-03 | MEDIUM | The raw letter-level reviewer scores were not stored, so the decoding was unauditable | `evidence/fidelity/raw_letter_scores.json` (transcribed from the hand-back messages), `decode_raw_scores.py` and `decoded_scores.txt` reproduce every table. The decode found one more **undisclosed** reviewer C/D mix-up (CP3, reviewer 2, depleted, anchors only). It is now disclosed in `cp3_RESULTS.md`. | Running `decode_raw_scores.py` |
| R1-04 | MEDIUM | The AC-2b calibration rule was replaced without being recorded | `03_FIDELITY_METHOD.md` "Refinement of AC-2b, recorded": CP2-CP8 are miscalibrated under the original rule. The pass threshold is unchanged, and the verdict NOT MET holds under either rule. | Doc |
| R1-05 | LOW | A blink overlay could draw for one vsync at the start of a cross-fade | The overlay is gated on a settled clip (`_previous == null && _fade >= 1`) | Code; existing fade tests pass |
| R1-06 | LOW | Blink data not bounds-checked; a malformed blink failed the whole manifest; the still tile decoded the blink atlas | `_parseBlink` drops only a malformed or out-of-cell blink. A missing atlas drops blinks rather than failing the manifest. The overlay is drawn only if its source lies inside the decoded atlas. The still tile never requests the atlas. | New tests: patch outside the cell drops only that blink; manifest without atlas still parses; still tile does not load the atlas |
| R1-07 | LOW | The OD-8 ownership proof was not persisted in run 4; run 4's log was truncated | `05_LIVE_QUALIFICATION_V2.md` states this precisely. The driver now records `our_brain` and the host's server record at "brain ready" for future runs. | Doc and driver |
| R1-08 | LOW | Ranges slightly imprecise | Corrected: 1.3-7.7 % of Solar's GPU; 2.5-6.9 MB under V1 | Doc |
| R1-09 | LOW | Test gaps | Added: blink atlas freed with the last Ember, still tile, R1-01. Blink while hidden is still covered only by the blinker unit test ("long pause skips the missed blink") and by the frame clock's existing suspension. | Tests |

After the repairs:
- targeted suites: 99 pass;
- `flutter analyze` on the touched files: clean;
- full suite: see `../tests/full_flutter_test_summary_r1.txt`.
