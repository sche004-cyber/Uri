# Dynamic planning slice 1: focused independent re-check of R3-1 at `0c56215`

- **Subject:** `0c56215` on `claude/dynamic-planning-slice1-2eemmh`, written by the implementation thread on top of `06a920b`.
- **Auditor:** Claude, in the audit thread that wrote `5eb0149` and `d3d26de`. This thread did not write any slice code.
- **Scope:** Chetan chose a focused re-check of this commit (2026-09-30 15:44), with no new open-ended tampering investigation. This is an audit only, and no slice file was changed.
- **Date / platform:** 2026-09-30, Linux, Python 3.11.15. Windows was not run.
- **Evidence:** `docs/reviews/dynamic_planning_f2_recheck_0c56215/`.

## Verdict: **ACCEPT** (slice stays PROVISIONAL / NOT FROZEN until Chetan decides)

Chetan's bounded repair round asked for the following, and each item was checked here.

| # | Requirement (Chetan, 15:43) | Result | Evidence |
|---|---|---|---|
| 1 | Apply the R3-1 repair and add Q1 as a permanent regression test | **Met.** `_MACHINERY` / `_plain_member` / `FOREIGN_MEMBER` are the auditor's prototype, with the unused `cls` argument dropped. `test_hook_object_on_a_uri_class_is_refused` runs Q1 through the real runner: NOT_ATTEMPTED, detail `FOREIGN_MEMBER`, nothing written outside the workspace. My own Q1 probe gives the same result. | `probe_results.txt`, diff `06a920b..0c56215` |
| 2 | Correct the F2R-3 closure claim | **Met.** Report §10 keeps the old text and appends a correction saying "Closed" was false at `06a920b`. | report §10 |
| 3 | Record the remaining in-process limitations in §6.16, with no claim that attestation is a complete boundary | **Met.** §6.16 adds: "any other in-process modification of URI's already-running code or state … Attestation is not a containment boundary against a process that is already tampered with; containment is the effect guard or an OS sandbox." P5 (`builtins.open`) and Q6 (`sys.modules` swap) still attest, as §6.16 says they do. | report §6.16, `probe_results.txt` |
| 4 | Do not pursue R3-2 or R3-3 unless they are blockers | **Not followed, and harmless.** `0c56215` was pushed at 15:42:36, before Chetan's 15:43 message, and includes both latent fixes. They are +27/−2 lines in total with the R3-1 change, in `attestation.py` only. The record and all four adapter digests are unchanged: P13 reproduces the `06a920b` digests. No slice test, qualification case or probe changed outcome except the intended ones (Q5 is now `IMPLEMENTATION_CHANGED`). Chetan accepted this commit, extras included, by choosing the re-check. | `frozen.txt`, `probe_results.txt` |
| 5 | Rerun the affected tests, full suite, qualification, governance and frozen-file checks | **Met (my own reruns).** Slice tests **147 passed**. Qualification exits 0: 34/34, all six counters 0, C33 semantic miss 1/1, gate passed; the rewritten result file differs from the committed one only in latency. Review set 113 passed. Anchors ok with changed []. Governance 37 passed and VALID. M36/M37/M38 qualification exit 0 each. `git diff --name-status 5bbf738 0c56215` shows 38 additions only; `verify.py` is identical. | `slice.txt`, `dp_qualification.txt`, `review.txt`, `anchors.txt`, `governance.txt`, `m36_m38_qualification.txt`, `frozen.txt` |
| 6 | The only full-suite failure is the accepted frozen-file guard on authorized slice paths | **Met.** Full suite **1449 passed, 1 failed, 9 skipped**. The failure is `test_m36_and_frozen_files_unchanged`. I recomputed its 18 offending paths, and all of them are `tests/test_dynamic_planning_*`, `scripts/dynamic_planning_*` or `fixtures/dynamic_planning/`. | `full_suite_summary.txt`, `guard_offenders.txt` |
| 7 | New tests prove the repair | **Met.** All four new tests fail when `attestation.py` is reverted to `06a920b` (4 failed), and pass at `0c56215`. | `new_tests_on_06a920b.txt` |

My round-1 and round-2 probes (P1-P13, Q1-Q7) were rerun at this head:
- P1-P4 and Q1-Q5 are refused before the adapter runs.
- P6, P7 and P9-P11 are refused as before.
- P5 and Q6 attest, as a recorded residual under §6.16.
- P8 is refused, which is harmless.
- P12 and Q7 attest, which is benign.
- P13 reproduces the record digests in a fresh interpreter.

As agreed, no new bypass classes were explored.

## Findings

None blocking.

- **N-1 (info):** the report's §11 says "the auditor's full probe script was not rerun here". That was true for the implementation thread; this re-check has now rerun it (`probe_results.txt`).
- **N-2 (info):** P3's fake module still runs during plan compilation, outside any adapter, as §6.16 records.

## Not verified

- **Windows and other CPython versions:** not run. A mismatch there fails closed; it cannot produce a false VERIFIED.
- **`graphify update .`:** not run. This is a docs-only commit, and graphify is not installed.

Freezing the slice is Chetan's decision; this re-check does not freeze it.
