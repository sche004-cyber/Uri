# M39 independent re-audit of repair commit `0d690ea`

- **Audited commit:** `0d690ea0e1dbb35b17360a6bd36e99d7c5c3bb67` (branch `claude/project-thread-wb7tmm`), repair round 5 over `736464a`.
- **Prior audit:** `b74519b` on `claude/project-thread-h6lbhn` (`docs/reviews/M39_INDEPENDENT_AUDIT_736464a.md`), verdict REPAIRS_REQUIRED.
- **Auditor:** Claude, in a fresh audit thread. Codex is paused. This audit did not repair anything and pushed nothing to the M39 branch.
- **Date:** 2026-09-29, Linux cloud container (Python 3.11.15). No Windows host was available.
- **Evidence:** `docs/reviews/M39_REAUDIT_0d690ea_evidence/`. A copy of this report is in `/mnt/project-files/audits/M39_REAUDIT_0d690ea.md`.

## Verdict: **ACCEPT**

Each finding in the repair round (F3, N3, F4, N1, N2, and F2 as a recorded limitation) is fixed. I verified this from the code, by running the new regression tests against the old code, and with my own probes. I found no false success and no change to frozen or live-app files. The suite, qualifications, governance checks, anchors and dry-run benchmark all pass.

There is one new LOW finding (R5-1) of the same kind as N3, plus two nits. None of them blocks. They can go in with the next M39 code change.

One governance item needs Chetan's decision: M37-L3 is recorded in the frozen M37 records, and his acceptance of it is still pending (G-1).

**M39 stays PROVISIONAL, NOT FROZEN.** This round did not cover F1 (R1.1 or R0 scope, Chetan's decision) or the live harness pilot, and both still gate closure.

## 1. Acceptance criteria (defined before inspection)

| # | Criterion |
|---|---|
| AC-1 | Every in-scope finding (F3, N3, F4, N1, N2) is fixed in the code or doc it names, and I confirm each fix by reading the code and by observed behaviour. F2 is recorded as a limitation with no code change. |
| AC-2 | The repair's regression tests fail on `736464a` and pass on `0d690ea`, which I reproduce myself. |
| AC-3 | I rerun the full `tests/` suite, the M36/M37/M38 qualifications, the governance validator and suite, the M33.3 anchors and the M39 dry-run benchmark, and record the results as observed. |
| AC-4 | A diff against the freeze commit `5bbf738` shows no change to frozen code or live-app files. The only change to a frozen test is the authorized M37 entry, pinned by hash. |
| AC-5 | Adversarial probes cover the new wording (consent screen, HARNESS_FAILED reply) and the stricter frozen check. Each probe set has a positive control. |
| AC-6 | I rerun my predecessor's fake-success probes and none of them now reaches a false success. |
| AC-7 | The repair thread's claims are compared with what I observed, and any difference is stated. |

## 2. Checks rerun (AC-3, AC-4)

| Check | Observed result | Evidence |
|---|---|---|
| `pytest tests/ -q` | **1528 passed, 0 failed, 9 skipped**, 130 subtests (EXIT 0). This matches the claim. | `tests_dir.txt` |
| M36 memory qualification | EXIT 0; 189 cases × 2 runs, `wrong_confirmed` 0, `invented_ids` 0, deterministic | `m36_memory_qualification.txt` |
| M37 edge qualification | EXIT 0, `gate_passed: true` | `m37_edge_qualification.txt` |
| M38 harness qualification | EXIT 0, `gate_passed: true` | `m38_harness_qualification.txt` |
| Governance validator | `VALID: docs/governance/URI_STATE.yaml — no DCL violations found.` | `governance_validator.txt` |
| Governance suite `tests/governance` | 37 passed | `governance_tests.txt` |
| M33.3 anchors | `ok: True`, `changed: []`, RAR `4db77566…5e1b95` | `anchors.txt` |
| M39 benchmark `--dry-run` | EXIT 0, gate PASS, 5/12 oracle-confirmed; tasks 05, 06, 08, 09 and 10 not measured (need a real harness, as before) | `m39_bench.json`, `m39_bench_stdout.txt` |
| Diff `5bbf738..0d690ea` | 96 files. Outside M39's own paths only four: `docs/governance/URI_ACTIVE_MILESTONE.md`, `docs/governance/URI_STATE.yaml`, `docs/plans/URI_BATCH_M36_M37_M38_FREEZE_RECORD.md` (additive text only, **0 removed lines**) and `tests/test_m37_edge_resolution.py`, whose SHA-256 is `f288b194…236853`, equal to the pin. No file under `uri_v1/memory`, `uri_v1/edge`, `uri_v1/execution`, `uri_core`, `uri_ui` or `uri_ui.py` changed. | `frozen_scope_namestatus.txt` |
| Diff `736464a..0d690ea` | 9 files: `uri_v1/office/{flow,view}.py`, the M39 fixture, three M39 tests, the M39 report, `URI_STATE.yaml` and the freeze record | `git diff --stat` |

Environment note: my first two suite runs failed because of the environment, not the code. The first had missing `google` packages, which `requirements.txt` does not declare. The second had `openpyxl` installed only in user site-packages, which the verifier's scrubbed `HOME` hides from its subprocess, so 46 tests failed across M37, M38 and M39. After a system-wide install, the run above came back clean. I discarded both failed runs and did not count them as evidence.

## 3. Finding-by-finding verification (AC-1, AC-2)

I checked out `736464a` in a separate worktree, added only the new test file and the fixture scenario, and ran them. **All 14 new tests fail on the old code. All 14 pass on `0d690ea`.** The existing `test_m39_repair4_regressions.py` passes 8/8 on the old code too, so it is not a new failure.

| Finding | Status | Code and behaviour checked |
|---|---|---|
| **F3 (MED)** consent screen said "never the network" and did not name the harness | **FIXED** | `view.py:43-55`: the screen names the harness from `adapter.harness_type` (`flow.py:_harness_name`) and says the file contents "will be sent to Claude Code / Codex CLI, which passes them over the network to its external model provider". The posture line now says the posture limits the harness's own tools and "does not stop the file contents above from reaching the provider". No "never the network" text is left anywhere in `uri_v1/office` or `scripts/m39_*`. Probed for Claude Code, Codex CLI, no harness configured, and a harness that is configured but not installed (§4). The posture claims match the adapters: Claude Code gets `--disallowedTools WebFetch WebSearch Bash` (`adapters.py:149`) and Codex gets `network_access=false` (`adapters.py:237`). |
| **N3 (MED)** reply said "Nothing was written to your files" after the harness wrote the original | **FIXED** as stated | `view.py:63-84`: if either ORIGINAL_MODIFIED flag is set, the reply warns that the original(s) changed, names them, says URI did not undo the change, and says the task stays open. The file names come from the frozen runner's `uri_observations.originals_changed` (`runner.py:77,88`), read through `run["result"]`. That is the same path the frozen `verify.py:287` reads, and a read failure falls back to "one or more of your original files". I confirmed "task stays open" against Memory: status `OPEN` in every probe. Probes covered a changed original, a deleted original, both originals changed, and a change during verification (§4). See R5-1 for the case with no flag. |
| **F4 (LOW)** test wrote to `/dev/null` | **FIXED by code; Windows not run** | `test_m39_repair4_regressions.py:113-116` uses `tmp_path / "bench.json"`. No other `/dev/null` is left in M39 tests or scripts. I had no Windows host to run it on. |
| **N1 (LOW)** frozen-files check allowed rollback to pre-freeze versions | **FIXED** | `test_m39_boundaries.py`: `KNOWN_UPSTREAM_REPAIRS` and `_matches_some_upstream_repair` are removed, and the only exemptions left are the M39 prefixes and the hash-pinned M37 test. On a disposable clone the guard failed for **all 37 tampers inside its scanned roots**: 31 rollbacks (each frozen file that changed after `763d8e7` or `b013dba`, restored to that commit's version), an M36 `sources.py` rollback, deleting `verify.py`, a new untracked file in `uri_v1/edge`, drift in the authorized M37 test, `chmod +x` on a frozen file, and an edit to `uri_core/app/server.py`. The clean clone passes, and so does an edit to an M39 file (positive controls). Results: `probes/n1_guard_probe_results.txt`. |
| **N2 (LOW)** stale M39 `URI_STATE.yaml` entry | **FIXED (additive)** | New `status_correction_2026_09_29_audit_736464a` and `repair_round_5_2026_09_29` fields. The stale fields stay as history, following the repository's additive convention, and the correction lists each one and says why it is stale. Its content matches the repository. See R5-2 for a similar stale note in another file. |
| **F2** frozen M37 guard's `uri_v1/edge/` and `uri_v1/execution/` prefixes | **RECORDED** as M37-L3, no code change | Freeze record §7 and `retained_limitation_addendum_2026_09_29` on the M37 entry. The frozen M37 test is unchanged apart from the pinned entry. Both texts say plainly that Chetan's acceptance is not yet recorded. See G-1. |

## 4. Adversarial probes (AC-5, AC-6)

**My predecessor's fake-success probes, rerun unchanged** (`probes/predecessor_probes_rerun.txt`, 14 passed): these probes tamper with the workbook, add an extra file, hardcode the output (two variants), make the candidate script a symlink out of the workspace, write the original directly, and claim VERIFIED in text. All of them end in HARNESS_FAILED, and apart from `write_original` none of them changes an original. The honest control reaches AWAITING_APPROVAL and then COMPLETED. The results match the predecessor's, apart from the `write_original` render, which now carries the new truthful warning. The case and width variants are also unchanged.

**New harness probes** (`probes/_r5_fake.py`, `probes/_r5_probe_test.py`, `probes/r5_probe_results.txt`):

| Harness behaviour | URI result | Reply text | Verdict |
|---|---|---|---|
| deletes `report.py` (and fixes the workspace copy) | HARNESS_FAILED, `ORIGINAL_MODIFIED_DURING_RUN` | warns and names `report.py`; task open | correct |
| appends to `report.py`, no fix | HARNESS_FAILED, same flag | warns and names `report.py` | correct |
| changes both originals and fixes | HARNESS_FAILED, same flag | names `report.py, sales.xlsx` | correct |
| rewrites the original with identical bytes, then fixes | AWAITING_APPROVAL | normal | correct (nothing changed) |
| writes a new `harness_notes.txt` into the user's folder, no fix | HARNESS_FAILED, no flags | **"Nothing was written to your files."** | **R5-1** |
| writes `harness_notes.txt` and fixes | AWAITING_APPROVAL (report.py only is written back) | no mention of the stray file | known no-OS-sandbox limitation; my strict assertion in this probe fails, and that failure is the recorded observation |
| honest fix (control) | AWAITING_APPROVAL | normal | control passes |
| Codex CLI adapter, consent screen | — | "Harness: Codex CLI. … external model provider …" | correct |
| harness configured but not installed | screen names Claude Code, and approval returns HARNESS_UNAVAILABLE ("Nothing was started") | — | acceptable (see N-2) |

## 5. Findings from this re-audit

| ID | Severity | Where | Finding |
|---|---|---|---|
| **R5-1** | LOW | `uri_v1/office/view.py:83-84`, pinned by `test_m39_repair5_regressions.py` (flags0 case) | **A HARNESS_FAILED reply with no flags still says "Nothing was written to your files", which URI cannot know.** No flag proves only that the manifest originals kept their hashes. In the probe, the harness wrote a new file into the user's authorized folder and the reply still said nothing was written. This is an instance of the frozen no-OS-sandbox limitation (M38-L2/S-L1). The real Claude Code adapter restricts file tools to the workspace path, so the realistic ways in are the harness escaping its tool scope or the verifier running harness code. No false success follows from it, which is why it is LOW, but it is the same false-reassurance problem as N3. **Fix:** in every branch, say "URI wrote nothing back to your files" instead of "Nothing was written to your files". Optionally add one line to the consent screen saying the harness is not OS-sandboxed. The fix is a wording change inside M39's own files and can go in with the next M39 change. |
| **R5-2** | LOW (docs) | `docs/governance/URI_ACTIVE_MILESTONE.md` | The M39 planning notes there still say M39 is "planned, not implemented" and depends on PROVISIONAL M36 `405db1f`. That is the same staleness N2 fixed in `URI_STATE.yaml`, and no correction note was added. Pre-existing, not introduced by `0d690ea`. |
| **N-1** | nit | `view.py:78-79` | "…not by URI's write-back (Claude Code): report.py" puts the harness name next to "URI's write-back", which can read as if Claude Code did URI's write-back. Suggested wording: "…changed by Claude Code during the harness run, not by URI's write-back: report.py". |
| **N-2** | nit | `flow.py:_harness_name` | If the harness is configured but not installed, the consent screen still says the files "will be sent to Claude Code". Approving then fails safely with HARNESS_UNAVAILABLE and nothing is sent, so nothing is harmed. |

### Governance item for Chetan

- **G-1: M37-L3 is recorded in frozen M37 records with acceptance pending.** `0d690ea` adds §7 to the freeze record and a `retained_limitation_addendum_2026_09_29` field to the M37 entry, which is marked `mutable: false`, in `URI_STATE.yaml`. Both additions are text only and both say "User acceptance not yet recorded", so nothing is misrepresented. But a retained limitation on a frozen milestone formally needs Chetan's acceptance, as the other limitations got at the 03:24 freeze. **Decision needed:** accept M37-L3 as a retained limitation, or ask for a different treatment. It does not affect this verdict.

### Claim precision (AC-7)

| Repair thread claim | Observed |
|---|---|
| Each finding fixed, with 14 regression tests that fail on the old code | Confirmed: 14 fail on `736464a` and 14 pass on `0d690ea`. |
| F2 recorded as M37-L3, no code change | Confirmed. |
| Suite 1528/0/9 | Confirmed. |
| Quals pass, governance VALID, anchors unchanged | Confirmed. Governance suite 37 passed. |
| "Only M39's own files and docs changed" | **Imprecise.** The commit also appends to the batch freeze record and to the frozen M37 entry in `URI_STATE.yaml`. Both changes are additive docs and were requested by the audit (F2), so they are allowed, but they are not M39's own files (G-1). |

## 6. Not verified, and whether it matters

- **Windows.** I did not run the F4 fix or the new N1 tests on Windows. The N1 tests use `git clone --shared`, and my predecessor noted that Codex saw clone setup errors on Windows. The fix is correct by reading, and a Windows run is needed before any claim about the full Windows suite. It does not change the verdict.
- **Live harness.** I did not run a real Claude Code or Codex. The consent-screen wording is checked against the adapter code only (M38-L1, live pilot pending). It does not change the verdict.
- **Guard coverage outside its scanned roots (informational, pre-existing).** `test_m36_m37_m38_and_frozen_files_unchanged` scans `uri_v1 uri_core uri_ui tests scripts fixtures`. So an edit to the root file `uri_ui.py` (PyQt UI) or a git-ignored file (for example under `__pycache__`) passes it. My own whole-tree diff against `5bbf738` shows neither changed, so it does not affect this verdict. Adding `uri_ui.py` to the pathspec would be a small hardening of M39's own guard.

## 7. Self-review against the acceptance criteria

- AC-1 and AC-2 are met: every finding has a disposition backed by code or a probe, and I ran the old code myself to show the regression tests fail on it.
- AC-3 and AC-4 are met: all checks were rerun here, and the discarded runs caused by the environment are disclosed in §2.
- AC-5 is met: I probed the wording four ways and the guard 36 ways, each set with positive controls.
- AC-6 is met: all of my predecessor's probes were rerun.
- AC-7 is met: one imprecise claim is recorded above.
- Correction to my own work while drafting: an early harness-probe file, `write_sibling_and_fix`, asserted that the run must never verify. That expectation was wrong because it tests the frozen no-sandbox limitation, not an M39 defect. I kept the failing result as the recorded observation and did not edit the assertion to make it pass.
- ACCEPT is consistent with the findings: nothing left is above LOW, and nothing touches a frozen guarantee, a live-app file or success reporting.
