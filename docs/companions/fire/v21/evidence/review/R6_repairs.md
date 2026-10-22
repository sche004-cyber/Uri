# Recheck R6 (b4ff2ed2): repairs

- **Reviewer:** a separate, read-only Claude agent; imported review, not counted by the driver.
- **Verdict: ACCEPT WITH FINDINGS.** No HIGH or MEDIUM findings; 8 LOW.
- **What R6 confirmed:**
  - all R5 findings are repaired;
  - no path shows a real Brain failure as Initializing;
  - no regression of normal startup;
  - no protected path changed;
  - 602/5/0 at `b4ff2ed2`, from its own run.
- Full text: `R6_recheck_b4ff2ed2.md`.

All repairs below are in the commit that adds this file. Each was checked against the files before this file was
written.

| Finding | Action |
|---|---|
| R6-1: section 6 numbers | **Repaired.** Shell 14.8 s (raw 14.839). Initializing about 12-13 s after the host started, with the reference times. The same figure is used in the report and in `09`. |
| R6-2: transition statistic included the cold start | **Repaired.** Frame 0 is excluded. p99 8.7 / 4.6 ms; worst 8.7 / 4.6 ms. The cold start (53 / 34 ms) is stated separately. |
| R6-3: "all MEDIUMs repaired" | **Repaired.** Now reads "repaired or disclosed; R3-05 (F-START-GAP) stays open". |
| R6-4: forward references | **Repaired.** Section 8 R6 row and the commits table now describe `b4ff2ed2` and this commit as they are. This file and the review exist in this commit. |
| R6-5: "scored identically" overstated | **Repaired** in the report and in `R2_RESULTS.md`: one 0.5-point difference on two items. |
| R6-6: R3_repairs wording claimed corrected | **Repaired.** The R3-05 row is corrected, and a correction note in `R5_repairs.md` keeps the history. |
| R6-7: stamped path not tested end to end | **Repaired (test only).** The test worker can stamp `checked_at`. A new conversation-level test covers newer health with a failed host, newer health READY over a stale STOPPED, and older health (12 tests in the file). Production code is unchanged since `06370431`. |
| R6-8: "untracked" perf output | **Repaired.** The wording now says what was moved, from where, and that it is committed. |

**Owner item from R6, recorded:** AC-P1 is met on median VRAM (147.2 vs 147.4 MB). The peak is 8.1 MB higher
(183.5 vs 175.4), from the `kindling` clip. The owner may rule on whether peak counts.
