# Dynamic planning slice 1: focused independent re-check of R3-1 at `0c56215` (and branch head `28fcbf9`)

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

## Addendum: branch head `28fcbf9` (verdict holds: ACCEPT at `28fcbf9`)

The branch head moved to `28fcbf9`, which sits on `0c56215`. It changes only two files: `tests/test_dynamic_planning_boundaries.py` and a report note. There is no change under `uri_v1/`, `scripts/` or `fixtures/`, so qualification behaviour is the same as at `0c56215`. `test_no_existing_module_imports_planning` now scans `git ls-files '*.py'` instead of every file on disk, and falls back to the old walk if git is unavailable.

I reran everything at `28fcbf9` itself:

| Check | Result | Evidence |
|---|---|---|
| Full suite | **1449 passed, 1 failed, 9 skipped**. The one failure is the accepted `test_m36_and_frozen_files_unchanged`. | `full_suite_summary_28fcbf9.txt` |
| Slice tests | 147 passed | `slice_28fcbf9.txt` |
| Frozen files | `5bbf738..28fcbf9` contains additions only; `verify.py` unchanged | `frozen_28fcbf9.txt` |
| Boundary test still bites | I created `uri_v1/zz_probe_importer.py` importing planning. While untracked, the test **passes**. Once `git add`ed, it **fails**. A tracked `tests/` importer also **fails**. After cleanup, the test passes. | `boundary_test_probe.txt` |

**Judgement: sound and in scope.** The test now guards tracked, committed code only. That is the code CI and reviewers see, and it is what the rule is about. The narrowing is that a new importer is not caught until it is staged. It cannot reach a commit uncaught, because a clean checkout makes every file tracked. The change removes a false failure caused by local scratch files; my own probe file hit this in round 1 (I-6).

Qualification at `28fcbf9` was not rerun: no code, fixture or script changed since `0c56215`, where it passed 34/34.

## Addendum 2: branch head `b6b2cb0` (2026-10-01; verdict holds: ACCEPT at `b6b2cb0`)

`b6b2cb0` sits on `28fcbf9` and changes two files: `tests/test_dynamic_planning_attestation.py` and the implementation report. The test change replaces a `_DataclassParams(...)` constructor call, which needs 6 arguments on 3.11 and 10 on 3.12+, with `copy.copy(params)` and `frozen = False`. Nothing under `uri_v1/`, `scripts/` or `fixtures/` changed since `28fcbf9` (`code_changed_since_28fcbf9.txt` = 0), so the attestation logic is unchanged.

| Check | Result | Evidence (`dynamic_planning_f2_recheck_0c56215/b6b2cb0/`) |
|---|---|---|
| Slice tests by Python version | 3.11: **147 passed**; 3.12: **147 passed**; 3.13: **147 passed** | `slice_by_python.txt` |
| The fix addresses a real failure | The `28fcbf9` version of the attestation test: 3.11 31 passed; 3.13 **1 failed**, 30 passed | `old_test_by_python.txt` |
| The tamper case still tampers | On 3.11 and 3.13 the copied params have `frozen=False` while the original stays `True`. Installing them gives `GENERATED_MISMATCH`, and restoring them attests again. | `tamper_check.txt` |
| Genuine catalog on 3.13 | Attests, because the record digests are source-based. Seen in `tamper_check.txt` (restored → `None`) and in the 3.13 slice run. | same |
| Full suite (3.11) | **1449 passed, 1 failed** (only the accepted `test_m36_and_frozen_files_unchanged`; 18 offenders, all slice paths), 9 skipped | `full_suite_summary.txt`, `guard_offenders.txt` |
| Slice qualification (3.11) | exit 0, 34/34, all six counters 0, C33 semantic miss 1/1, gate passed. The result file differs only in latency (0 other lines). | `dp_qualification.txt`, `qual_nonlatency_diff_lines.txt` |
| Governance | 37 passed, VALID | `governance.txt` |
| Frozen files | `5bbf738..b6b2cb0` contains additions only; `verify.py` unchanged | `frozen.txt` |

**Not run here:** the full suite and qualification on 3.12 and 3.13 (only the slice tests ran there; the venvs had only pytest and openpyxl), Windows, and `graphify update .`. None of these affects the verdict for a test-only change.

## Addendum 3: package move `b6b2cb0..565eae8` (2026-10-01; verdict: **ACCEPT at `565eae8`**)

Chetan picked "Move, then freeze" at 12:23. `565eae8` moves the slice's 9 code files from `uri_v1/execution/planning/` to `uri_v1/planning/`. This re-check covers the move only. Evidence is in `dynamic_planning_f2_recheck_0c56215/565eae8_move/`.

| Check | Result |
|---|---|
| Pure move | 8 of the 9 files are renamed byte-for-byte (`R100`). `actions.py` changes only in `QUALIFICATION_PATH` (`parents[3]` → `parents[2]`, for the shallower location) and the re-pinned record digest. Every other change in `scripts/`, `tests/` and `fixtures/` is an import path or a path constant. The slice's own boundary test now checks for `uri_v1.planning` instead of `execution.planning`. Tracked `.py`/`.json` files contain no references to the old path, and the old directory is gone. |
| Record honest | Normalising module names, digests and the note shows the regenerated record is identical to `b6b2cb0`'s: same statuses, boundaries, mechanisms and evidence text. Each digest recomputed now equals its recorded value, all four adapters attest, and the pinned digest `9998e2b2…` matches the file. The digests changed only because the module name is part of the hashed implementation. The battery and gate files, workbooks and generator are byte-identical to `b6b2cb0`. (`record_honesty.txt`) |
| Attestation still refuses tampering | My P1-P13 and Q1-Q7 probes, with paths updated, give the same results as at `b6b2cb0`. P1-P4 and Q1-Q5 are refused. P5 and Q6 are the recorded residual. (`probe_results.txt`) |
| Slice tests | Python 3.11: 147 passed; Python 3.13: 147 passed |
| Qualification (3.11) | exit 0, 34/34, all six counters 0, C33 semantic miss 1/1, gate passed. The result file differs only in latency. |
| Full suite (3.11) | **1449 passed, 1 failed, 9 skipped.** The one failure is the accepted guard. It has **27** offenders: the 18 previous ones plus the 9 moved code files, which now sit in `uri_v1/planning/` instead of the guard's allowlisted `uri_v1/execution/`. All 27 are slice paths; none is a frozen M36-M38 path. That count is expected for this move. |
| Review set / anchors / governance / M36-M38 quals | 113 passed / ok, changed [] / 37 passed, VALID / exit 0 each |
| Frozen files | `5bbf738..565eae8` contains additions only; **0** files changed under `uri_v1/execution`, `uri_v1/edge` and `uri_v1/memory`; `verify.py` unchanged |
| Import boundary after the move | The frozen M37 import check no longer covers `uri_v1/planning/`. The slice's own `test_planning_imports_nothing_outside_its_boundary` still does, and it passes. Planning imports only `uri_v1.edge.report` and `uri_v1.execution.{acceptance, lineage, officefile, verify, workspace}` (`planning_imports.txt`), the same set as before. |
| Freeze draft applied to `565eae8` (scratch, not committed) | Governance 37 passed, VALID; anchors ok; full suite 1449/1, accepted guard only (`with_freeze_patch.txt`) |

**Review of the freeze draft (`freeze_draft_on_565eae8.patch`) against Chetan's 12:22 authorization.** It meets the authorization. Small fixes before commit:

1. The §2 audit-chain row "Focused re-check of the move: PENDING" should cite this addendum's commit and read ACCEPT.
2. Item 4 of the authorization ("without modifying the previously frozen components") has no evidence row at `565eae8` in §3. Add one: `git diff 5bbf738 565eae8` contains additions only, 0 files under `uri_v1/execution|edge|memory`, `verify.py` unchanged. I verified this here.
3. The §1 "verbatim" quote stops before Chetan's last two sentences (follow-up reporting). Either label it an excerpt or quote it in full.
4. DP-L3 says "Effect guard declined", citing a "Freeze, no guard" card that I could not see. It is consistent with the 12:22 message, which says the freeze does not approve the guard. If that card cannot be cited, "not approved; not implemented" is the wording that is true regardless.

Windows is recorded correctly: not performed at `565eae8`; at `b6b2cb0` it was reported from Chetan's PC but is not a repository artifact (DP-L8, §3a).
