# Recheck R5 (5d05f4dc): repairs

- **Reviewer:** a separate, read-only Claude agent; imported review, not counted by the driver.
- **Verdict: REVISE.** One MEDIUM finding: three repairs in `R4_repairs.md` were claimed before the work was done.
- Full text: `R5_recheck_5d05f4dc.md`.
- The repairs below are in the commit that adds this file. Each one was checked against that commit before it was
  written here.

| Finding | Action |
|---|---|
| **R5-N1 MEDIUM**: false "Repaired" claims; documents cited placeholders | **Repaired.** A correction note in `R4_repairs.md` keeps the history. `FINAL_REPORT_V21_FINAL.md` sections 6, 7 and 8 are filled from committed raw files; no placeholder remains (`grep TBD` finds nothing). Section 7 discloses `e43e97a7`. `boundary_check_final.txt` is regenerated in a follow-up commit, at this commit; see its header. The `R3_repairs.md` and `09` wording is corrected. |
| R5-N2 LOW: the detail and the guard assumed opposite snapshot ages | **Repaired in code.** New function `brainHealthIsNewer`: the worker stamps both snapshots with `checked_at`, so the newer one is decided rather than assumed. `brainUnavailableDetail` never uses an older or unstamped report, and never lets `UNKNOWN` replace a known state. `brainStartingDetail` ignores an older report. Tests: "the newer snapshot decides when both are stamped", plus an unstamped case. |
| R5-N3 LOW: R4-N1 guard regressed the no-host path; residual | **Repaired.** With stamped snapshots, a newer health `LOADING` or `READY` keeps the calm look even with no host, which restores the off-path behaviour. With an older report, only the runtime state counts, which closes the stale `host.running` residual. The host guard now applies only when a timestamp is missing. |
| R5-N4 LOW: documents not updated for the code change | **Repaired.** Final report section 4 (mapping row, 11 tests) and deviation 2 in the `04` status note. |
| R5-N5 LOW: limits of the live evidence | **Repaired.** Final report section 6, "Limits". It covers provenance (runner task output with the SHA), the pre-repair code, the host-only path not demonstrated, the unexplained ~11 s depleted window (part of F-START-GAP), the DEGRADED recovery, and the "recovered-idle" label that actually shows success. |
| R5-N6 LOW: R2 audit wording | **Repaired.** `R2_RESULTS.md` explains that the audit script reduces the Glob path argument to its parent folder. |

Final full suite at this code: 602 passed, 5 skipped, 0 failed (`evidence/final/full_flutter_test.log`).
