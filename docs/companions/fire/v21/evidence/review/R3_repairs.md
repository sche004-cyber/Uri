# Review R3 (0484afdc): repairs

**Reviewer.** A separate, read-only Claude agent: an outside-driver fallback, recorded as an **imported review that
the driver does not count**. It worked in the clean worktree `C:\uri-wt\ember-review-0484afdc`. Its verdict was
**REVISE**: 1 HIGH, 4 MEDIUM and 7 LOW findings. The full review is in `R3_review_0484afdc.md`.

| Finding | Action |
|---|---|
| **R3-01 HIGH**: two Brain snapshots of different ages | **Repaired.** New function `brainStartingDetail(runtimeState, health)` in `oi_sources.dart`. Initializing now needs both snapshots to agree on a startup: the runtime is `STARTING`, `LOADING` or `STOPPED`; the newer `brain_health` readiness is `STARTING`, `LOADING` or `READY`, or `STOPPED` with a running host in a startup state; and the running host reports nothing in `FAILED`, `STOPPED`, `STOPPING`, `RELEASE_WAIT` or `WAITING_FOR_GPU`. A failure in either snapshot is never shown as Initializing. A stale `STOPPED` while the newer report says the Brain is up stays calm instead of flashing depleted. New tests cover snapshots that disagree (`companion_initializing_test.dart`, group "decides from both snapshots"). |
| **R3-02 MEDIUM**: `WAITING_FOR_GPU` mapped to Initializing | **Repaired.** `WAITING_FOR_GPU` now stays unavailable, in line with `brain_health`, which reports UNAVAILABLE with the remedy "close GPU apps". Initializing also no longer accepts `STARTING_HOST` or `CALIBRATING` as runtime states: Runtime v1 never reports them, and they are accepted only as host states. `WAITING_FOR_LEASE` (queued behind another session) stays Initializing with the detail "Waiting for the GPU". This is a deliberate extension of the startup proposal, recorded in `04_STARTUP_PROPOSAL_V21.md`. |
| **R3-03 MEDIUM**: cited evidence was not committed | **Repaired.** `evidence/final/` is committed: haze probe and gates, size crop, transparency gates and contrast sheets, the T4 diagnosis, rehearsal logs, the full test log and the boundary check. |
| **R3-04 MEDIUM**: R2 conclusions overreach | **Repaired.** `R2_RESULTS.md` "Reading" is rewritten. The control is close to Ember by construction. Only still frames were scored, so the round makes no claim about motion. The 90 % finding is limited to "this cut-out", not "any artwork". (b) is weak evidence. The final report follows the same wording. |
| **R3-05 MEDIUM**: launch still shows depleted first; no live evidence | F-START-GAP stays an owner decision (launcher). After the R3-01 repair, the live first-time run records timed state sequences of the real startup; see the final report, section 6. |
| R3-06 LOW: live driver loses the first state after a reset | **Repaired.** `lastState` is reset with `states`. |
| R3-07 LOW: class doc comment misplaced | **Repaired.** The class doc comment is back on `OiCompanionSource`. |
| R3-08 LOW: intermediate commit `e43e97a7` failed the suite | **Disclosed** in the final report. The suite at the repaired commit is the evidence of record (`evidence/final/full_flutter_test.log`). |
| R3-09 LOW: stale startup documents | **Repaired.** `04_STARTUP_PROPOSAL_V21.md` has a dated status note. The owner's approval of the direction is recorded in `FINAL_REPORT_V21_FINAL.md`. |
| R3-10 LOW: wording | **Repaired.** Protocol change log C-2, the decoder (lowest values to one decimal place; caveat on any AC-F1R PASS), and the `R2_RESULTS.md` corrections. The access-audit wording now matches the audit files. |
| R3-11 LOW: definition of the size-crop "cut"; file count | **Repaired.** The `size_crop_v21.py` docstring now defines "cut". The plan says 23 non-asset files. |
| R3-12 LOW: dark blob at the depleted feet and hard head rim on light desktops | **Open**, as F-LIGHT-1 (owner decision on the light-desktop treatment). |

Note on the haze metric: R3 measured 61.1 % -> 25.9 % of the cell darkened on white, against 11.4 % from
`haze_probe_v21.py`. R3 counted every darkened pixel, including the character itself. The probe excludes a 6 px
dilation around the character. Both measurements show the reduction.
