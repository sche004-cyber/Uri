# Recheck R4 (d12e70ed): repairs

- **Reviewer:** a separate, read-only Claude agent; imported review, not counted by the driver.
- **Verdict: ACCEPT WITH FINDINGS.**
  - R3-01 (HIGH) and R3-02 are verified as repaired.
  - All new findings are LOW.
  - Full text: `R4_recheck_d12e70ed.md`.

| Finding | Action |
|---|---|
| R4-N1: stale health plus a fresh runtime `STOPPED` | **Repaired.** A `STOPPED` runtime now counts as a startup only while a Brain host is running. Test: "health older than a STOPPED read ...". |
| R4-N2: the unavailable detail names the stale state | **Repaired.** New function `brainUnavailableDetail`: it names a failing host state, or a newer health readiness, before the polled state. Test: "the unavailable detail names the newer state". |
| R4-N3: `WAITING_FOR_LEASE` history; deviations unrecorded | **Repaired.** The `R3_repairs.md` row is corrected, and the `04` status note lists the four deviations. |
| R4-N4: T4 extent understated | **Repaired.** The final report says 70 of 72 frames, 7-14 px, worst 14 px at frame 8. |
| R4-N5: evidence not pinned to a commit | **Repaired.** `boundary_check_final.txt` is regenerated at the final HEAD. `full_flutter_test.log` now begins with the base SHA and the working-tree state it ran on; the content was then committed unchanged as the R4 repair commit. |
| R4-N6: final report section 6 was a placeholder | **Repaired.** Section 6 is filled from the committed live run at `d12e70ed` (`evidence/final/live/`). |
| R4-N7: R3-08 not disclosed | **Repaired.** Final report, section 7. |
| R4-N8: earlier report stale | **Repaired.** A forward pointer was added to `FINAL_QUALIFICATION_REPORT_V21.md` section 8. |
| R4-N9: R2 audit wording; stale bullet | **Repaired** in `R2_RESULTS.md`. |

**Owner observations raised by R4, recorded and not changed (pre-existing behaviour or owner choices):**
- A stale `READY` shows idle for up to 15 s after the Brain stops.
- A requested restart looks depleted during its stop and memory-release phase.
- `WAITING_FOR_LEASE` stays calm for as long as another workload holds the GPU, while `brain_health` reports
  UNAVAILABLE. The detail "Waiting for the GPU" stays visible.

**Correction (after recheck R5, MEDIUM finding R5-N1).** When this file was committed at `5d05f4dc`, the rows for R4-N5
(boundary check regenerated), R4-N6 (section 6 filled) and R4-N7 (section 7 disclosure) were marked "Repaired",
but that work had not yet been done. The claims were false at that commit. The work was done in the next commit:
see `R5_repairs.md`. The rows above are kept as written, to preserve the history.
